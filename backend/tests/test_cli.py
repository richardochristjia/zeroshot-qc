"""CLI tests: inspect happy path, error contract, and empty detections.

The repo-root `cli.py` is loaded by file location (test_smoke.py
precedent); all runs use `--fake` with a tmp data dir so no real
models or repo files are touched.

Run: cd backend && .venv/bin/python -m pytest tests/test_cli.py
"""

import importlib.util
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings


def _load_cli():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "cli.py"
    spec = importlib.util.spec_from_file_location("cli_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


@pytest.fixture
def cli_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(settings, "data_dir", str(data_dir))
    return data_dir


@pytest.fixture
def part_image(tmp_path: Path) -> Path:
    image_path = tmp_path / "part.png"
    Image.new("RGB", (64, 48), color=(150, 150, 150)).save(
        image_path, format="PNG"
    )
    return image_path


def test_inspect_fake_happy_path_prints_lines_and_saves_overlay(
    cli_dirs: Path, part_image: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # screw ships mm_per_px=null, so its lines also pin `-` rendering.
    argv = [
        "inspect",
        str(part_image),
        "--profile",
        "screw",
        "--no-judge",
        "--fake",
    ]
    assert cli.main(argv) == 0
    captured = capsys.readouterr()
    assert "d1 " in captured.out
    assert "area_mm2=- length_mm=-" in captured.out
    overlay_lines = [
        line for line in captured.out.splitlines() if line.startswith("overlay: ")
    ]
    assert len(overlay_lines) == 1
    overlay_path = Path(overlay_lines[0].removeprefix("overlay: "))
    assert overlay_path == cli_dirs / "runs" / "cli" / "part_overlay.png"
    assert overlay_path.is_file()
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_inspect_unknown_profile_exits_one_without_traceback(
    cli_dirs: Path, part_image: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "inspect",
        str(part_image),
        "--profile",
        "no-such",
        "--no-judge",
        "--fake",
    ]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "unknown profile" in captured.err
    assert captured.out == ""
    assert "Traceback" not in captured.err


def test_inspect_bad_image_exits_one_without_traceback(
    cli_dirs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "inspect",
        str(tmp_path / "missing.png"),
        "--profile",
        "screw",
        "--no-judge",
        "--fake",
    ]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "could not open image" in captured.err
    assert captured.out == ""
    assert "Traceback" not in captured.err


class _EmptySegmenter:
    def segment(self, image: Image.Image, prompts: list[str]) -> list:
        return []


def test_inspect_empty_detections_exits_zero_with_unmarked_overlay(
    cli_dirs: Path,
    part_image: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "build_segmenter", lambda fake: _EmptySegmenter())
    argv = [
        "inspect",
        str(part_image),
        "--profile",
        "screw",
        "--no-judge",
        "--fake",
    ]
    assert cli.main(argv) == 0
    captured = capsys.readouterr()
    assert "no detections" in captured.out
    assert "overlay: " in captured.out
    assert (cli_dirs / "runs" / "cli" / "part_overlay.png").is_file()
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
