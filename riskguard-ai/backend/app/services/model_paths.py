import os
import sys

# backend/app/services -> backend/app -> backend -> repo root (project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Make the ml/ package importable no matter where uvicorn/tests are launched from.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

MODEL_DIR = os.path.join(PROJECT_ROOT, "ml", "models")
EVAL_METRICS_PATH = os.path.join(MODEL_DIR, "evaluation_metrics.json")
HONEST_METRICS_PATH = os.path.join(MODEL_DIR, "honest_metrics.json")
FEEDBACK_LEDGER_PATH = os.path.join(MODEL_DIR, "feedback_loop_history.json")


def model_path(name: str) -> str:
    return os.path.join(MODEL_DIR, name)