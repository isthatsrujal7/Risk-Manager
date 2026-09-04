from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models.database import get_db
from app.models.models import Investigation, Transaction, RiskAssessment, Review
from app.agents.investigation_agent import InvestigationAgent

router = APIRouter()


@router.get("/")
def list_investigations(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    invs = db.query(Investigation).order_by(Investigation.timestamp.desc()).offset(skip).limit(limit).all()

    results = []
    for inv in invs:
        txn = db.query(Transaction).filter(Transaction.transaction_id == inv.transaction_id).first()
        review = db.query(Review).filter(Review.investigation_id == inv.investigation_id).first()
        assessment = db.query(RiskAssessment).filter(RiskAssessment.transaction_id == inv.transaction_id).first()
        results.append({
            "investigation_id": inv.investigation_id,
            "transaction_id": inv.transaction_id,
            "customer_id": inv.customer_id,
            "summary": inv.summary,
            "recommended_action": inv.recommended_action,
            "risk_tier": assessment.risk_tier if assessment else "UNKNOWN",
            "amount": txn.amount if txn else 0,
            "has_review": review is not None,
            "human_decision": review.human_decision if review else None,
            "timestamp": inv.timestamp.isoformat() if inv.timestamp else None,
        })

    return results


@router.get("/{investigation_id}")
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    txn = db.query(Transaction).filter(Transaction.transaction_id == inv.transaction_id).first()
    assessment = db.query(RiskAssessment).filter(RiskAssessment.transaction_id == inv.transaction_id).first()
    review = db.query(Review).filter(Review.investigation_id == inv.investigation_id).first()

    return {
        "investigation_id": inv.investigation_id,
        "transaction_id": inv.transaction_id,
        "customer_id": inv.customer_id,
        "risk_assessment_id": inv.risk_assessment_id,
        "summary": inv.summary,
        "evidence": inv.evidence,
        "contributing_factors": inv.contributing_factors,
        "behavioral_anomalies": inv.behavioral_anomalies,
        "related_activity": inv.related_activity,
        "uncertainty": inv.uncertainty,
        "recommended_action": inv.recommended_action,
        "explanation": inv.explanation,
        "agent_model_used": inv.agent_model_used,
        "is_llm_generated": inv.is_llm_generated,
        "timestamp": inv.timestamp.isoformat() if inv.timestamp else None,
        "transaction": {
            "transaction_id": txn.transaction_id if txn else None,
            "amount": txn.amount if txn else 0,
            "customer_id": txn.customer_id if txn else None,
            "payment_method": txn.payment_method if txn else None,
            "merchant_category": txn.merchant_category if txn else None,
            "merchant_name": txn.merchant_name if txn else None,
            "device_id": txn.device_id if txn else None,
            "location_city": txn.location_city if txn else None,
            "location_country": txn.location_country if txn else None,
            "timestamp": txn.timestamp.isoformat() if txn and txn.timestamp else None,
        } if txn else None,
        "risk_assessment": {
            "final_risk_score": assessment.final_risk_score if assessment else 0,
            "behavioral_deviation_score": assessment.behavioral_deviation_score if assessment else 0,
            "ml_risk_score": assessment.ml_risk_score if assessment else 0,
            "risk_tier": assessment.risk_tier if assessment else "UNKNOWN",
            "handling_user": assessment.handling_user if assessment else "AI",
            "hitl_band": assessment.hitl_band if assessment else "AI_AUTOPILOT",
            "needs_alert": assessment.needs_alert if assessment else False,
            "top_signals": assessment.top_signals if assessment else [],
        } if assessment else None,
        "review": {
            "review_id": review.review_id if review else None,
            "human_decision": review.human_decision if review else None,
            "reviewer_note": review.reviewer_note if review else None,
            "ai_recommendation": review.ai_recommendation if review else None,
        } if review else None,
    }


@router.post("/{transaction_id}/investigate")
def run_investigation(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    existing = db.query(Investigation).filter(Investigation.transaction_id == transaction_id).first()
    if existing:
        return {"investigation_id": existing.investigation_id, "status": "already_exists"}

    agent = InvestigationAgent(db)
    report = agent.investigate(transaction_id)

    assessment = db.query(RiskAssessment).filter(RiskAssessment.transaction_id == transaction_id).first()

    investigation = Investigation(
        transaction_id=transaction_id,
        customer_id=txn.customer_id,
        risk_assessment_id=assessment.assessment_id if assessment else None,
        summary=report.get("summary", ""),
        evidence=report.get("evidence", []),
        contributing_factors=report.get("contributing_factors", []),
        behavioral_anomalies=report.get("behavioral_anomalies", []),
        related_activity=report.get("related_activity", []),
        uncertainty=report.get("uncertainty", ""),
        recommended_action=report.get("recommended_action", "REVIEW"),
        explanation=report.get("explanation", ""),
        agent_model_used=report.get("agent_model_used", "deterministic"),
        is_llm_generated=report.get("is_llm_generated", False),
    )
    db.add(investigation)

    from app.models.models import AuditLog
    audit = AuditLog(
        transaction_id=transaction_id,
        event_type="investigation_created",
        event_data={"investigation_id": investigation.investigation_id, "agent": investigation.agent_model_used},
    )
    db.add(audit)
    db.commit()
    db.refresh(investigation)

    return {
        "investigation_id": investigation.investigation_id,
        "status": "created",
        "report": {
            "summary": investigation.summary,
            "recommended_action": investigation.recommended_action,
            "is_llm_generated": investigation.is_llm_generated,
        },
    }
