import os

# backend/app/services -> backend/app -> backend -> repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

MODEL_DIR = os.path.join(_REPO_ROOT, "ml", "models")
EVAL_METRICS_PATH = os.path.join(MODEL_DIR, "evaluation_metrics.json")
HONEST_METRICS_PATH = os.path.join(MODEL_DIR, "honest_metrics.json")
FEEDBACK_LEDGER_PATH = os.path.join(MODEL_DIR, "feedback_loop_history.json")


def model_path(name: str) -> str:
    return os.path.join(MODEL_DIR, name)