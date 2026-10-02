import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # тесты не открывают окна

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXAMPLES = ROOT / "examples"
