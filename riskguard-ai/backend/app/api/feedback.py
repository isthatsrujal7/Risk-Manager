from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.models.database import get_db
from app.models.models import Review, Transaction, RiskAssessment, AuditLog, User
from app.schemas.schemas import FeedbackCreate
from app.auth import get_current_user, require_roles

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/summary")
def feedback_summary(db: Session = Depends(get_db)):
    total_reviews = db.query(Review).filter(Review.human_decision.isnot(None)).count()
    fp = db.query(Review).filter(Review.is_false_positive == True).count()
    fn = db.query(Review).filter(Review.is_false_negative == True).count()

    approved = db.query(Review).filter(Review.human_decision == "APPROVED").count()
    rejected = db.query(Review).filter(Review.human_decision == "REJECTED").count()
    escalated = db.query(Review).filter(Review.human_decision == "ESCALATED").count()

    total_assessments = db.query(RiskAssessment).count()
    total_fraud_flagged = db.query(RiskAssessment).filter(RiskAssessment.ml_prediction == "suspicious").count()
    actual_fraud = db.query(Transaction).filter(Transaction.is_fraud == True).count()
    actual_legitimate = db.query(Transaction).filter(Transaction.is_fraud == False).count()

    tp = min(total_fraud_flagged, actual_fraud)
    tn = max(0, actual_legitimate - fp)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    fp_cost = float(__import__("os").getenv("FP_COST_PER_INCIDENT", "50"))
    fn_cost = float(__import__("os").getenv("FN_COST_PER_INCIDENT", "500"))
    total_cost = fp * fp_cost + fn * fn_cost

    return {
        "total_reviews": total_reviews,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "approved_count": approved,
        "rejected_count": rejected,
        "escalated_count": escalated,
        "total_fp_cost": round(fp * fp_cost, 2),
        "total_fn_cost": round(fn * fn_cost, 2),
        "total_estimated_cost": round(total_cost, 2),
        "fp_cost_per_incident": fp_cost,
        "fn_cost_per_incident": fn_cost,
    }


@router.get("/errors")
def error_patterns(db: Session = Depends(get_db)):
    false_positives = db.query(Review).filter(Review.is_false_positive == True).all()
    false_negatives = db.query(Review).filter(Review.is_false_negative == True).all()

    fp_categories = {}
    fn_categories = {}
    for fp in false_positives:
        txn = db.query(Transaction).filter(Transaction.transaction_id == fp.transaction_id).first()
        if txn:
            cat = txn.merchant_category or "unknown"
            fp_categories[cat] = fp_categories.get(cat, 0) + 1
    for fn in false_negatives:
        txn = db.query(Transaction).filter(Transaction.transaction_id == fn.transaction_id).first()
        if txn:
            cat = txn.merchant_category or "unknown"
            fn_categories[cat] = fn_categories.get(cat, 0) + 1

    return {
        "false_positive_patterns": fp_categories,
        "false_negative_patterns": fn_categories,
        "total_false_positives": len(false_positives),
        "total_false_negatives": len(false_negatives),
    }


@router.get("/export")
def export_feedback_data(db: Session = Depends(get_db)):
    reviews = db.query(Review).filter(Review.human_decision.isnot(None)).all()

    dataset = []
    for r in reviews:
        assessment = db.query(RiskAssessment).filter(RiskAssessment.transaction_id == r.transaction_id).first()
        dataset.append({
            "transaction_id": r.transaction_id,
            "ai_recommendation": r.ai_recommendation,
            "human_decision": r.human_decision,
            "outcome": r.outcome,
            "is_false_positive": r.is_false_positive,
            "is_false_negative": r.is_false_negative,
            "ml_risk_score": assessment.ml_risk_score if assessment else None,
            "final_risk_score": assessment.final_risk_score if assessment else None,
            "behavioral_deviation": assessment.behavioral_deviation_score if assessment else None,
            "model_version": assessment.model_version if assessment else None,
        })

    return {"count": len(dataset), "dataset": dataset}


@router.post("/record-outcome")
def record_outcome(feedback: FeedbackCreate, user: User = Depends(require_roles("analyst", "admin")), db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.transaction_id == feedback.transaction_id).first()
    if review:
        review.outcome = feedback.outcome

    txn = db.query(Transaction).filter(Transaction.transaction_id == feedback.transaction_id).first()
    if txn:
        if feedback.outcome == "fraud" and txn.is_fraud:
            pass
        elif feedback.outcome == "legitimate" and not txn.is_fraud:
            pass

    audit = AuditLog(
        transaction_id=feedback.transaction_id,
        event_type="outcome_recorded",
        event_data={"outcome": feedback.outcome, "recorded_by": feedback.reviewer_name},
    )
    db.add(audit)
    db.commit()

    return {"status": "recorded", "transaction_id": feedback.transaction_id, "outcome": feedback.outcome}
