from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import uuid

from app.models.database import get_db
from app.models.models import Transaction, RiskAssessment
from app.schemas.schemas import TransactionCreate, TransactionResponse, RiskAssessmentResponse, RiskScoreRequest
from app.services.risk_scoring import RiskScoringService
from app.services.cost_decision import cost_decision_dict

router = APIRouter()


@router.get("/", response_model=List[TransactionResponse])
def list_transactions(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    txns = db.query(Transaction).order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
    return txns


@router.get("/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    assessment = db.query(RiskAssessment).filter(RiskAssessment.transaction_id == transaction_id).first()

    return {
        "transaction": {
            "transaction_id": txn.transaction_id,
            "customer_id": txn.customer_id,
            "amount": txn.amount,
            "currency": txn.currency,
            "payment_method": txn.payment_method,
            "merchant_category": txn.merchant_category,
            "merchant_name": txn.merchant_name,
            "device_id": txn.device_id,
            "ip_address": txn.ip_address,
            "location_city": txn.location_city,
            "location_country": txn.location_country,
            "timestamp": txn.timestamp.isoformat() if txn.timestamp else None,
            "is_fraud": txn.is_fraud,
        },
        "risk_assessment": {
            "assessment_id": assessment.assessment_id,
            "ml_risk_score": assessment.ml_risk_score,
            "ml_prediction": assessment.ml_prediction,
            "ml_confidence": assessment.ml_confidence,
            "behavioral_deviation_score": assessment.behavioral_deviation_score,
            "final_risk_score": assessment.final_risk_score,
            "risk_tier": assessment.risk_tier,
            "recommended_action": assessment.recommended_action,
            "handling_user": assessment.handling_user,
            "hitl_band": assessment.hitl_band,
            "needs_alert": assessment.needs_alert,
            "top_signals": assessment.top_signals,
            "feature_contributions": assessment.feature_contributions,
            "cost_decision": (assessment.feature_contributions or {}).get("cost_decision", {}),
            "model_version": assessment.model_version,
        } if assessment else None,
    }


@router.post("/")
def create_transaction(txn: TransactionCreate, db: Session = Depends(get_db)):
    txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    db_txn = Transaction(
        transaction_id=txn_id,
        customer_id=txn.customer_id,
        amount=txn.amount,
        currency=txn.currency,
        payment_method=txn.payment_method,
        merchant_category=txn.merchant_category,
        merchant_name=txn.merchant_name,
        device_id=txn.device_id,
        ip_address=txn.ip_address,
        location_city=txn.location_city,
        location_country=txn.location_country,
        timestamp=txn.timestamp or datetime.now(timezone.utc),
        # Ground-truth labels are never accepted from live ingestion; the label
        # is assigned later by investigation (human decision) or batch analysis.
        is_fraud=False,
    )
    db.add(db_txn)
    db.commit()
    db.refresh(db_txn)

    service = RiskScoringService(db)
    assessment = service.score_transaction(db_txn)

    return {
        "transaction_id": txn_id,
        "risk_assessment": {
            "final_risk_score": assessment.final_risk_score,
            "risk_tier": assessment.risk_tier,
            "recommended_action": assessment.recommended_action,
            "ml_risk_score": assessment.ml_risk_score,
            "behavioral_deviation_score": assessment.behavioral_deviation_score,
        },
    }


@router.post("/{transaction_id}/score")
def score_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    service = RiskScoringService(db)
    assessment = service.score_transaction(txn)

    return {
        "assessment_id": assessment.assessment_id,
        "final_risk_score": assessment.final_risk_score,
        "risk_tier": assessment.risk_tier,
        "recommended_action": assessment.recommended_action,
    }
