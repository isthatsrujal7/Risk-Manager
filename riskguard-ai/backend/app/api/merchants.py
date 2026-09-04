from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import User
from app.services.merchant_risk import (
    compute_merchant_profiles,
    list_merchant_profiles,
    get_merchant_profile,
)
from app.auth import get_current_user, require_roles

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/rebuild")
def rebuild_profiles(user: User = Depends(require_roles("analyst", "admin")), db: Session = Depends(get_db)):
    compute_merchant_profiles(db)
    return {"status": "ok", "message": "Merchant risk profiles rebuilt"}


@router.get("/")
def list_profiles(
    tier: str = None,
    limit: int = Query(100, ge=1, le=500),
    skip: int = 0,
    db: Session = Depends(get_db),
):
    return list_merchant_profiles(db, tier=tier, limit=limit, skip=skip)


@router.get("/summary")
def merchant_summary(db: Session = Depends(get_db)):
    compute_merchant_profiles(db)
    from app.models.models import MerchantRiskProfile
    total = db.query(MerchantRiskProfile).count()
    tiers = {}
    for t in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        tiers[t] = db.query(MerchantRiskProfile).filter(
            MerchantRiskProfile.risk_tier == t
        ).count()
    avg = db.query(MerchantRiskProfile.risk_score).all()
    avg_score = sum(a[0] for a in avg) / total if avg else 0
    return {
        "total_merchants": total,
        "tiers": tiers,
        "avg_risk_score": round(avg_score, 2),
    }


@router.get("/{merchant_id}")
def profile_detail(merchant_id: str, db: Session = Depends(get_db)):
    data = get_merchant_profile(db, merchant_id)
    if not data:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    return data
