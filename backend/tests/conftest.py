import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEMO_DIR = REPO / "demo"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
