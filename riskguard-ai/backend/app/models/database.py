import os

# Resolve DATABASE_URL from .env early so a relative sqlite path is anchored to
# the repo root no matter which working directory the process runs from. Without
# this, seeding (run from the repo root) and the backend (run from backend/) can
# silently end up on two different database files.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# backend/app/models -> backend/app -> backend -> repo root (project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_DEFAULT_DATABASE_URL = "sqlite:///./riskguard.db"


def _resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///") :]
        if path and not os.path.isabs(path):
            path = os.path.normpath(os.path.join(PROJECT_ROOT, path))
        return "sqlite:///" + path
    return url


DATABASE_URL = _resolve_database_url()

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()