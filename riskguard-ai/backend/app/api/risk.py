from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models.database import get_db
from app.models.models import RiskAssessment, Transaction
from app.schemas.schemas import RiskScoreRequest
from app.services.cost_decision import cost_decision_dict

router = APIRouter()


def _cost_for(amount: float, risk_score: float) -> dict:
    return cost_decision_dict(amount or 0, risk_score or 0)


@router.get("/scores")
def list_risk_scores(skip: int = 0, limit: int = 50, tier: str = None, db: Session = Depends(get_db)):
    q = db.query(RiskAssessment)
    if tier:
        q = q.filter(RiskAssessment.risk_tier == tier.upper())
    assessments = q.order_by(RiskAssessment.final_risk_score.desc()).offset(skip).limit(limit).all()

    results = []
    for a in assessments:
        txn = db.query(Transaction).filter(Transaction.transaction_id == a.transaction_id).first()
        results.append({
            "assessment_id": a.assessment_id,
            "transaction_id": a.transaction_id,
            "customer_id": txn.customer_id if txn else "unknown",
            "amount": txn.amount if txn else 0,
            "ml_risk_score": a.ml_risk_score,
            "behavioral_deviation_score": a.behavioral_deviation_score,
            "final_risk_score": a.final_risk_score,
            "risk_tier": a.risk_tier,
            "recommended_action": a.recommended_action,
            "handling_user": a.handling_user,
            "hitl_band": a.hitl_band,
            "needs_alert": a.needs_alert,
            "ml_prediction": a.ml_prediction,
            "model_version": a.model_version,
            "cost_decision": (a.feature_contributions or {}).get("cost_decision") or _cost_for(txn.amount if txn else 0, a.final_risk_score),
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        })

    return results


@router.get("/distribution")
def risk_distribution(db: Session = Depends(get_db)):
    total = db.query(RiskAssessment).count()
    low = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "LOW").count()
    medium = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "MEDIUM").count()
    high = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "HIGH").count()
    critical = db.query(RiskAssessment).filter(RiskAssessment.risk_tier == "CRITICAL").count()

    return {
        "total": total,
        "LOW": low,
        "MEDIUM": medium,
        "HIGH": high,
        "CRITICAL": critical,
    }
