import os
import json
import logging
from urllib import request

from sqlalchemy.orm import Session

from app.models.models import Alert

logger = logging.getLogger("alerts")
logging.basicConfig(level=logging.INFO)

ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").strip()
ALERT_SLACK_WEBHOOK = os.getenv("ALERT_SLACK_WEBHOOK", "").strip()


def create_alert(
    db: Session,
    *,
    alert_type="RISK_ALERT",
    transaction_id=None,
    severity="CRITICAL",
    source="hitl",
    title="",
    message="",
    metadata=None,
):
    """Persist an Alert row and dispatch external notifications. Returns the Alert."""
    alert = Alert(
        alert_type=alert_type,
        transaction_id=transaction_id,
        severity=severity,
        source=source,
        title=title,
        message=message,
        metadata_json=metadata or {},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    dispatch_notifications(alert)
    return alert


def dispatch_notifications(alert: Alert):
    """Send external notifications. No external URL is configured by default, so
    this logs a placeholder that can be wired to email/Slack/webhook via env vars."""
    payload = {
        "alert_id": alert.alert_id,
        "title": alert.title,
        "message": alert.message,
        "severity": alert.severity,
        "source": alert.source,
        "transaction_id": alert.transaction_id,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }

    if ALERT_WEBHOOK_URL:
        _post_json(ALERT_WEBHOOK_URL, payload, timeout=5)

    if ALERT_SLACK_WEBHOOK:
        _post_json(ALERT_SLACK_WEBHOOK, {"text": f"*{alert.title}*: {alert.message}"}, timeout=5)

    if ALERT_EMAIL_TO:
        logger.info("[EMAIL] To=%s Subject=%s Body=%s", ALERT_EMAIL_TO, alert.title, alert.message)
    else:
        logger.info(
            "[NOTIFICATION] Delivered alert %s (%s): %s. Configure ALERT_WEBHOOK_URL / ALERT_SLACK_WEBHOOK / ALERT_EMAIL_TO to enable external delivery.",
            alert.alert_id, alert.severity, alert.message,
        )


def _post_json(url: str, payload: dict, timeout=5):
    try:
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except Exception as e:
        logger.warning("Webhook delivery failed: %s", e)
        return None


def ack_alert(db: Session, alert_id: str, status="ACKNOWLEDGED", assigned_to=None, resolution_note=""):
    from datetime import datetime, timezone
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        return None
    alert.status = status
    if assigned_to:
        alert.assigned_to = assigned_to
    if resolution_note:
        alert.resolution_note = resolution_note
    if status == "ACKNOWLEDGED" and not alert.acknowledged_at:
        alert.acknowledged_at = datetime.now(timezone.utc)
    elif status == "RESOLVED":
        alert.resolved_at = datetime.now(timezone.utc)
        if not alert.acknowledged_at:
            alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert
