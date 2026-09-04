import os
import json
import shutil
from datetime import datetime, timezone

import pandas as pd

from sqlalchemy.orm import Session

from app.models.models import Transaction, Review, RiskAssessment
# Importing model_paths also bootstraps the repo root onto sys.path so ml.src is
# importable no matter which directory the process runs from.
from app.services import model_paths
from app.services.model_paths import MODEL_DIR

_CANDIDATE_DIR = os.path.join(MODEL_DIR, "_candidates")


def _extract_human_labeled_data(db: Session) -> pd.DataFrame:
    """Pull transactions with a confirmed human review into the same DataFrame
    schema the feature pipeline expects, using the human decision as the label."""
    reviews = db.query(Review).filter(Review.human_decision.isnot(None)).all()

    rows = []
    for r in reviews:
        txn = db.query(Transaction).filter(Transaction.transaction_id == r.transaction_id).first()
        if not txn:
            continue
        # Use the human-confirmed outcome as ground truth
        if r.outcome:
            label = 1 if r.outcome == "fraud" else 0
        elif r.human_decision == "REJECTED":
            label = 1
        else:
            label = int(bool(txn.is_fraud))

        # Customer profile fields (fallback to defaults when unavailable)
        from app.models.models import BehavioralProfile
        profile = db.query(BehavioralProfile).filter(
            BehavioralProfile.customer_id == txn.customer_id
        ).first()
        avg_amt = profile.avg_transaction_amount if profile and profile.avg_transaction_amount else (txn.amount or 1000)
        std_amt = profile.std_transaction_amount if profile and profile.std_transaction_amount else (avg_amt * 0.4)

        # Same semantics as live serving: a device/city is "new" when it is not
        # part of the customer's established behavior.
        if profile is not None:
            known_devices = set(profile.common_devices or [])
            known_locations = set(profile.common_locations or [])
            is_new_device = int(txn.device_id not in known_devices)
            is_new_city = int(txn.location_city not in known_locations)
        else:
            is_new_device = 0
            is_new_city = 0

        ts = txn.timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            # Synthetic data generator emits tz-aware UTC timestamps; match that
            # so the combined training frame doesn't mix aware and naive values.
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        rows.append({
            "transaction_id": txn.transaction_id,
            "customer_id": txn.customer_id,
            "amount": txn.amount or 0,
            "currency": txn.currency or "INR",
            "payment_method": txn.payment_method or "unknown",
            "merchant_category": txn.merchant_category or "unknown",
            "merchant_name": txn.merchant_name or "Unknown",
            "device_id": txn.device_id or "DEV-0",
            "ip_address": txn.ip_address or "0.0.0.0",
            "location_city": txn.location_city or "Unknown",
            "location_country": txn.location_country or "IN",
            "timestamp": ts,
            "is_fraud": label,
            "is_new_device": is_new_device,
            "is_new_city": is_new_city,
            "account_age_days": 180,
            "customer_avg_amount": avg_amt,
            "customer_std_amount": std_amt,
        })

    return pd.DataFrame(rows)


def retrain_candidate_from_feedback(db: Session, n_synthetic=3000, fraud_rate=0.05):
    """Train a NEW candidate model on synthetic data + human-labeled feedback.

    This NEVER replaces the active model. The result is written to versioned
    candidate artifacts plus a ledger entry with status "candidate". A risk team
    member must call approve_candidate() to promote it. Returns a report.
    """
    from ml.src.data_generator import generate_synthetic_data
    from ml.src.model import train_and_evaluate

    human_df = _extract_human_labeled_data(db)

    # Build a synthetic base so the model has enough signal + variety
    synthetic = generate_synthetic_data(
        n_customers=200, n_transactions=n_synthetic, fraud_rate=fraud_rate, seed=42
    )
    base_train = synthetic["train"]
    base_val = synthetic["val"]
    base_test = synthetic["test"]

    # Combine human-labeled rows into a training set that mirrors base schema
    if not human_df.empty:
        human_train = human_df.sample(frac=0.8, random_state=42)
        human_test = human_df.drop(human_train.index)
        combined_train = pd.concat([base_train, human_train], ignore_index=True)
        data = {
            "train": combined_train,
            "val": synthetic["val"],
            "test": pd.concat([base_test, human_test], ignore_index=True) if not human_test.empty else base_test,
        }
    else:
        data = {"train": base_train, "val": base_val, "test": base_test}

    # Train into a scratch dir so the ACTIVE fraud_model.joblib /
    # feature_pipeline.joblib are never touched by a candidate run.
    os.makedirs(_CANDIDATE_DIR, exist_ok=True)
    results = train_and_evaluate(data, [], models_dir=_CANDIDATE_DIR)

    best = results["best_model"]
    new_version = f"fb-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    versioned_model = os.path.join(MODEL_DIR, f"fraud_model_{new_version}.joblib")
    versioned_pipeline = os.path.join(MODEL_DIR, f"feature_pipeline_{new_version}.joblib")
    shutil.copy(os.path.join(_CANDIDATE_DIR, "fraud_model.joblib"), versioned_model)
    shutil.copy(os.path.join(_CANDIDATE_DIR, "feature_pipeline.joblib"), versioned_pipeline)

    test_metrics = results["models"][best]["test"]
    _write_ledger({
        "version": new_version,
        "best_model": best,
        "f1": test_metrics["f1"],
        "precision": test_metrics["precision"],
        "recall": test_metrics["recall"],
        "false_positives": test_metrics["false_positives"],
        "false_negatives": test_metrics["false_negatives"],
        "human_labeled_rows": int(len(human_df)),
        "status": "candidate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "human_labeled_rows": int(len(human_df)),
        "synthetic_rows": n_synthetic,
        "training_total_rows": int(len(data["train"])),
        "new_model_version": new_version,
        "test_metrics": test_metrics,
        "status": "candidate",
        "note": "Candidate trained and stored. The active model is UNCHANGED. Approve to promote.",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def approve_candidate(version: str) -> dict:
    """Promote a candidate model to the active fraud_model.joblib.

    An operator explicitly approves a candidate version (e.g. after reviewing
    its held-out metrics in the UI). Only then are the active artifact files
    replaced and the in-process model cache invalidated.
    """
    versioned_model = os.path.join(MODEL_DIR, f"fraud_model_{version}.joblib")
    versioned_pipeline = os.path.join(MODEL_DIR, f"feature_pipeline_{version}.joblib")
    if not os.path.exists(versioned_model) or not os.path.exists(versioned_pipeline):
        return {"ok": False, "error": f"Candidate version '{version}' not found."}

    shutil.copy(versioned_model, os.path.join(MODEL_DIR, "fraud_model.joblib"))
    shutil.copy(versioned_pipeline, os.path.join(MODEL_DIR, "feature_pipeline.joblib"))
    # Refresh the dashboard's reported evaluation metrics from this version.
    for name in ("evaluation_metrics.json", "honest_metrics.json"):
        cand = os.path.join(_CANDIDATE_DIR, name)
        if os.path.exists(cand):
            shutil.copy(cand, os.path.join(MODEL_DIR, name))

    _mark_ledger_approved(version)

    # Invalidate the in-process model cache so the next scored transaction
    # reloads the newly approved artifacts.
    try:
        from app.services import risk_scoring
        risk_scoring.reload_model_cache()
    except Exception:
        pass

    return {"ok": True, "approved_version": version}


def _write_ledger(entry: dict):
    ledger_path = os.path.join(MODEL_DIR, "feedback_loop_history.json")
    history = []
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            history = json.load(f)
    history.append(entry)
    with open(ledger_path, "w") as f:
        json.dump(history, f, indent=2)


def _mark_ledger_approved(version: str):
    ledger_path = os.path.join(MODEL_DIR, "feedback_loop_history.json")
    if not os.path.exists(ledger_path):
        return
    with open(ledger_path) as f:
        history = json.load(f)
    for entry in history:
        if entry.get("version") == version:
            entry["status"] = "approved"
    with open(ledger_path, "w") as f:
        json.dump(history, f, indent=2)


def get_feedback_loop_status(db: Session):
    ledger_path = os.path.join(MODEL_DIR, "feedback_loop_history.json")
    history = []
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            history = json.load(f)

    # Candidate versions currently staged and awaiting approval.
    pending_candidates = [
        {"version": e["version"], "f1": e.get("f1"), "precision": e.get("precision"),
         "recall": e.get("recall"), "created": e.get("timestamp")}
        for e in history if e.get("status") == "candidate"
    ]

    human_rows = len(_extract_human_labeled_data(db))
    reviews_total = db.query(Review).filter(Review.human_decision.isnot(None)).count()
    fp = db.query(Review).filter(Review.is_false_positive == True).count()
    fn = db.query(Review).filter(Review.is_false_negative == True).count()

    # Current active model version from the live weights file
    active_version = "v1.0-rf"
    current_path = os.path.join(MODEL_DIR, "fraud_model.joblib")
    if os.path.exists(current_path):
        try:
            import joblib
            d = joblib.load(current_path)
            active_version = d.get("model_version", active_version)
        except Exception:
            pass

    return {
        "human_labeled_rows": human_rows,
        "total_reviews": reviews_total,
        "false_positives": fp,
        "false_negatives": fn,
        "active_model_version": active_version,
        "pending_candidates": pending_candidates,
        "retrain_history": history,
        "last_retrain": history[-1] if history else None,
        "governance": "Retrained models are staged as candidates and require explicit approval before they become active.",
    }