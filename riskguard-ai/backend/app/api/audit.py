from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import AuditLog

router = APIRouter()


@router.get("/")
def list_audit_logs(skip: int = 0, limit: int = 100, transaction_id: str = None, event_type: str = None, db: Session = Depends(get_db)):
    q = db.query(AuditLog)
    if transaction_id:
        q = q.filter(AuditLog.transaction_id == transaction_id)
    if event_type:
        q = q.filter(AuditLog.event_type == event_type)

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


@router.get("/{transaction_id}")
def get_audit_for_transaction(transaction_id: str, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(
        AuditLog.transaction_id == transaction_id
    ).order_by(AuditLog.timestamp.asc()).all()

    return [
        {
            "log_id": l.log_id,
            "event_type": l.event_type,
            "event_data": l.event_data,
            "model_version": l.model_version,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in logs
    ]
