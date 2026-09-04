import os
import sys

# Make app/ and ml/ importable regardless of CWD (mirrors local dev bootstrap).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.models.database import engine, Base, SessionLocal
from app.models.models import Transaction
from app.services import model_paths


def ensure_trained_model():
    """The trained ML artifacts are committed to the repo (ml/models/*.joblib).

    For environments where they are somehow absent (e.g. a stripped clone with
    LFS/git-lfs disabled), regenerate them from the same deterministic seed used
    for evaluation so the demo never silently falls back to heuristic scoring.
    """
    model_p = model_paths.model_path("fraud_model.joblib")
    pipeline_p = model_paths.model_path("feature_pipeline.joblib")
    if os.path.exists(model_p) and os.path.exists(pipeline_p):
        print(f"Trained model found: {model_p}")
        return
    print("Trained model artifacts missing - retraining from the same seed...")
    from scripts.train_model import main as train_main
    train_main()


def ensure_demo_data():
    Base.metadata.create_all(bind=engine)

    from app.auth import ensure_default_users
    ensure_default_users()

    ensure_trained_model()

    db = SessionLocal()
    try:
        if db.query(Transaction).count() == 0:
            print("Empty database detected - seeding the held-out demo stream...")
            from scripts.seed_database import seed_database
            seed_database()
        else:
            print("Database already populated - skipping seed.")
    finally:
        db.close()


if __name__ == "__main__":
    ensure_demo_data()