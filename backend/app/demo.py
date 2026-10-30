"""Demo bundle: seed ``backend/demo/`` into DATA_DIR and read its manifest."""

import json
import shutil
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


def seed_demo(src: Path, dst: Path) -> int:
    """Copy files under ``src`` into ``dst``; never overwrite. Returns copies made."""
    if not src.is_dir():
        return 0
    copied = 0
    for path in src.rglob("*"):
        target = dst / path.relative_to(src)
        if path.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    return copied


def load_samples(data_dir: Path) -> list[dict]:
    """Manifest entries whose image exists under ``data_dir``; ``[]`` if unreadable."""
    try:
        entries = json.loads((data_dir / "samples.json").read_text(encoding="utf-8"))
        return [e for e in entries if (data_dir / e["file"]).is_file()]
    except (OSError, ValueError, KeyError, TypeError):
        return []
