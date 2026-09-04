from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.risk.spike_detection import (
    detect_fraud_spikes,
    persist_spike_alert,
    get_spike_history,
    build_spike_timeseries,
)
from app.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/detect")
def detect_spike(
    window_minutes: int = Query(60, ge=5, le=1440),
    baseline_hours: int = Query(168, ge=24, le=720),
    z_threshold: float = Query(3.0, ge=1.0, le=10.0),
    min_volume: int = Query(5, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Detect a system-wide fraud/suspicious transaction spike and (if present)
    persist a deduplicated risk_team_alert audit event."""
    spike = detect_fraud_spikes(
        db,
        window_minutes=window_minutes,
        baseline_hours=baseline_hours,
        z_threshold=z_threshold,
        min_volume=min_volume,
    )
    new_alert = False
    if spike["is_spike"]:
        new_alert = persist_spike_alert(db, spike)
    spike["new_alert_created"] = new_alert
    return spike


@router.get("/history")
def spike_history(limit: int = 50, db: Session = Depends(get_db)):
    return get_spike_history(db, limit=limit)


@router.get("/timeseries")
def spike_timeseries(
    interval_minutes: int = Query(60, ge=15, le=720),
    hours: int = Query(168, ge=24, le=720),
    db: Session = Depends(get_db),
):
    return build_spike_timeseries(db, interval_minutes=interval_minutes, hours=hours)
