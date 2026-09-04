from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.feedback_loop import retrain_from_feedback, get_feedback_loop_status

router = APIRouter()


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return get_feedback_loop_status(db)


@router.post("/retrain")
def retrain(db: Session = Depends(get_db)):
    try:
        report = retrain_from_feedback(db)
        return {"status": "ok", **report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")
