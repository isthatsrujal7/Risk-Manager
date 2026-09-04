from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.models.database import get_db
from app.models.models import Review, Investigation, Transaction, AuditLog, User
from app.schemas.schemas import ReviewCreate
from app.auth import get_current_user, require_roles

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/")
def list_reviews(skip: int = 0, limit: int = 50, status: str = None, db: Session = Depends(get_db)):
    q = db.query(Review)
    if status == "pending":
        q = q.filter(Review.human_decision.is_(None))
    elif status == "decided":
        q = q.filter(Review.human_decision.isnot(None))

    reviews = q.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for r in reviews:
        inv = db.query(Investigation).filter(Investigation.investigation_id == r.investigation_id).first()
        txn = db.query(Transaction).filter(Transaction.transaction_id == r.transaction_id).first()
        results.append({
            "review_id": r.review_id,
            "investigation_id": r.investigation_id,
            "transaction_id": r.transaction_id,
            "amount": txn.amount if txn else 0,
            "customer_id": txn.customer_id if txn else "unknown",
            "ai_recommendation": r.ai_recommendation,
            "human_decision": r.human_decision,
            "reviewer_note": r.reviewer_note,
            "reviewer_name": r.reviewer_name,
            "outcome": r.outcome,
            "summary": inv.summary if inv else "",
            "recommended_action": inv.recommended_action if inv else "",
            "timestamp": r.created_at.isoformat() if r.created_at else None,
            "decision_timestamp": r.decision_timestamp.isoformat() if r.decision_timestamp else None,
        })

    return results


@router.get("/pending-count")
def pending_review_count(db: Session = Depends(get_db)):
    count = db.query(Review).filter(Review.human_decision.is_(None)).count()
    return {"pending_count": count}


@router.post("/")
def submit_review(review: ReviewCreate, user: User = Depends(require_roles("analyst", "admin")), db: Session = Depends(get_db)):
    db_review = db.query(Review).filter(Review.investigation_id == review.investigation_id).first()
    if not db_review:
        raise HTTPException(status_code=404, detail="Review not found for this investigation")

    inv = db.query(Investigation).filter(Investigation.investigation_id == review.investigation_id).first()
    txn = db.query(Transaction).filter(Transaction.transaction_id == review.transaction_id).first()
    reviewer_name = review.reviewer_name or (user.display_name or user.username)

    db_review.human_decision = review.human_decision
    db_review.reviewer_note = review.reviewer_note
    db_review.reviewer_name = reviewer_name
    db_review.decision_timestamp = datetime.now(timezone.utc)

    if txn and txn.is_fraud and review.human_decision == "APPROVED":
        db_review.is_false_negative = True
    elif txn and not txn.is_fraud and review.human_decision == "REJECTED":
        db_review.is_false_positive = True

    audit = AuditLog(
        transaction_id=review.transaction_id,
        event_type="review_decision",
        event_data={
            "investigation_id": review.investigation_id,
            "ai_recommendation": db_review.ai_recommendation,
            "human_decision": review.human_decision,
            "reviewer": reviewer_name,
            "note": review.reviewer_note,
            "is_false_positive": db_review.is_false_positive,
            "is_false_negative": db_review.is_false_negative,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(db_review)

    return {
        "review_id": db_review.review_id,
        "status": "recorded",
        "human_decision": db_review.human_decision,
        "is_false_positive": db_review.is_false_positive,
        "is_false_negative": db_review.is_false_negative,
    }
