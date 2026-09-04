import os
import sys

# backend/app -> repo root (project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Ensure the ml/ package is importable regardless of the working directory the
# backend is launched from (uvicorn, pytest, docker, IDE run buttons, etc).
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)