"""Adds the repo root to sys.path so `scripts/*.py` can `import src...`
when run directly (`python scripts/fetch.py`) rather than as a module."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
