"""Smoke script: SAM over 3 MVTec images x 3 prompts, overlays, one judge call.

Canonical run: cd backend && python scripts/smoke.py [--fake]
Fake mode uses deterministic fakes with distinct cache ids so it can
never poison the real cache. Real mode is the default.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections import Counter
from pathlib import Path

# Bootstrap the backend root onto sys.path so `python scripts/smoke.py`
# from backend/ (and `python backend/scripts/smoke.py` from repo root)
# can import `app.*`.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from PIL import Image, ImageDraw  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.adapters.base import AdapterNotConfiguredError  # noqa: E402
from app.adapters.fakes import FakeJudge, FakeSegmenter  # noqa: E402
from app.adapters.muse_spark import MuseSparkJudge  # noqa: E402
from app.adapters.sam import SamSegmenter  # noqa: E402
from app.config import settings  # noqa: E402
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache  # noqa: E402
from app.pipeline.measure import measure_mask  # noqa: E402
from app.pipeline.overlay import make_overlay  # noqa: E402
from app.schemas import Detection, ProductProfile, RawMask  # noqa: E402

SMOKE_PROMPTS = ["scratch", "crack", "dent"]


def build_adapters(fake: bool) -> tuple[CachedSegmenter, CachedJudge]:
    """Single fake/real selection point. Returns cached adapters."""
    cache = DiskCache(Path(settings.data_dir) / "cache")
    if fake:
        segmenter = CachedSegmenter(FakeSegmenter(), "fake-sam", cache)
        judge = CachedJudge(FakeJudge(), "fake-judge", cache)
    else:
        segmenter = CachedSegmenter(
            SamSegmenter(), settings.sam_model_id, cache
        )
        judge = CachedJudge(
            MuseSparkJudge(), settings.judge_model_id, cache
        )
    return segmenter, judge


def _collect_images(root: Path, exclude_roots: list[Path]) -> list[Path]:
    if not root.exists():
        return []
    found = {
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    }
    return [
        path
        for path in sorted(found, key=str)
        if not any(_is_under(path, ex) for ex in exclude_roots)
    ]


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def discover_image_paths() -> list[Path]:
    mvtec = Path(settings.mvtec_dir)
    images = _collect_images(mvtec, exclude_roots=[])
    if len(images) >= 3:
        return images[:3]
    data_dir = Path(settings.data_dir)
    cache_root = data_dir / "cache"
    smoke_root = data_dir / "runs" / "smoke"
    fallback = _collect_images(data_dir, exclude_roots=[cache_root, smoke_root])
    if len(fallback) >= 3:
        return fallback[:3]
    return (images or fallback)[:3]


def _make_placeholders() -> list[tuple[str, Image.Image]]:
    placeholders: list[tuple[str, Image.Image]] = []
    colors = [(180, 180, 180), (150, 170, 190), (190, 160, 140)]
    for i, color in enumerate(colors, start=1):
        img = Image.new("RGB", (128, 96), color=color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([10 + i * 5, 10, 50 + i * 5, 40], outline=(80, 80, 80), width=2)
        draw.ellipse([70, 50, 110, 85], outline=(60, 60, 60), width=2)
        placeholders.append((f"placeholder_{i}", img))
    return placeholders


def _masks_to_detections(masks: list[RawMask]) -> list[Detection]:
    """Measure raw masks into `Detection`s with `d1...` ids, in mask order.

    Undecodable RLE is skipped with a warning (inspect.py precedent);
    size-mismatched masks still measure fine here and are skipped with
    a warning later by `make_overlay`.
    """
    detections: list[Detection] = []
    for mask in masks:
        try:
            measured = measure_mask(mask.mask_rle)
        except Exception as exc:
            warnings.warn(
                f"skipping undecodable RLE for {mask.label!r}: {exc}"
            )
            continue
        detections.append(
            Detection(
                id=f"d{len(detections) + 1}",
                label=mask.label,
                score=mask.score,
                bbox=measured["bbox"],
                mask_rle=mask.mask_rle,
                area_px=measured["area_px"],
                length_px=measured["length_px"],
            )
        )
    return detections


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ZeroShot QC smoke run")
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use deterministic fake adapters instead of the real Meta API.",
    )
    args = parser.parse_args(argv)
    fake: bool = args.fake

    segmenter, judge = build_adapters(fake)

    paths = discover_image_paths()
    images: list[tuple[str, Image.Image]] = []
    if len(paths) >= 3:
        for path in paths[:3]:
            try:
                with Image.open(path) as raw:
                    images.append((path.stem, raw.convert("RGB").copy()))
            except Exception as exc:
                print(f"error: could not open image {path}: {exc}", file=sys.stderr)
                return 1
    else:
        if fake:
            images = _make_placeholders()
        else:
            mvtec_dir = Path(settings.mvtec_dir)
            data_dir = Path(settings.data_dir)
            print(
                "data missing: need 3 images ( *.png / *.jpg / *.jpeg ) under "
                f"{mvtec_dir} (or {data_dir}).\n"
                "Download MVTec AD (CC BY-NC-SA 4.0) into data/mvtec/ — see README — "
                "or run with --fake to verify the plumbing on placeholder images.",
                file=sys.stderr,
            )
            return 1

    overlay_dir = Path(settings.data_dir) / "runs" / "smoke"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    per_image_detections: list[list[Detection]] = []
    overlays: list[Image.Image] = []
    seen_stems: dict[str, int] = {}

    try:
        for stem, image in images:
            masks = segmenter.segment(image, SMOKE_PROMPTS)
            counts = Counter(m.label for m in masks)
            parts = ", ".join(
                f"{prompt}={counts.get(prompt, 0)}" for prompt in SMOKE_PROMPTS
            )
            extra = [lbl for lbl in counts if lbl not in SMOKE_PROMPTS]
            if extra:
                parts += ", " + ", ".join(f"{lbl}={counts[lbl]}" for lbl in sorted(extra))
            print(f"{stem}: {parts}")

            detections = _masks_to_detections(masks)
            per_image_detections.append(detections)
            overlay = make_overlay(image, detections)
            overlays.append(overlay)
            occurrence = seen_stems.get(stem, 0)
            seen_stems[stem] = occurrence + 1
            if occurrence == 0:
                overlay_path = overlay_dir / f"{stem}_overlay.png"
            else:
                overlay_path = overlay_dir / f"{stem}_{occurrence + 1}_overlay.png"
            overlay.save(overlay_path, format="PNG")
    except AdapterNotConfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    first_stem, first_image = images[0]
    first_overlay = overlays[0]
    detections = per_image_detections[0]
    profile = ProductProfile(
        id="smoke",
        name="Smoke",
        defect_prompts=list(SMOKE_PROMPTS),
        rules="Smoke check: flag any scratch, crack, or dent.",
    )
    try:
        verdict = judge.judge(first_image, first_overlay, None, detections, profile)
    except AdapterNotConfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"error: judge verdict failed validation: {exc}", file=sys.stderr)
        return 1

    print(f"verdict: {verdict.model_dump_json()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
