import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

for path in (
    ROOT / "src" / "shared" / "core" / "src",
    ROOT / "src" / "shared" / "ai" / "src",
    ROOT / "src" / "shared" / "db" / "src",
):
    sys.path.insert(0, str(path))
