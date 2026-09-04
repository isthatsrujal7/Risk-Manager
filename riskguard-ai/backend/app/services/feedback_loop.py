import os
import sys
import json
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy.orm import Session

from app.models.models import Transaction, Review, RiskAssessment

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "models")


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
            "account_age_days": 180,
            "customer_avg_amount": avg_amt,
            "customer_std_amount": std_amt,
        })

    return pd.DataFrame(rows)


def retrain_from_feedback(db: Session, n_synthetic=3000, fraud_rate=0.05):
    """Retrain the fraud model combining synthetic data with real human-labeled
    feedback. Saves a new versioned model and evaluation metrics. Returns a report."""
    from ml.src.data_generator import generate_synthetic_data
    from ml.src.model import FraudModel, train_and_evaluate

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

    results = train_and_evaluate(data, [])

    best = results["best_model"]
    new_version = f"v2-feedback-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # train_and_evaluate saves with fixed v1 names; re-save under a versioned name
    _version_artifacts(best, new_version, results)

    return {
        "human_labeled_rows": int(len(human_df)),
        "synthetic_rows": n_synthetic,
        "training_total_rows": int(len(data["train"])),
        "best_model": best,
        "new_model_version": new_version,
        "test_metrics": results["models"][best]["test"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def _version_artifacts(best_model_name, version, results):
    """Copy the freshly saved v1 artifacts to a versioned filename + write a
    feedback-loop ledger entry."""
    import shutil
    os.makedirs(MODEL_DIR, exist_ok=True)

    src_model = os.path.join(MODEL_DIR, "fraud_model.joblib")
    src_pipeline = os.path.join(MODEL_DIR, "feature_pipeline.joblib")

    versioned_model = os.path.join(MODEL_DIR, f"fraud_model_{version}.joblib")
    versioned_pipeline = os.path.join(MODEL_DIR, f"feature_pipeline_{version}.joblib")
    if os.path.exists(src_model):
        shutil.copy(src_model, versioned_model)
    if os.path.exists(src_pipeline):
        shutil.copy(src_pipeline, versioned_pipeline)

    ledger_path = os.path.join(MODEL_DIR, "feedback_loop_history.json")
    history = []
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            history = json.load(f)

    history.append({
        "version": version,
        "best_model": best_model_name,
        "f1": results["models"][best_model_name]["test"]["f1"],
        "precision": results["models"][best_model_name]["test"]["precision"],
        "recall": results["models"][best_model_name]["test"]["recall"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    with open(ledger_path, "w") as f:
        json.dump(history, f, indent=2)


def get_feedback_loop_status(db: Session):
    ledger_path = os.path.join(MODEL_DIR, "feedback_loop_history.json")
    history = []
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            history = json.load(f)

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
        "retrain_history": history,
        "last_retrain": history[-1] if history else None,
    }
