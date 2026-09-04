from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Transaction, RiskAssessment, FraudPatternTrack, MerchantRiskProfile


def _merchant_key(merchant_id, merchant_name, category):
    return {
        "merchant_id": merchant_id or "MER-UNKNOWN",
        "merchant_name": merchant_name,
        "category": category,
    }


def compute_merchant_profiles(db: Session):
    """Aggregate risk metrics for every distinct merchant in the transactions
    table and upsert a MerchantRiskProfile row for each."""
    txns = db.query(Transaction).order_by(Transaction.timestamp).all()

    by_merchant = {}
    for t in txns:
        key = t.merchant_id or (t.merchant_name or "MER-UNKNOWN")
        if key not in by_merchant:
            by_merchant[key] = _merchant_key(t.merchant_id, t.merchant_name, t.merchant_category)
            by_merchant[key]["_rows"] = []
        by_merchant[key]["_rows"].append(t)

    for key, info in by_merchant.items():
        rows = info["_rows"]
        risk_scores = []
        flagged = 0
        critical = 0
        high = 0
        medium = 0
        settlement_fail = 0
        reverse = 0
        total_amount = 0.0

        for t in rows:
            total_amount += t.amount or 0
            if t.reversal_count and t.reversal_count > 0:
                reverse += 1
            if t.settlement_status and "fail" in t.settlement_status.lower():
                settlement_fail += 1

            ra = db.query(RiskAssessment).filter(
                RiskAssessment.transaction_id == t.transaction_id
            ).first()
            if ra:
                s = ra.final_risk_score or 0
                risk_scores.append(s)
                if s >= 90:
                    critical += 1
                elif s >= 60:
                    high += 1
                elif s >= 25:
                    medium += 1
                if s >= 25:
                    flagged += 1

        avg_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        max_score = max(risk_scores) if risk_scores else 0

        pattern_count = 0
        for t in rows:
            pattern_count += db.query(FraudPatternTrack).filter(
                FraudPatternTrack.transaction_id == t.transaction_id,
                FraudPatternTrack.is_merchant_risk == True,
            ).count()

        # Composite merchant risk score (0-100): weighted blend of blocked rate,
        # flagged rate, settlement failures, reversals, and max exposure.
        n = max(len(rows), 1)
        blocked_rate = critical / n
        flagged_rate = flagged / n
        failures = min(settlement_fail / n, 1.0)
        reversals = min(reverse / n, 1.0)

        merchant_score = 100 * (
            0.45 * blocked_rate +
            0.20 * flagged_rate +
            0.15 * failures +
            0.10 * reversals +
            0.10 * min(max_score / 100, 1.0)
        )
        merchant_score = min(100, max(0, merchant_score))

        if merchant_score < 25:
            tier = "LOW"
        elif merchant_score < 60:
            tier = "MEDIUM"
        elif merchant_score < 80:
            tier = "HIGH"
        else:
            tier = "CRITICAL"

        profile = db.query(MerchantRiskProfile).filter(
            MerchantRiskProfile.merchant_id == info["merchant_id"]
        ).first()
        if not profile:
            profile = MerchantRiskProfile(merchant_id=info["merchant_id"])
            db.add(profile)

        profile.merchant_name = info["merchant_name"]
        profile.category = info["category"]
        profile.total_transactions = len(rows)
        profile.total_amount = round(total_amount, 2)
        profile.flagged_count = flagged
        profile.critical_count = critical
        profile.high_count = high
        profile.medium_count = medium
        profile.settlement_failure_count = settlement_fail
        profile.reverse_count = reverse
        profile.avg_risk_score = round(avg_score, 2)
        profile.max_risk_score = round(max_score, 2)
        profile.risk_score = round(merchant_score, 2)
        profile.risk_tier = tier
        profile.pattern_count = pattern_count
        profile.last_updated = datetime.now(timezone.utc)

    db.commit()


def list_merchant_profiles(db: Session, tier: str = None, limit=100, skip=0):
    q = db.query(MerchantRiskProfile)
    if tier:
        q = q.filter(MerchantRiskProfile.risk_tier == tier.upper())
    profiles = q.order_by(MerchantRiskProfile.risk_score.desc()).offset(skip).limit(limit).all()
    return [_serialize(p) for p in profiles]


def get_merchant_profile(db: Session, merchant_id: str):
    profile = db.query(MerchantRiskProfile).filter(
        MerchantRiskProfile.merchant_id == merchant_id
    ).first()
    if not profile:
        return None
    data = _serialize(profile)

    txns = db.query(Transaction).filter(Transaction.merchant_id == merchant_id).all()
    data["transactions"] = []
    for t in txns:
        ra = db.query(RiskAssessment).filter(
            RiskAssessment.transaction_id == t.transaction_id
        ).first()
        data["transactions"].append({
            "transaction_id": t.transaction_id,
            "customer_id": t.customer_id,
            "amount": t.amount,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "risk_score": round(ra.final_risk_score, 2) if ra else 0,
            "risk_tier": ra.risk_tier if ra else "UNKNOWN",
            "settlement_status": t.settlement_status,
            "payment_status": t.payment_status,
        })
    data["transactions"].sort(key=lambda x: x["risk_score"], reverse=True)
    return data


def _serialize(p):
    return {
        "merchant_id": p.merchant_id,
        "merchant_name": p.merchant_name,
        "category": p.category,
        "total_transactions": p.total_transactions,
        "total_amount": p.total_amount,
        "flagged_count": p.flagged_count,
        "critical_count": p.critical_count,
        "high_count": p.high_count,
        "medium_count": p.medium_count,
        "settlement_failure_count": p.settlement_failure_count,
        "reverse_count": p.reverse_count,
        "avg_risk_score": p.avg_risk_score,
        "max_risk_score": p.max_risk_score,
        "risk_score": p.risk_score,
        "risk_tier": p.risk_tier,
        "pattern_count": p.pattern_count,
        "last_updated": p.last_updated.isoformat() if p.last_updated else None,
    }
