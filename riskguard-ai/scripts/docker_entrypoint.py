import os
import sys

# Make app/ and ml/ importable regardless of CWD (mirrors local dev bootstrap).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.models.database import engine, Base, SessionLocal
from app.models.models import Transaction


def ensure_demo_data():
    Base.metadata.create_all(bind=engine)
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