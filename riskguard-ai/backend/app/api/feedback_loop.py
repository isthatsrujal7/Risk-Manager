from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.feedback_loop import retrain_candidate_from_feedback, approve_candidate, get_feedback_loop_status

router = APIRouter()


class ApproveRequest(BaseModel):
    version: str


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return get_feedback_loop_status(db)


@router.post("/retrain")
def retrain(db: Session = Depends(get_db)):
    """Stage a candidate model from synthetic data + human-labeled feedback.

    The active model is NOT replaced. A new candidate is trained, versioned,
    and recorded with status "candidate"; an operator must approve it.
    """
    try:
        report = retrain_candidate_from_feedback(db)
        return {"status": "ok", **report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")


@router.post("/approve")
def approve(req: ApproveRequest, db: Session = Depends(get_db)):
    """Promote an approved candidate to the active model (explicit operator gate)."""
    result = approve_candidate(req.version)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Candidate not found"))
    return result