import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import RiskAssessment, Transaction
from app.services.live_feed import subscribe, unsubscribe, broadcast, client_count

router = APIRouter()


@router.get("/events")
async def live_events(request: Request):
    """Server-Sent Events stream of real-time transaction/risk activity."""
    async def event_generator():
        q = subscribe()
        try:
            # Initial "connected" heartbeat
            yield f"data: {json.dumps({'type': 'connected', 'client_count': client_count()})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield payload
                except asyncio.TimeoutError:
                    # keep-alive comment to prevent proxy timeouts
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/recent")
def recent_events(limit: int = 20, db: Session = Depends(get_db)):
    """Recent events to hydrate the monitor page on load."""
    assessments = db.query(RiskAssessment).order_by(
        RiskAssessment.timestamp.desc()
    ).limit(limit).all()

    events = []
    for a in assessments:
        txn = db.query(Transaction).filter(
            Transaction.transaction_id == a.transaction_id
        ).first()
        events.append({
            "type": "new_assessment",
            "data": {
                "transaction_id": a.transaction_id,
                "customer_id": txn.customer_id if txn else "unknown",
                "amount": txn.amount if txn else 0,
                "final_risk_score": a.final_risk_score,
                "risk_tier": a.risk_tier,
                "recommended_action": a.recommended_action,
                "hitl_band": a.hitl_band,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            },
        })
    return events


@router.get("/stats")
def stream_stats():
    return {"connected_clients": client_count()}
