from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import Alert, User
from app.services.notifications import create_alert, ack_alert
from app.auth import get_current_user, require_roles

router = APIRouter(dependencies=[Depends(get_current_user)])


class AcknowledgeRequest(BaseModel):
    status: Optional[str] = "ACKNOWLEDGED"
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None


@router.get("/")
def list_alerts(
    status: str = None,
    severity: str = None,
    source: str = None,
    limit: int = Query(100, ge=1, le=500),
    skip: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status.upper())
    if severity:
        q = q.filter(Alert.severity == severity.upper())
    if source:
        q = q.filter(Alert.source == source)
    alerts = q.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize(a) for a in alerts]


@router.get("/summary")
def alert_summary(db: Session = Depends(get_db)):
    total = db.query(Alert).count()
    open = db.query(Alert).filter(Alert.status == "OPEN").count()
    ack = db.query(Alert).filter(Alert.status == "ACKNOWLEDGED").count()
    resolved = db.query(Alert).filter(Alert.status == "RESOLVED").count()
    by_severity = {}
    for s in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        by_severity[s] = db.query(Alert).filter(Alert.severity == s).count()
    return {
        "total": total,
        "open": open,
        "acknowledged": ack,
        "resolved": resolved,
        "by_severity": by_severity,
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge(alert_id: str, body: AcknowledgeRequest, user: User = Depends(require_roles("analyst", "admin")), db: Session = Depends(get_db)):
    alert = ack_alert(db, alert_id, body.status or "ACKNOWLEDGED", body.assigned_to, body.resolution_note)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize(alert)


@router.post("/{alert_id}/resolve")
def resolve(alert_id: str, body: AcknowledgeRequest, user: User = Depends(require_roles("analyst", "admin")), db: Session = Depends(get_db)):
    alert = ack_alert(db, alert_id, "RESOLVED", body.assigned_to, body.resolution_note)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize(alert)


@router.get("/{alert_id}")
def alert_detail(alert_id: str, db: Session = Depends(get_db)):
    a = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize(a)


def _serialize(a: Alert) -> dict:
    return {
        "alert_id": a.alert_id,
        "alert_type": a.alert_type,
        "transaction_id": a.transaction_id,
        "severity": a.severity,
        "source": a.source,
        "title": a.title,
        "message": a.message,
        "metadata": a.metadata_json,
        "status": a.status,
        "assigned_to": a.assigned_to,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "resolution_note": a.resolution_note,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
