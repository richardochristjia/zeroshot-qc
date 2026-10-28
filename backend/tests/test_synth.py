"""Synth generator tests (M5): determinism, verbatim masks, diff fallback.

Run: cd backend && .venv/bin/python -m pytest -q
"""

from pathlib import Path

import pytest

import numpy as np
from PIL import Image

from app.adapters.fakes import FakeImageGenerator
from app.config import settings
from app.synth import generate as gen
from app.synth.generate import diff_mask, generate_pairs


def _written_bytes(pairs: list[tuple[Path, Path | None]]) -> list[tuple[bytes, bytes | None]]:
    return [
        (
            image_path.read_bytes(),
            mask_path.read_bytes() if mask_path is not None else None,
        )
        for image_path, mask_path in pairs
    ]


def test_fake_generate_is_deterministic(tmp_path: Path) -> None:
    first = generate_pairs(
        "bottle", "scratch", 3, generator=FakeImageGenerator(), out_root=tmp_path
    )
    assert len(first) == 3
    for image_path, mask_path in first:
        assert image_path.is_file()
        assert mask_path is not None and mask_path.is_file()
    before = _written_bytes(first)
    second = generate_pairs(
        "bottle", "scratch", 3, generator=FakeImageGenerator(), out_root=tmp_path
    )
    assert _written_bytes(second) == before


def test_layout_paths_exact(tmp_path: Path) -> None:
    pairs = generate_pairs(
        "bottle", "scratch", 2, generator=FakeImageGenerator(), out_root=tmp_path
    )
    assert [str(image_path.relative_to(tmp_path)) for image_path, _ in pairs] == [
        "bottle/scratch/000.png",
        "bottle/scratch/001.png",
    ]
    assert [str(mask_path.relative_to(tmp_path)) for _, mask_path in pairs] == [
        "bottle/scratch/000_mask.png",
        "bottle/scratch/001_mask.png",
    ]
    assert (tmp_path / "bottle" / "_reference.png").is_file()


def test_returned_masks_used_verbatim(tmp_path: Path) -> None:
    generator = FakeImageGenerator()
    pairs = generate_pairs(
        "bottle", "scratch", 2, generator=generator, out_root=tmp_path
    )
    for image_path, mask_path in pairs:
        assert mask_path is not None
        stored = np.asarray(Image.open(mask_path).convert("L"))
        assert stored.size > 0 and (stored > 128).any()


def test_missing_mask_triggers_diff_fallback(tmp_path: Path, capsys) -> None:
    class PaintOnly:
        """add_defect without add_defect_with_mask: forces the diff path."""

        def add_defect(self, good_image, defect_description, mask):
            painted = good_image.convert("RGB").copy()
            pixels = painted.load()
            for y in range(6, 14):
                for x in range(6, 14):
                    pixels[x, y] = (255, 0, 0)
            return painted

    pairs = generate_pairs(
        "bottle", "scratch", 1, generator=PaintOnly(), out_root=tmp_path
    )
    _, mask_path = pairs[0]
    assert mask_path is not None and mask_path.is_file()
    stored = np.asarray(Image.open(mask_path).convert("L"))
    assert (stored > 128).any()
    out = capsys.readouterr().out
    assert "mask=diff(threshold=" in out


def test_empty_diff_keeps_image_omits_mask_and_logs(tmp_path: Path, capsys) -> None:
    class Identity:
        def add_defect(self, good_image, defect_description, mask):
            return good_image.convert("RGB").copy()

    pairs = generate_pairs(
        "bottle", "scratch", 1, generator=Identity(), out_root=tmp_path
    )
    image_path, mask_path = pairs[0]
    assert image_path.is_file()
    assert mask_path is None
    assert list(tmp_path.rglob("*_mask.png")) == []
    out = capsys.readouterr().out
    assert "empty diff, omitting mask" in out


def test_rerun_empty_diff_removes_stale_mask(tmp_path: Path) -> None:
    from app.eval.dataset import load_synth_category

    class PaintOnly:
        def add_defect(self, good_image, defect_description, mask):
            painted = good_image.convert("RGB").copy()
            pixels = painted.load()
            for y in range(6, 14):
                for x in range(6, 14):
                    pixels[x, y] = (255, 0, 0)
            return painted

    class Identity:
        def add_defect(self, good_image, defect_description, mask):
            return good_image.convert("RGB").copy()

    generate_pairs(
        "bottle", "scratch", 1, generator=PaintOnly(), out_root=tmp_path
    )
    assert (tmp_path / "bottle" / "scratch" / "000_mask.png").is_file()
    pairs = generate_pairs(
        "bottle", "scratch", 1, generator=Identity(), out_root=tmp_path
    )
    _, mask_path = pairs[0]
    assert mask_path is None
    assert not (tmp_path / "bottle" / "scratch" / "000_mask.png").exists()
    _, items = load_synth_category(tmp_path, "bottle")
    assert items[0].mask_path is None


def test_all_black_exact_mask_omitted_and_unlinked(
    tmp_path: Path, capsys
) -> None:
    class BlackMask:
        def add_defect_with_mask(
            self, good_image, defect_description, *, seed: str = ""
        ):
            image = good_image.convert("RGB").copy()
            return image, Image.new("L", image.size, 0)

    generate_pairs(
        "bottle", "scratch", 1,
        generator=FakeImageGenerator(), out_root=tmp_path,
    )
    assert (tmp_path / "bottle" / "scratch" / "000_mask.png").is_file()
    pairs = generate_pairs(
        "bottle", "scratch", 1, generator=BlackMask(), out_root=tmp_path
    )
    image_path, mask_path = pairs[0]
    assert image_path.is_file()
    assert mask_path is None
    assert list(tmp_path.rglob("*_mask.png")) == []
    assert "empty exact mask, omitting mask" in capsys.readouterr().out


def test_diff_mask_finds_painted_shapes() -> None:
    good = Image.new("RGB", (48, 48), (128, 128, 128))
    bad = good.copy()
    bad_pixels = bad.load()
    for y in range(10, 20):
        for x in range(10, 20):
            bad_pixels[x, y] = (255, 0, 0)
    mask = diff_mask(good, bad)
    expected = np.zeros((48, 48), bool)
    expected[10:20, 10:20] = True
    assert (mask == expected).all()
    assert not bool(diff_mask(good, good.copy()).any())


def test_load_good_image_uses_relative_profile_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "mvtec").mkdir()
    Image.new("RGB", (7, 5), color=(1, 2, 3)).save(tmp_path / "mvtec" / "g.png")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "p.json").write_text(
        '{"id": "p", "name": "P", "defect_prompts": ["x"], "rules": "r",'
        ' "reference_image": "mvtec/g.png"}'
    )
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(gen, "PROFILES_DIR", profiles)
    image, _ = gen.load_good_image("p")
    assert image.size == (7, 5)
