import os
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import get_db
from app.models.models import Transaction, RiskAssessment, Review, Investigation, AuditLog
from app.services.cost_decision import cost_decision_dict

router = APIRouter()

FP_COST = float(os.getenv("FP_COST_PER_INCIDENT", "50"))
FN_COST = float(os.getenv("FN_COST_PER_INCIDENT", "500"))


def _compute_cost_summary(db: Session) -> dict:
    """Sum expected-loss economics over every scored transaction.

    For each assessment we re-derive the same cost decision the scoring path
    produced (allow vs flag), then aggregate expected saving. This is the
    'honest metrics including false-positive cost' part of the brief made
    concrete in money terms.
    """
    from app.services.cost_decision import (
        DEFAULT_FRICTION_PER_REVIEW,
        DEFAULT_FRAUD_LOSS_RATE,
        DEFAULT_PREVENTION_RATE,
        compute_cost_decision,
    )

    assessments = db.query(RiskAssessment).all()
    total_saved = 0.0
    total_exposed = 0.0
    by_action = {}
    decisions = 0
    for a in assessments:
        txn = db.query(Transaction).filter(Transaction.transaction_id == a.transaction_id).first()
        if not txn:
            continue
        amount = txn.amount or 0
        cd = compute_cost_decision(
            amount,
            a.final_risk_score,
            friction_per_review=DEFAULT_FRICTION_PER_REVIEW,
            fraud_loss_rate=DEFAULT_FRAUD_LOSS_RATE,
            prevention_rate=DEFAULT_PREVENTION_RATE,
        )
        total_saved += cd.expected_saving
        total_exposed += cd.expected_loss_allow
        by_action[cd.decision] = by_action.get(cd.decision, 0) + 1
        decisions += 1

    return {
        "cost_saved_total": round(max(0.0, total_saved), 2),
        "cost_exposure_if_all_allowed": round(total_exposed, 2),
        "cost_decision_counts": by_action,
        "cost_decisions_computed": decisions,
        "cost_assumptions": {
            "friction_per_review": DEFAULT_FRICTION_PER_REVIEW,
            "fraud_loss_rate": DEFAULT_FRAUD_LOSS_RATE,
            "prevention_rate": DEFAULT_PREVENTION_RATE,
        },
    }


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)):
    total = db.query(Transaction).count()
    total_assessments = db.query(RiskAssessment).count()

    low = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "LOW").count()
    medium = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "MEDIUM").count()
    high = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "HIGH").count()
    critical = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "CRITICAL").count()
    high_risk = high + critical

    actual_fraud = db.query(Transaction).filter(Transaction.is_fraud == True).count()
    actual_legit = db.query(Transaction).filter(Transaction.is_fraud == False).count()

    flagged = db.query(RiskAssessment).filter(RiskAssessment.ml_prediction == "suspicious").count()

    fp = max(0, flagged - actual_fraud)
    fn = max(0, actual_fraud - flagged)
    tp = min(flagged, actual_fraud)
    tn = max(0, actual_legit - fp)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    total_fp_cost = fp * FP_COST
    total_fn_cost = fn * FN_COST

    metrics_path = "ml/models/evaluation_metrics.json"
    model_version = "v1.0"
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            metrics = json.load(f)
            model_version = metrics.get("model_version", "v1.0")

    ai_auto = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "LOW").count()
    human_review = db.query(RiskAssessment).filter(RiskAssessment.risk_tier.in_(["MEDIUM", "HIGH"])).count()
    ai_blocked = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "CRITICAL").count()
    alerts = db.query(RiskAssessment).filter(RiskAssessment.needs_alert == True).count()

    # --- Cost-aware analysis across the book (expected-loss engine) ---
    cost_summary = _compute_cost_summary(db)

    return {
        "total_transactions": total,
        "total_assessments": total_assessments,
        "high_risk_count": high_risk,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "total_fp_cost": round(total_fp_cost, 2),
        "total_fn_cost": round(total_fn_cost, 2),
        "total_cost": round(total_fp_cost + total_fn_cost, 2),
        "risk_distribution": {"LOW": low, "MEDIUM": medium, "HIGH": high, "CRITICAL": critical},
        "hitl_summary": {
            "ai_autopilot": ai_auto,
            "human_review": human_review,
            "ai_blocked_with_alert": ai_blocked,
            "total_alerts_raised": alerts,
            "bands": {
                "AI_AUTOPILOT": {"range": "0-25", "handled_by": "AI", "action": "ALLOW / Auto-process", "count": ai_auto},
                "HUMAN_REVIEW": {"range": "25-90", "handled_by": "Human", "action": "Manual review required", "count": human_review},
                "AI_MANAGED_BLOCK": {"range": "90-100", "handled_by": "AI + Human Alert", "action": "Auto-block/hold + alert team", "count": ai_blocked},
            },
        },
        "model_version": model_version,
        "fp_count": fp,
        "fn_count": fn,
        "tp_count": tp,
        "tn_count": tn,
        "actual_fraud": actual_fraud,
        "flagged_suspicious": flagged,
        "fp_cost_per_incident": FP_COST,
        "fn_cost_per_incident": FN_COST,
        **cost_summary,
    }


@router.get("/model-performance")
def model_performance(db: Session = Depends(get_db)):
    metrics_path = "ml/models/evaluation_metrics.json"
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            return json.load(f)
    return {"error": "Model metrics not found. Run training first."}


@router.get("/risk-trends")
def risk_trends(db: Session = Depends(get_db)):
    assessments = db.query(RiskAssessment).order_by(RiskAssessment.timestamp).all()

    daily_data = {}
    for a in assessments:
        if a.timestamp:
            day = a.timestamp.strftime("%Y-%m-%d")
            if day not in daily_data:
                daily_data[day] = {"date": day, "total": 0, "low": 0, "medium": 0, "high": 0, "critical": 0, "avg_score": 0, "scores": []}
            daily_data[day]["total"] += 1
            daily_data[day][a.risk_tier.lower()] = daily_data[day].get(a.risk_tier.lower(), 0) + 1
            daily_data[day]["scores"].append(a.final_risk_score)

    for day_data in daily_data.values():
        scores = day_data.pop("scores", [])
        day_data["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0

    trends = sorted(daily_data.values(), key=lambda x: x["date"])
    return {"trends": trends[-30:]}


@router.get("/audit-trail")
def audit_trail(transaction_id: str = None, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(AuditLog)
    if transaction_id:
        q = q.filter(AuditLog.transaction_id == transaction_id)
    logs = q.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

    return [
        {
            "log_id": l.log_id,
            "transaction_id": l.transaction_id,
            "event_type": l.event_type,
            "event_data": l.event_data,
            "model_version": l.model_version,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in logs
    ]


@router.get("/hitl-alerts")
def hitl_alerts(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get risk team alerts for 90-100 score transactions (AI blocked + alerted)."""
    alerts = db.query(AuditLog).filter(
        AuditLog.event_type == "risk_team_alert"
    ).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

    results = []
    for a in alerts:
        assessment = None
        txn = None
        if a.transaction_id:
            assessment = db.query(RiskAssessment).filter(
                RiskAssessment.transaction_id == a.transaction_id
            ).first()
            txn = db.query(Transaction).filter(
                Transaction.transaction_id == a.transaction_id
            ).first()

        results.append({
            "log_id": a.log_id,
            "transaction_id": a.transaction_id,
            "event_data": a.event_data,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "amount": txn.amount if txn else 0,
            "customer_id": txn.customer_id if txn else "unknown",
            "final_risk_score": assessment.final_risk_score if assessment else 0,
            "risk_tier": assessment.risk_tier if assessment else "UNKNOWN",
        })

    return results


@router.get("/hitl-summary")
def hitl_summary(db: Session = Depends(get_db)):
    ai_auto = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "LOW").count()
    human_review = db.query(RiskAssessment).filter(RiskAssessment.risk_tier.in_(["MEDIUM", "HIGH"])).count()
    ai_blocked = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "CRITICAL").count()
    alerts = db.query(AuditLog).filter(AuditLog.event_type == "risk_team_alert").count()
    auto_allowed = db.query(AuditLog).filter(AuditLog.event_type == "auto_allowed").count()
    sent_human = db.query(AuditLog).filter(AuditLog.event_type == "sent_for_human_review").count()
    ai_held = db.query(AuditLog).filter(AuditLog.event_type == "ai_auto_held").count()

    total = ai_auto + human_review + ai_blocked

    return {
        "total_transactions": total,
        "bands": [
            {
                "band": "AI_AUTOPILOT",
                "score_range": "0 – 25",
                "handled_by": "AI",
                "action": "Allow / auto-process",
                "emoji": "🤖",
                "count": ai_auto,
                "pct": round(ai_auto / total * 100, 1) if total else 0,
                "auto_allowed_count": auto_allowed,
            },
            {
                "band": "HUMAN_REVIEW",
                "score_range": "25 – 90",
                "handled_by": "Human",
                "action": "Send for manual review",
                "emoji": "👤",
                "count": human_review,
                "pct": round(human_review / total * 100, 1) if total else 0,
                "sent_to_human_count": sent_human,
            },
            {
                "band": "AI_MANAGED_BLOCK",
                "score_range": "90 – 100",
                "handled_by": "AI + Human Alert",
                "action": "Auto-block/hold + alert risk team",
                "emoji": "🚨",
                "count": ai_blocked,
                "pct": round(ai_blocked / total * 100, 1) if total else 0,
                "alerts_count": alerts,
                "ai_held_count": ai_held,
            },
        ],
        "total_alerts": alerts,
    }
