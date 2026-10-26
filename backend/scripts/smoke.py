"""Smoke script: SAM over 3 MVTec images x 3 prompts, overlays, one judge call.

Canonical run: cd backend && python scripts/smoke.py [--fake]
Fake mode uses deterministic fakes with distinct cache ids so it can
never poison the real cache. Real mode is the default.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Bootstrap the backend root onto sys.path so `python scripts/smoke.py`
# from backend/ (and `python backend/scripts/smoke.py` from repo root)
# can import `app.*`.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from pycocotools import mask as mask_api  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.adapters.base import AdapterNotConfiguredError  # noqa: E402
from app.adapters.fakes import FakeJudge, FakeSegmenter  # noqa: E402
from app.adapters.muse_spark import MuseSparkJudge  # noqa: E402
from app.adapters.sam import SamSegmenter  # noqa: E402
from app.config import settings  # noqa: E402
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache  # noqa: E402
from app.schemas import Detection, ProductProfile, RawMask, Verdict  # noqa: E402

SMOKE_PROMPTS = ["scratch", "crack", "dent"]

_IMAGE_GLOBS = ("*.png", "*.jpg", "*.jpeg")

_TINT_COLORS: dict[str, tuple[int, int, int]] = {
    "scratch": (255, 80, 80),
    "crack": (80, 200, 80),
    "dent": (80, 120, 255),
}


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
    found: list[Path] = []
    for pattern in _IMAGE_GLOBS:
        for path in root.rglob(pattern):
            # Case-insensitive extension match via lower suffix check is
            # handled by glob patterns already being lower; also accept
            # upper-case extensions by scanning all files.
            found.append(path)
    # Also catch upper-case extensions.
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            if path not in found:
                found.append(path)
    # Deduplicate and sort by path string.
    unique = sorted(set(found), key=lambda p: str(p))
    filtered: list[Path] = []
    for path in unique:
        if any(_is_under(path, ex) for ex in exclude_roots):
            continue
        filtered.append(path)
    return filtered


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
    # Return whatever we have (0-2). Caller decides fake vs real.
    # Prefer mvtec results if any, else fallback.
    combined = images if images else fallback
    return combined[:3]


def _make_placeholders() -> list[tuple[str, Image.Image]]:
    placeholders: list[tuple[str, Image.Image]] = []
    colors = [(180, 180, 180), (150, 170, 190), (190, 160, 140)]
    for i, color in enumerate(colors, start=1):
        img = Image.new("RGB", (128, 96), color=color)
        draw = ImageDraw.Draw(img)
        # Deterministic detail so segmentation hash differs per image.
        draw.rectangle([10 + i * 5, 10, 50 + i * 5, 40], outline=(80, 80, 80), width=2)
        draw.ellipse([70, 50, 110, 85], outline=(60, 60, 60), width=2)
        placeholders.append((f"placeholder_{i}", img))
    return placeholders


def _decode_mask(mask_rle: dict, height: int, width: int) -> np.ndarray:
    counts = mask_rle.get("counts")
    if isinstance(counts, str):
        counts_bytes = counts.encode("utf-8")
    elif isinstance(counts, bytes):
        counts_bytes = counts
    else:
        # Fallback: try to encode via pycocotools from uncompressed form.
        counts_bytes = counts  # type: ignore[assignment]
    rle = {"size": mask_rle.get("size", [height, width]), "counts": counts_bytes}
    decoded = mask_api.decode(rle)
    # decode returns (h, w) or (h, w, n); squeeze to 2D.
    if decoded.ndim == 3:
        decoded = decoded[:, :, 0]
    return decoded


def _make_overlay(image: Image.Image, masks: list[RawMask]) -> Image.Image:
    base = image.convert("RGB")
    h, w = base.size[1], base.size[0]
    overlay_arr = np.array(base, dtype=np.float32)
    for mask in masks:
        color = _TINT_COLORS.get(mask.label, (255, 200, 0))
        try:
            binary = _decode_mask(mask.mask_rle, h, w)
        except Exception:
            continue
        # binary is (h, w) with 0/1
        sel = binary.astype(bool)
        if not sel.any():
            continue
        tint = np.array(color, dtype=np.float32)
        overlay_arr[sel] = overlay_arr[sel] * 0.45 + tint * 0.55
    return Image.fromarray(np.clip(overlay_arr, 0, 255).astype(np.uint8), mode="RGB")


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

    # --- Image discovery -------------------------------------------
    paths = discover_image_paths()
    # Each entry: (stem, PIL image)
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

    per_image_masks: list[list[RawMask]] = []
    overlays: list[Image.Image] = []

    try:
        for stem, image in images:
            masks = segmenter.segment(image, SMOKE_PROMPTS)
            per_image_masks.append(masks)
            counts = Counter(m.label for m in masks)
            parts = ", ".join(
                f"{prompt}={counts.get(prompt, 0)}" for prompt in SMOKE_PROMPTS
            )
            # Include any unexpected labels too.
            extra = [lbl for lbl in counts if lbl not in SMOKE_PROMPTS]
            if extra:
                parts += ", " + ", ".join(f"{lbl}={counts[lbl]}" for lbl in sorted(extra))
            print(f"{stem}: {parts}")

            overlay = _make_overlay(image, masks)
            overlays.append(overlay)
            overlay_path = overlay_dir / f"{stem}_overlay.png"
            overlay.save(overlay_path, format="PNG")
    except AdapterNotConfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # --- Judge call (once, on first image) -------------------------
    first_stem, first_image = images[0]
    first_overlay = overlays[0]
    first_masks = per_image_masks[0]
    detections = [
        Detection(
            id=f"d{i + 1}",
            label=m.label,
            score=m.score,
            bbox=(0, 0, 0, 0),
            mask_rle=m.mask_rle,
            area_px=0,
            length_px=0.0,
        )
        for i, m in enumerate(first_masks)
    ]
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

    try:
        validated = Verdict.model_validate(verdict.model_dump())
    except ValidationError as exc:
        print(f"error: judge verdict failed validation: {exc}", file=sys.stderr)
        return 1

    print(f"verdict: {validated.model_dump_json()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
