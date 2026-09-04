import math
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.models import Transaction, RiskAssessment, AuditLog


def _buckets(timestamps, interval_minutes):
    """Group timestamps into fixed-width time buckets keyed by floor bucket start."""
    counts = defaultdict(int)
    for ts in timestamps:
        if ts is None:
            continue
        bucket = int(ts.timestamp() // (interval_minutes * 60)) * (interval_minutes * 60)
        counts[bucket] += 1
    return counts


def _zscore_anomaly(values, current_value, std_floor=1.0, z_threshold=3.0):
    """Return (is_anomaly, z, mean, std) for current_value vs historical values."""
    if not values:
        return False, 0.0, 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    if std < std_floor:
        std = std_floor
    z = (current_value - mean) / std
    return (z >= z_threshold), z, mean, std


def detect_fraud_spikes(db: Session, window_minutes=60, baseline_hours=168, z_threshold=3.0, min_volume=5):
    """Detect system-wide spikes in suspicious/fraud transaction volume.

    Compares the current sliding window (default 60 min) against the recent
    baseline (default 7 days) using a Z-score on suspicious transaction counts.
    Returns a list of detected spikes, oldest baseline removed and any new
    spikes written as risk_team_alert audit events for dedup.
    """
    # Anchor the analysis to the most recent assessment in the DB so the spike
    # detector yields meaningful results over whatever data window is loaded
    # (e.g. seeded historical data) rather than only wall-clock "now".
    latest = db.query(RiskAssessment).order_by(
        RiskAssessment.timestamp.desc()
    ).first()
    anchor = latest.timestamp if latest and latest.timestamp else datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)

    now = anchor
    window_start = now - timedelta(minutes=window_minutes)
    baseline_start = now - timedelta(hours=baseline_hours)

    # SQLite stores naive UTC datetimes; use a naive cutoff for the SQL filter
    # to avoid aware-vs-naive comparison issues, then normalize in Python.
    naive_cutoff = baseline_start.replace(tzinfo=None)

    assessments = db.query(RiskAssessment).filter(
        RiskAssessment.timestamp >= naive_cutoff
    ).all()

    baseline_counts = defaultdict(int)   # bucket -> suspicious count (excluding current window handled below)
    current_window_suspicious = []

    for a in assessments:
        if a.timestamp is None:
            continue
        ts = a.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        suspicious = (a.ml_prediction == "suspicious") or (a.final_risk_score >= 50)
        bucket = int(ts.timestamp() // (window_minutes * 60))
        if ts >= window_start:
            current_window_suspicious.append(suspicious)
        else:
            baseline_counts[bucket] += 1 if suspicious else 0

    current_count = sum(1 for s in current_window_suspicious if s)

    # Build historical series of per-window suspicious counts from baseline buckets
    history = list(baseline_counts.values())

    is_spike, z, mean, std = _zscore_anomaly(
        history, current_count, std_floor=1.0, z_threshold=z_threshold
    )
    is_spike = is_spike and current_count >= min_volume

    total_window = len(current_window_suspicious)
    suspicious_rate = (current_count / total_window * 100) if total_window else 0.0

    return {
        "window_minutes": window_minutes,
        "baseline_hours": baseline_hours,
        "current_window_suspicious": current_count,
        "current_window_total": total_window,
        "current_suspicious_rate_pct": round(suspicious_rate, 2),
        "historical_avg_suspicious_per_window": round(mean, 2) if history else 0,
        "historical_std": round(std, 2) if history else 0,
        "z_score": round(z, 2) if history else 0,
        "is_spike": bool(is_spike),
        "z_threshold": z_threshold,
        "min_volume": min_volume,
    }


def persist_spike_alert(db: Session, spike: dict):
    """Write a risk_team_alert audit event for an ongoing spike. Includes a
    spike_window_key for idempotency (dedup repeated scans of the same window)."""
    now = datetime.now(timezone.utc)
    window_key = int(now.timestamp() // (spike["window_minutes"] * 60))

    existing = db.query(AuditLog).filter(
        AuditLog.event_type == "fraud_spike_alert"
    ).all()
    for a in existing:
        if a.event_data and a.event_data.get("spike_window_key") == window_key:
            return False

    db.add(AuditLog(
        transaction_id=None,
        event_type="fraud_spike_alert",
        event_data={
            "spike_window_key": window_key,
            "severity": "CRITICAL",
            "window_minutes": spike["window_minutes"],
            "current_window_suspicious": spike["current_window_suspicious"],
            "current_window_total": spike["current_window_total"],
            "current_suspicious_rate_pct": spike["current_suspicious_rate_pct"],
            "z_score": spike["z_score"],
            "historical_avg_suspicious_per_window": spike["historical_avg_suspicious_per_window"],
            "alert_message": (
                f"FRAUD SPIKE ALERT: {spike['current_window_suspicious']} suspicious transactions "
                f"({spike['current_suspicious_rate_pct']}%) in the last {spike['window_minutes']} min, "
                f"Z-score {spike['z_score']} vs historical avg {spike['historical_avg_suspicious_per_window']}."
            ),
        },
        model_version="spike-detector-v1",
    ))
    db.commit()

    try:
        from app.services.notifications import create_alert
        create_alert(
            db,
            alert_type="FRAUD_SPIKE",
            transaction_id=None,
            severity="CRITICAL",
            source="spike_detector",
            title=f"Fraud spike detected: {spike['current_window_suspicious']} suspicious in {spike['window_minutes']}m",
            message=(
                f"FRAUD SPIKE ALERT: {spike['current_window_suspicious']} suspicious transactions "
                f"({spike['current_suspicious_rate_pct']}%) in the last {spike['window_minutes']} min, "
                f"Z-score {spike['z_score']} vs historical avg {spike['historical_avg_suspicious_per_window']}."
            ),
            metadata={
                "window_minutes": spike["window_minutes"],
                "current_window_suspicious": spike["current_window_suspicious"],
                "z_score": spike["z_score"],
                "window_key": window_key,
            },
        )
    except Exception as e:
        print(f"Spike alert creation failed: {e}")

    return True


def get_spike_history(db: Session, limit=50):
    alerts = db.query(AuditLog).filter(
        AuditLog.event_type == "fraud_spike_alert"
    ).order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return [
        {
            "log_id": a.log_id,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            **a.event_data,
        }
        for a in alerts
    ]


def build_spike_timeseries(db: Session, interval_minutes=60, hours=168):
    """Return an hourly time series of total & suspicious transaction counts
    for the Overview charts."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)

    assessments = db.query(RiskAssessment).filter(
        RiskAssessment.timestamp >= start
    ).all()

    series = defaultdict(lambda: {"total": 0, "suspicious": 0})
    for a in assessments:
        if a.timestamp is None:
            continue
        bucket = int(a.timestamp.timestamp() // (interval_minutes * 60)) * (interval_minutes * 60)
        series[bucket]["total"] += 1
        if (a.ml_prediction == "suspicious") or (a.final_risk_score >= 50):
            series[bucket]["suspicious"] += 1

    points = []
    for bucket in sorted(series.keys()):
        points.append({
            "time": datetime.fromtimestamp(bucket, tz=timezone.utc).isoformat(),
            "total": series[bucket]["total"],
            "suspicious": series[bucket]["suspicious"],
        })
    return points
