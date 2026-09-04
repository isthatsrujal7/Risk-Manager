from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from collections import Counter

from app.models.database import get_db
from app.models.models import Transaction, FraudPatternTrack, Customer, AuditLog
from app.risk.fraud_patterns import FraudPatternDetector, FraudPatternType, PATTERN_DESCRIPTIONS
from app.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/templates")
def get_pattern_templates():
    return {
        k.value: {
            "name": v["name"],
            "description": v["description"],
            "severity": v["severity"],
            "example": v["example"],
            "detection_signals": v["detection_signals"],
            "business_impact": v["business_impact"],
        }
        for k, v in PATTERN_DESCRIPTIONS.items()
    }


@router.get("/detect/{transaction_id}")
def detect_patterns(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn_data = _build_txn_data(txn)
    customer_history = _get_customer_history(txn.customer_id, db)
    recent = _get_recent_transactions(txn.customer_id, db, include_current=txn)

    detector = FraudPatternDetector()
    results = detector.detect_all_patterns(txn_data, customer_history, recent)

    for result in results:
        _save_pattern(db, txn, result)

    return {
        "transaction_id": transaction_id,
        "patterns_detected": len(results),
        "patterns": [
            {
                "type": r.pattern_type.value,
                "name": PATTERN_DESCRIPTIONS[r.pattern_type]["name"],
                "confidence": round(r.confidence, 2),
                "severity": r.severity,
                "signals": r.signals,
                "explanation": r.explanation,
                "is_merchant_risk": r.is_merchant_risk,
                "is_customer_risk": r.is_customer_risk,
                "recommended_action": r.recommended_action,
            }
            for r in results
        ],
    }


@router.get("/transaction/{transaction_id}")
def get_patterns_for_transaction(transaction_id: str, db: Session = Depends(get_db)):
    patterns = db.query(FraudPatternTrack).filter(
        FraudPatternTrack.transaction_id == transaction_id
    ).all()

    return [
        {
            "pattern_id": p.pattern_id,
            "transaction_id": p.transaction_id,
            "customer_id": p.customer_id,
            "pattern_type": p.pattern_type,
            "pattern_name": p.pattern_name,
            "confidence": p.confidence,
            "severity": p.severity,
            "signals": p.signals,
            "explanation": p.explanation,
            "is_merchant_risk": p.is_merchant_risk,
            "is_customer_risk": p.is_customer_risk,
            "recommended_action": p.recommended_action,
            "detected_at": p.detected_at.isoformat() if p.detected_at else None,
        }
        for p in patterns
    ]


@router.get("/summary")
def get_pattern_summary(db: Session = Depends(get_db)):
    patterns = db.query(FraudPatternTrack).all()

    by_type = Counter()
    by_severity = Counter()
    for p in patterns:
        by_type[p.pattern_type] += 1
        by_severity[p.severity] += 1

    merchant_risk = sum(1 for p in patterns if p.is_merchant_risk)
    customer_risk = sum(1 for p in patterns if p.is_customer_risk)

    return {
        "total_patterns": len(patterns),
        "patterns_by_type": dict(by_type),
        "patterns_by_severity": dict(by_severity),
        "merchant_risk_count": merchant_risk,
        "customer_risk_count": customer_risk,
        "templates": {
            k.value: {"name": v["name"], "severity": v["severity"], "description": v["description"]}
            for k, v in PATTERN_DESCRIPTIONS.items()
        },
    }


@router.get("/transaction/{transaction_id}/classify")
def classify_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    detector = FraudPatternDetector()
    txn_data = _build_txn_data(txn)
    history = _get_customer_history(txn.customer_id, db)
    recent = _get_recent_transactions(txn.customer_id, db, include_current=txn)

    results = detector.detect_all_patterns(txn_data, history, recent)

    if not results:
        return {
            "transaction_id": transaction_id,
            "classification": "NORMAL",
            "severity": "LOW",
            "is_merchant_risk": False,
            "is_customer_risk": False,
            "recommended_action": "ALLOW",
            "patterns": [],
            "summary": "No fraud behavior patterns detected. Transaction appears within normal behavior.",
        }

    highest = max(results, key=lambda r: r.confidence)

    return {
        "transaction_id": transaction_id,
        "classification": PATTERN_DESCRIPTIONS[highest.pattern_type]["name"],
        "severity": highest.severity,
        "is_merchant_risk": highest.is_merchant_risk,
        "is_customer_risk": highest.is_customer_risk,
        "recommended_action": highest.recommended_action,
        "patterns": [
            {
                "type": r.pattern_type.value,
                "name": PATTERN_DESCRIPTIONS[r.pattern_type]["name"],
                "confidence": round(r.confidence, 2),
                "severity": r.severity,
            }
            for r in results
        ],
        "summary": highest.explanation,
    }


def _build_txn_data(txn: Transaction) -> dict:
    return {
        "transaction_id": txn.transaction_id,
        "customer_id": txn.customer_id,
        "amount": txn.amount,
        "payment_method": txn.payment_method,
        "merchant_category": txn.merchant_category,
        "merchant_name": txn.merchant_name,
        "merchant_id": txn.merchant_id,
        "device_id": txn.device_id,
        "location_city": txn.location_city,
        "location_country": txn.location_country,
        "timestamp": txn.timestamp,
        "payment_status": txn.payment_status,
        "settlement_status": txn.settlement_status,
        "display_status": txn.display_status,
        "actual_status": txn.actual_status,
        "bank_callback_status": txn.bank_callback_status,
        "gateway_status": txn.gateway_status,
        "bank_ref_number": txn.bank_ref_number,
        "reversal_count": txn.reversal_count,
        "is_fraud": txn.is_fraud,
    }


def _get_customer_history(customer_id: str, db: Session) -> list:
    txns = db.query(Transaction).filter(
        Transaction.customer_id == customer_id
    ).order_by(Transaction.timestamp.desc()).limit(50).all()

    history = []
    for t in txns:
        entry = {
            "device_id": t.device_id,
            "location_city": t.location_city,
            "amount": t.amount,
            "avg_amount": t.amount,
            "timestamp": t.timestamp,
            "has_refund": t.reversal_count > 0 if t.reversal_count else False,
            "merchant_name": t.merchant_name,
            "payment_method": t.payment_method,
        }
        history.append(entry)

    if history:
        avg = sum(h["amount"] for h in history) / len(history)
        for h in history:
            h["avg_amount"] = avg

    return history


def _get_recent_transactions(customer_id: str, db: Session, include_current=None) -> list:
    txns = db.query(Transaction).filter(
        Transaction.customer_id == customer_id
    ).order_by(Transaction.timestamp.desc()).limit(30).all()

    recent = []
    for t in txns:
        if include_current and t.transaction_id == include_current.transaction_id:
            continue
        recent.append({
            "transaction_id": t.transaction_id,
            "customer_id": t.customer_id,
            "amount": t.amount,
            "payment_method": t.payment_method,
            "merchant_name": t.merchant_name,
            "merchant_id": t.merchant_id,
            "settlement_status": t.settlement_status,
            "device_id": t.device_id,
            "location_city": t.location_city,
            "timestamp": t.timestamp,
        })

    return recent


def _save_pattern(db: Session, txn: Transaction, result):
    pattern = FraudPatternTrack(
        transaction_id=txn.transaction_id,
        customer_id=txn.customer_id,
        pattern_type=result.pattern_type.value,
        pattern_name=PATTERN_DESCRIPTIONS[result.pattern_type]["name"],
        confidence=result.confidence,
        severity=result.severity,
        signals=result.signals,
        explanation=result.explanation,
        is_merchant_risk=result.is_merchant_risk,
        is_customer_risk=result.is_customer_risk,
        recommended_action=result.recommended_action,
    )
    db.add(pattern)

    audit = AuditLog(
        transaction_id=txn.transaction_id,
        event_type="fraud_pattern_detected",
        event_data={
            "pattern_type": result.pattern_type.value,
            "pattern_name": PATTERN_DESCRIPTIONS[result.pattern_type]["name"],
            "confidence": result.confidence,
            "severity": result.severity,
        },
    )
    db.add(audit)
    db.commit()
