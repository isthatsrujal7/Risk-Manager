import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from app.models.database import SessionLocal, engine, Base
from app.models.models import Customer, Transaction, RiskAssessment, BehavioralProfile, Investigation, Review, AuditLog, Alert
from app.services.behavioral import BehavioralFingerprintService
from app.services import model_paths
from app import risk_policy
from ml.src.data_generator import generate_synthetic_data
from ml.src.feature_pipeline import FeaturePipeline
from ml.src.model import FraudModel
import json


def seed_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.auth import ensure_default_users
    ensure_default_users()
    print("Default viewer/analyst/admin accounts ensured.")

    print("Generating synthetic data...")
    data = generate_synthetic_data(n_customers=200, n_transactions=5000, fraud_rate=0.05, seed=42)

    print("Loading ML model...")
    pipeline = FeaturePipeline()
    model = FraudModel()

    model_path = model_paths.model_path("fraud_model.joblib")
    pipeline_path = model_paths.model_path("feature_pipeline.joblib")

    if os.path.exists(model_path) and os.path.exists(pipeline_path):
        model.load(model_path)
        pipeline.load(pipeline_path)
        print("Loaded trained model.")
    else:
        print("No trained model found. Training new model...")
        from ml.src.model import train_and_evaluate
        results = train_and_evaluate(data, [])
        pipeline.load(pipeline_path)
        model.load(model_path)
        print(f"Trained and loaded best model: {results['best_model']}")

    db = SessionLocal()
    behavioral = BehavioralFingerprintService(db)
    try:
        print("Seeding customers...")
        for _, row in data["customers"].iterrows():
            cust = Customer(
                customer_id=row["customer_id"],
                name=f"Customer {row['customer_id'][-5:]}",
                email=f"{row['customer_id'].lower()}@demo.in",
                phone=f"+91{random.randint(7000000000, 9999999999)}",
            )
            db.add(cust)
        db.commit()

        print("Seeding transactions and risk assessments...")
        # Seed the chronological HELD-OUT TEST WINDOW (the newest 20% of the
        # synthetic stream). The model never trained on these rows, so the demo
        # dashboard reproduces the exact metrics claimed on the held-out test
        # set instead of showing training-period numbers. No ground-truth labels
        # are used to shape any score.
        batch_df = data["full"].tail(1000)
        batch_df = batch_df.sort_values("timestamp").reset_index(drop=True)

        for idx, (_, row) in enumerate(batch_df.iterrows()):
            is_fraud_txn = bool(row["is_fraud"])
            payment_status, settlement_status, display_status, actual_status = _get_payment_statuses(is_fraud_txn, row)

            txn = Transaction(
                transaction_id=row["transaction_id"],
                customer_id=row["customer_id"],
                amount=row["amount"],
                currency=row["currency"],
                payment_method=row["payment_method"],
                merchant_category=row["merchant_category"],
                merchant_name=row["merchant_name"],
                device_id=row["device_id"],
                ip_address=row["ip_address"],
                location_city=row["location_city"],
                location_country=row["location_country"],
                timestamp=pd_to_dt(row["timestamp"]),
                is_fraud=is_fraud_txn,
                payment_status=payment_status,
                settlement_status=settlement_status,
                display_status=display_status,
                actual_status=actual_status,
                bank_callback_status="received" if not is_fraud_txn else random.choice(["received", "failed", "missing"]),
                gateway_status="completed" if not is_fraud_txn else random.choice(["completed", "completed", "failed"]),
                bank_ref_number=f"BANK-{random.randint(100000, 999999)}" if not is_fraud_txn else None,
                reversal_count=0 if not is_fraud_txn else random.choice([0, 1, 1, 2]),
                merchant_id=f"MER-{random.randint(1000, 9999)}",
            )
            db.add(txn)

            # Mirror the live scoring semantics exactly: baseline built from the
            # customer's prior history EXCLUDING this transaction, ml features
            # from that baseline, and event-time recency windows.
            profile = behavioral.update_profile(
                row["customer_id"],
                exclude_transaction_id=row["transaction_id"],
                reference_ts=pd_to_dt(row["timestamp"]),
            )

            ml_row = pd.DataFrame([{
                "transaction_id": row["transaction_id"],
                "customer_id": row["customer_id"],
                "amount": float(row["amount"]),
                "currency": "INR",
                "payment_method": row["payment_method"],
                "merchant_category": row["merchant_category"],
                "merchant_name": row["merchant_name"],
                "device_id": row["device_id"],
                "ip_address": row["ip_address"],
                "location_city": row["location_city"],
                "location_country": row["location_country"],
                "timestamp": pd_to_dt(row["timestamp"]),
                "is_fraud": False,
                "account_age_days": int(row.get("account_age_days", 180)),
                "customer_avg_amount": float(row["customer_avg_amount"]),
                "customer_std_amount": float(row["customer_std_amount"]),
                "is_new_device": int(row.get("is_new_device", 0)),
                "is_new_city": int(row.get("is_new_city", 0)),
            }])
            ml_score = float(model.predict_proba(pipeline.transform(ml_row))[0]) * 100

            behavioral_score = behavioral.calculate_deviation(txn, profile)
            final_score = 0.7 * ml_score + 0.3 * behavioral_score
            final_score = min(100, max(0, final_score))

            tier = risk_policy.risk_tier(final_score)
            hitl_band = risk_policy.hitl_band(final_score)
            needs_alert = final_score >= risk_policy.BAND_BLOCK_MIN
            action_map = {"LOW": "ALLOW", "MEDIUM": "VERIFY", "HIGH": "REVIEW", "CRITICAL": "HOLD"}
            action = action_map[tier]
            handling = "AI" if tier == "LOW" else ("AI + HUMAN ALERT" if tier == "CRITICAL" else "HUMAN REVIEW")

            assessment = RiskAssessment(
                transaction_id=row["transaction_id"],
                ml_risk_score=round(ml_score, 2),
                ml_prediction="suspicious" if ml_score > 50 else "legitimate",
                ml_confidence=round(abs(ml_score - 50) / 50, 2),
                behavioral_deviation_score=round(behavioral_score, 2),
                final_risk_score=round(final_score, 2),
                risk_tier=tier,
                recommended_action=action,
                handling_user=handling,
                hitl_band=hitl_band,
                needs_alert=needs_alert,
                top_signals=[
                    {"signal": "amount_ratio", "value": row.get("amount_to_avg_ratio", 1), "weight": 0.3},
                    {"signal": "unusual_hour", "value": row.get("is_unusual_hour", 0), "weight": 0.2},
                    {"signal": "unusual_amount", "value": row.get("is_unusual_amount", 0), "weight": 0.25},
                ],
                feature_contributions={"amount": 0.3, "hour": 0.2, "category": 0.15},
                model_version=model.model_version,
                timestamp=pd_to_dt(row["timestamp"]),
            )
            db.add(assessment)

            if tier in ("HIGH", "CRITICAL"):
                inv = Investigation(
                    transaction_id=row["transaction_id"],
                    customer_id=row["customer_id"],
                    risk_assessment_id=assessment.assessment_id,
                    summary=f"Transaction flagged at {tier} risk. Amount ₹{row['amount']:.0f} is {row.get('amount_to_avg_ratio', 1):.1f}x customer average.",
                    evidence=[
                        {"type": "risk_score", "value": round(final_score, 2), "source": "model"},
                        {"type": "ml_score", "value": round(ml_score, 2), "source": "model"},
                        {"type": "behavioral_deviation", "value": round(behavioral_score, 2), "source": "behavioral_engine"},
                    ],
                    contributing_factors=[
                        f"Transaction amount ₹{row['amount']:.0f} is significantly above average",
                        f"Unusual hour: {row.get('hour', 12)}:00",
                        f"New device/location detected",
                    ],
                    behavioral_anomalies=[
                        f"Amount deviation: {row.get('amount_to_avg_ratio', 1):.1f}x normal",
                        f"Unusual time of day",
                    ],
                    related_activity=[],
                    uncertainty="Model confidence moderate. Behavioral data limited for newer customers.",
                    recommended_action="REVIEW",
                    explanation=f"ML model detected suspicious pattern with {model.model_name_map.get(model.model_type, model.model_type)} ({model.model_version}). Amount and timing are outside normal profile.",
                    timestamp=pd_to_dt(row["timestamp"]),
                )
                db.add(inv)
                db.flush()

                review = Review(
                    investigation_id=inv.investigation_id,
                    transaction_id=row["transaction_id"],
                    ai_recommendation="REVIEW",
                    human_decision="APPROVED" if not row["is_fraud"] else "REJECTED",
                    reviewer_note="Demo seeded decision",
                    reviewer_name="system",
                    decision_timestamp=pd_to_dt(row["timestamp"]),
                    outcome="legitimate" if not row["is_fraud"] else "fraud",
                    is_false_positive=(not row["is_fraud"] and tier in ("HIGH", "CRITICAL")),
                    is_false_negative=False,
                )
                db.add(review)

            if needs_alert:
                alert = AuditLog(
                    transaction_id=row["transaction_id"],
                    event_type="risk_team_alert",
                    event_data={
                        "severity": "CRITICAL",
                        "final_risk_score": final_score,
                        "ai_action": "TRANSACTION_BLOCKED_AND_HELD",
                        "alert_message": f"CRITICAL ALERT: Transaction {row['transaction_id']} scored {final_score:.0f}/100. AI has automatically blocked and held this transaction. Human risk team review recommended IMMEDIATELY.",
                        "risk_tier": tier,
                        "recommended_action": action,
                    },
                    model_version="v1.0-rf",
                )
                db.add(alert)
                db.add(AuditLog(
                    transaction_id=row["transaction_id"],
                    event_type="ai_auto_held",
                    event_data={"reason": "Score >= 90. AI blocked transaction and alerted risk team."},
                    model_version="v1.0-rf",
                ))
                db.add(Alert(
                    alert_type="CRITICAL_TRANSACTION",
                    transaction_id=row["transaction_id"],
                    severity="CRITICAL",
                    source="hitl",
                    title=f"Critical transaction {row['transaction_id']} blocked & held",
                    message=(
                        f"Transaction {row['transaction_id']} scored {final_score:.0f}/100 (CRITICAL). "
                        f"AI has automatically blocked and held this transaction. Human risk team "
                        f"review recommended immediately."
                    ),
                    metadata_json={
                        "final_risk_score": final_score,
                        "risk_tier": tier,
                        "recommended_action": action,
                        "ai_action": "TRANSACTION_BLOCKED_AND_HELD",
                    },
                    status="OPEN",
                    created_at=pd_to_dt(row["timestamp"]),
                ))
            elif tier == "LOW":
                db.add(AuditLog(
                    transaction_id=row["transaction_id"],
                    event_type="auto_allowed",
                    event_data={"handled_by": "ai", "reason": "Low risk score below 25%, auto-processed without human review"},
                    model_version="v1.0-rf",
                ))
            elif tier in ("MEDIUM", "HIGH"):
                db.add(AuditLog(
                    transaction_id=row["transaction_id"],
                    event_type="sent_for_human_review",
                    event_data={
                        "final_risk_score": final_score,
                        "risk_tier": tier,
                        "why": "Score in 25-90 range. AI recommends action but human judgment required.",
                        "ai_recommendation": action,
                    },
                    model_version="v1.0-rf",
                ))

        db.commit()
        print(f"Seeded {db.query(Transaction).count()} transactions")
        print(f"Seeded {db.query(RiskAssessment).count()} risk assessments")
        print(f"Seeded {db.query(Investigation).count()} investigations")
        print(f"Seeded {db.query(Review).count()} reviews")

        print("\nDetecting fraud patterns...")
        _detect_fraud_patterns(db)

        print(f"Seeded {db.query(__import__('app.models.models', fromlist=['FraudPatternTrack']).FraudPatternTrack).count()} fraud patterns")

        print("\nBuilding merchant risk profiles...")
        from app.services.merchant_risk import compute_merchant_profiles
        compute_merchant_profiles(db)
        print(f"Seeded {db.query(Alert).count()} alerts")
        print(f"Seeded {db.query(__import__('app.models.models', fromlist=['MerchantRiskProfile']).MerchantRiskProfile).count()} merchant profiles")
        print("Database seeded successfully!")

    finally:
        db.close()


def pd_to_dt(val):
    if isinstance(val, datetime):
        return val
    if hasattr(val, "to_pydatetime"):
        return val.to_pydatetime()
    return datetime.now(timezone.utc)


def _detect_fraud_patterns(db):
    from app.risk.fraud_patterns import FraudPatternDetector, PATTERN_DESCRIPTIONS
    from app.models.models import FraudPatternTrack

    detector = FraudPatternDetector()
    txns = db.query(Transaction).filter(Transaction.is_fraud == True).limit(60).all()

    for txn in txns:
        txn_data = _build_txn_data(txn)
        history = _get_customer_history(txn.customer_id, db)
        recent = _get_recent_transactions(txn.customer_id, db, txn)

        try:
            results = detector.detect_all_patterns(txn_data, history, recent)
            for result in results:
                pattern = FraudPatternTrack(
                    transaction_id=txn.transaction_id,
                    customer_id=txn.customer_id,
                    pattern_type=result.pattern_type.value,
                    pattern_name=PATTERN_DESCRIPTIONS[result.pattern_type]["name"],
                    confidence=result.confidence,
                    severity=result.severity,
                    signals=result.signals,
                    explanation=result.explanation,
                    is_merchant_risk=result.is_merchant_risk,
                    is_customer_risk=result.is_customer_risk,
                    recommended_action=result.recommended_action,
                )
                db.add(pattern)
        except Exception as e:
            print(f"  Error detecting patterns for {txn.transaction_id}: {e}")

    db.commit()


def _build_txn_data(txn):
    return {
        "transaction_id": txn.transaction_id,
        "customer_id": txn.customer_id,
        "amount": txn.amount,
        "payment_method": txn.payment_method,
        "merchant_category": txn.merchant_category,
        "merchant_name": txn.merchant_name,
        "merchant_id": txn.merchant_id,
        "device_id": txn.device_id,
        "location_city": txn.location_city,
        "location_country": txn.location_country,
        "timestamp": txn.timestamp,
        "payment_status": txn.payment_status,
        "settlement_status": txn.settlement_status,
        "display_status": txn.display_status,
        "actual_status": txn.actual_status,
        "bank_callback_status": txn.bank_callback_status,
        "gateway_status": txn.gateway_status,
        "bank_ref_number": txn.bank_ref_number,
        "reversal_count": txn.reversal_count,
        "is_fraud": txn.is_fraud,
    }


def _get_customer_history(customer_id, db):
    from app.models.models import Transaction as T
    txns = db.query(T).filter(T.customer_id == customer_id).order_by(T.timestamp.desc()).limit(50).all()
    history = []
    for t in txns:
        history.append({
            "device_id": t.device_id,
            "location_city": t.location_city,
            "amount": t.amount,
            "avg_amount": t.amount,
            "timestamp": t.timestamp,
            "has_refund": t.reversal_count > 0 if t.reversal_count else False,
            "merchant_name": t.merchant_name,
            "payment_method": t.payment_method,
        })
    if history:
        avg = sum(h["amount"] for h in history) / len(history)
        for h in history:
            h["avg_amount"] = avg
    return history


def _get_recent_transactions(customer_id, db, exclude_txn=None):
    from app.models.models import Transaction as T
    txns = db.query(T).filter(T.customer_id == customer_id).order_by(T.timestamp.desc()).limit(30).all()
    recent = []
    for t in txns:
        if exclude_txn and t.transaction_id == exclude_txn.transaction_id:
            continue
        recent.append({
            "transaction_id": t.transaction_id,
            "customer_id": t.customer_id,
            "amount": t.amount,
            "payment_method": t.payment_method,
            "merchant_name": t.merchant_name,
            "merchant_id": t.merchant_id,
            "settlement_status": t.settlement_status,
            "device_id": t.device_id,
            "location_city": t.location_city,
            "timestamp": t.timestamp,
        })
    return recent


def _get_payment_statuses(is_fraud, row):
    """Assign realistic payment/settlement statuses to seed realistic fraud patterns."""
    if not is_fraud:
        return "completed", "completed", "completed", "completed"

    r = random.random()
    amount = row["amount"]
    category = row.get("merchant_category", "")

    if r < 0.3:
        return "completed", "failed", "completed", "failed"
    elif r < 0.5:
        return "completed", "pending", "completed", "pending"
    elif r < 0.65:
        return "completed", "none", "completed", "completed"
    elif r < 0.8:
        return "failed", "failed", "completed", "failed"
    else:
        if amount < 100:
            return "completed", "completed", "completed", "completed"
        return "completed", "failed", "completed", "failed"


if __name__ == "__main__":
    seed_database()
