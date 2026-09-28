import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import card_tracker
card = card_tracker.analyze(df, "C0001", "2025-12")
print(card["title"], card["message"])