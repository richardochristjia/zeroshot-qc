"""Every committed profile's reference image exists under data_dir."""

import json
from pathlib import Path

import pytest

from app.config import settings
from app.pipeline.inspect import resolve_reference_path
from app.synth.generate import PROFILES_DIR

PROFILES = sorted(PROFILES_DIR.glob("*.json"))


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_profile_reference_exists(path: Path) -> None:
    ref = json.loads(path.read_text(encoding="utf-8")).get("reference_image")
    if not ref:
        pytest.skip("profile sets no reference_image")
    if not (Path(settings.data_dir) / "mvtec").is_dir():
        pytest.skip("MVTec dataset absent")
    assert resolve_reference_path(ref).is_file()
