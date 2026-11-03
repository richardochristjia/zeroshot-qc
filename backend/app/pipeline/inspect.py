"""Segmentation orchestrator (M2 Inspect phase) plus the M3 judge step.

Single flow: load image (RGB) + named profile, segment, drop masks
below ``profile.min_score``, greedily merge duplicates with IoU above
0.5, assign stable ``d1, d2, ...`` ids in score order, measure each.
With a judge supplied, render the overlay and judge the detections
against the effective rules, then force FAIL in code per the
consistency rule (HANDOFF §7 step 8).
"""

import json
import math
import os
import re
import tempfile
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from pycocotools import mask as mask_api

from app.adapters.base import Judge, Segmenter
from app.config import settings
from app.pipeline.measure import decode_rle_for_image, measure_mask
from app.pipeline.overlay import make_overlay
from app.schemas import Detection, ProductProfile, RawMask, Verdict

MERGE_IOU_THRESHOLD = 0.5

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"

# No separators or dots: absolute paths and `..` traversal cannot spell
# a match, so the joined path always stays under PROFILES_DIR.
_PROFILE_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")


def load_profile(name: str) -> ProductProfile:
    """Load ``backend/profiles/<name>.json`` and validate as ProductProfile.

    Anchored to this module file so repo-root and ``backend/`` CWDs
    resolve identically. Names outside ``[A-Za-z0-9_-]+`` are rejected
    so untrusted input (e.g. CLI ``--profile``) cannot traverse.
    """
    if not _PROFILE_NAME_RE.fullmatch(name):
        raise ValueError(f"unknown profile {name!r}: invalid profile name")
    path = PROFILES_DIR / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"unknown profile {name!r}: {path} does not exist") from None
    return ProductProfile.model_validate(data)


def save_profile(profile: ProductProfile) -> Path:
    """Atomically write ``profile`` to ``backend/profiles/<id>.json``."""
    if not _PROFILE_NAME_RE.fullmatch(profile.id):
        raise ValueError(f"unknown profile {profile.id!r}: invalid profile name")
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{profile.id}.json"
    payload = json.dumps(profile.model_dump(), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=PROFILES_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(payload)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def _mask_iou(first: np.ndarray, second: np.ndarray) -> float:
    """IoU of two binary (H, W) masks; 0.0 when both are empty."""
    union = int(np.logical_or(first, second).sum())
    if union == 0:
        return 0.0
    return float(np.logical_and(first, second).sum()) / union


def _encode_mask_text(binary: np.ndarray) -> dict:
    """Re-encode a binary (H, W) array as JSON-safe text-counts COCO RLE."""
    fortran = np.asfortranarray(binary.astype(np.uint8))
    encoded = mask_api.encode(fortran)
    return {
        "size": [int(encoded["size"][0]), int(encoded["size"][1])],
        "counts": encoded["counts"].decode("utf-8"),
    }


def _decode_valid_masks(
    masks: list[RawMask], width: int, height: int
) -> list[tuple[RawMask, np.ndarray]]:
    """Decode masks, skipping undecodable, mismatched, or empty ones.

    An all-zero mask would otherwise emit a ``(0,0,0,0)`` detection.
    """
    valid: list[tuple[RawMask, np.ndarray]] = []
    for mask in masks:
        binary = decode_rle_for_image(
            mask.mask_rle, width, height, f"{mask.label!r}"
        )
        if binary is None:
            continue
        if not binary.any():
            warnings.warn(
                f"skipping zero-area mask for {mask.label!r}: no foreground pixels"
            )
            continue
        valid.append((mask, binary))
    return valid


def resolve_reference_path(path: str) -> Path:
    """Absolute paths pass through; relative ones resolve under data_dir."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(settings.data_dir) / candidate


def _load_reference_image(path: str) -> Image.Image:
    """Load a known-good reference image; missing files are a caller error."""
    try:
        with Image.open(resolve_reference_path(path)) as raw:
            return raw.convert("RGB").copy()
    except Exception as exc:
        raise ValueError(f"could not open reference image {path}: {exc}") from exc


def enforce_consistency(verdict: Verdict) -> Verdict:
    """Force FAIL in code when the rulings demand it (HANDOFF §7 step 8).

    The model's own verdict word is not trusted: any ruling with
    ``is_real_defect`` and a cited rule, any missed defect, or a part that
    does not match the product, means FAIL. Returns the input unchanged
    when it already agrees.
    """
    must_fail = (
        any(r.is_real_defect and r.rule_violated for r in verdict.rulings)
        or bool(verdict.missed_defects)
        or not verdict.part_matches
    )
    if must_fail and verdict.verdict != "FAIL":
        return verdict.model_copy(update={"verdict": "FAIL"})
    return verdict


PART_PAD = 0.08
NO_CROP_AREA = 0.95
# A candidate whose box covers this much of the part box is SAM re-finding
# the part, not a defect; the judge dismisses it and then misses the defect.
PART_SIZED = 0.5


def part_noun(profile: ProductProfile) -> str:
    return profile.name.replace("_", " ").replace("-", " ").strip().lower()


def _box_area(box: tuple[int, int, int, int]) -> int:
    return (box[2] - box[0]) * (box[3] - box[1])


def part_box(
    image: Image.Image, profile: ProductProfile, segmenter: Segmenter
) -> tuple[int, int, int, int] | None:
    """Unpadded (x0, y0, x1, y1) box of the largest part mask, or None.

    Uses the largest mask only, so a stray small mask cannot widen the crop.
    """
    width, height = image.size
    masks = segmenter.segment(image, [part_noun(profile)])
    boxes = []
    for mask, binary in _decode_valid_masks(
        [m for m in masks if m.score >= profile.min_score], width, height
    ):
        ys, xs = np.nonzero(binary)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return max(boxes, key=_box_area) if boxes else None


def crop_box(
    box: tuple[int, int, int, int] | None, size: tuple[int, int]
) -> tuple[int, int, int, int] | None:
    """Padded crop around a part box; None when absent or ~whole frame."""
    if box is None:
        return None
    width, height = size
    x0, y0, x1, y1 = box
    pad = PART_PAD * max(x1 - x0, y1 - y0)
    x0, y0 = max(0, round(x0 - pad)), max(0, round(y0 - pad))
    x1, y1 = min(width, round(x1 + pad)), min(height, round(y1 + pad))
    if (x1 - x0) * (y1 - y0) >= NO_CROP_AREA * width * height:
        return None
    return int(x0), int(y0), int(x1), int(y1)


def locate_part(
    image: Image.Image, profile: ProductProfile, segmenter: Segmenter
) -> tuple[int, int, int, int] | None:
    """Padded (x0, y0, x1, y1) box of the part, or None when absent or ~whole frame."""
    return crop_box(part_box(image, profile, segmenter), image.size)


def _part_sized(binary: np.ndarray, part: tuple[int, int, int, int]) -> bool:
    ys, xs = np.nonzero(binary)
    x0, y0 = max(int(xs.min()), part[0]), max(int(ys.min()), part[1])
    x1, y1 = min(int(xs.max()) + 1, part[2]), min(int(ys.max()) + 1, part[3])
    return max(0, x1 - x0) * max(0, y1 - y0) >= PART_SIZED * _box_area(part)


def judge_box_to_pixels(
    box: list[float] | None, crop: tuple[int, int, int, int]
) -> tuple[int, int, int, int] | None:
    """Map a 0-1000 judge box inside ``crop`` (x0, y0, x1, y1) to full-image (x, y, w, h)."""
    if box is None or len(box) != 4 or not all(math.isfinite(v) for v in box):
        return None
    x1, y1, x2, y2 = box
    if not (0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 1000):
        return None
    cx0, cy0, cx1, cy1 = crop
    cw, ch = cx1 - cx0, cy1 - cy0
    px0, px1 = round(cx0 + x1 * cw / 1000), round(cx0 + x2 * cw / 1000)
    py0, py1 = round(cy0 + y1 * ch / 1000), round(cy0 + y2 * ch / 1000)
    px0, px1 = max(cx0, px0), min(cx1, px1)
    py0, py1 = max(cy0, py0), min(cy1, py1)
    if px1 - px0 < 1 or py1 - py0 < 1:
        return None
    return px0, py0, px1 - px0, py1 - py0


def _judge_detections(
    verdict: Verdict, crop: tuple[int, int, int, int], size: tuple[int, int], mm_per_px: float | None
) -> list[Detection]:
    width, height = size
    found = []
    for index, missed in enumerate(verdict.missed_defects, start=1):
        mapped = judge_box_to_pixels(missed.box, crop)
        if mapped is None:
            continue
        x, y, w, h = mapped
        binary = np.zeros((height, width), dtype=np.uint8)
        binary[y : y + h, x : x + w] = 1
        mask_rle = _encode_mask_text(binary)
        sizes = measure_mask(mask_rle, mm_per_px)
        found.append(
            Detection(
                id=f"j{index}",
                label="judge",
                score=verdict.confidence,
                bbox=sizes["bbox"],
                mask_rle=mask_rle,
                area_px=sizes["area_px"],
                length_px=sizes["length_px"],
                area_mm2=sizes["area_mm2"],
                length_mm=sizes["length_mm"],
                source="judge",
            )
        )
    return found


def run_inspection(
    image: Image.Image,
    profile: ProductProfile,
    segmenter: Segmenter,
    judge: Judge | None = None,
    rules: str | None = None,
    reference: Image.Image | None = None,
    part_crop: bool = False,
) -> list[Detection] | tuple[list[Detection], Verdict]:
    """Segment, filter, merge, measure, and optionally judge.

    Without a judge this is the M2 path and returns score-ordered
    detections. With a judge it also renders the overlay, judges the
    detections, enforces the consistency rule, and returns
    ``(detections, verdict)``.

    ``rules`` replaces ``profile.rules`` for this call only (the
    profile object is never mutated); ``reference`` overrides
    ``profile.reference_image`` for this call, which is otherwise
    loaded from disk when set. ``part_crop`` judges a zoomed crop of the
    part SAM finds (image, overlay and the reference's own part box);
    detections stay in full-image pixels.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    part = None
    if judge is not None and part_crop:
        # The part lookup does not depend on the defect call: run both at once.
        with ThreadPoolExecutor(max_workers=1) as pool:
            part_job = pool.submit(part_box, image, profile, segmenter)
            raw_masks = segmenter.segment(image, profile.defect_prompts)
            part = part_job.result()
    else:
        raw_masks = segmenter.segment(image, profile.defect_prompts)
    kept = [m for m in raw_masks if m.score >= profile.min_score]
    decoded = _decode_valid_masks(kept, width, height)
    if part is not None:
        decoded = [(m, b) for m, b in decoded if not _part_sized(b, part)]
    decoded.sort(key=lambda item: (-item[0].score, item[0].label))

    groups: list[dict] = []
    for mask, binary in decoded:
        target = None
        for group in groups:
            if _mask_iou(binary, group["mask"]) > MERGE_IOU_THRESHOLD:
                target = group
                break
        if target is None:
            groups.append({"mask": binary, "score": mask.score, "labels": [mask.label]})
        else:
            target["mask"] = np.logical_or(target["mask"], binary).astype(np.uint8)
            if mask.label not in target["labels"]:
                target["labels"].append(mask.label)
            target["score"] = max(target["score"], mask.score)

    groups.sort(key=lambda g: (-g["score"], "+".join(g["labels"])))
    detections: list[Detection] = []
    for index, group in enumerate(groups, start=1):
        mask_rle = _encode_mask_text(group["mask"])
        sizes = measure_mask(mask_rle, profile.mm_per_px)
        detections.append(
            Detection(
                id=f"d{index}",
                label="+".join(group["labels"]),
                score=group["score"],
                bbox=sizes["bbox"],
                mask_rle=mask_rle,
                area_px=sizes["area_px"],
                length_px=sizes["length_px"],
                area_mm2=sizes["area_mm2"],
                length_mm=sizes["length_mm"],
            )
        )
    if judge is None:
        return detections
    effective_profile = profile
    if rules is not None:
        effective_profile = profile.model_copy(update={"rules": rules})
    effective_reference = reference
    if effective_reference is None and profile.reference_image:
        effective_reference = _load_reference_image(profile.reference_image)
    overlay = make_overlay(image, detections)
    judged_image = image
    crop = (0, 0, width, height)
    box = crop_box(part, image.size)
    if box:
        judged_image, overlay = image.crop(box), overlay.crop(box)
        crop = box
        # Same reference every call, so this is a cache hit after the first.
        ref_box = effective_reference is not None and locate_part(
            effective_reference, profile, segmenter
        )
        if ref_box:
            effective_reference = effective_reference.crop(ref_box)
    verdict = judge.judge(
        judged_image, overlay, effective_reference, detections, effective_profile
    )
    detections = detections + _judge_detections(
        verdict, crop, (width, height), profile.mm_per_px
    )
    return detections, enforce_consistency(verdict)


def inspect_image(
    image_path: str | Path, profile_name: str, segmenter: Segmenter
) -> list[Detection]:
    """Load image + named profile from disk, then run the inspection."""
    image = Image.open(image_path).convert("RGB")
    profile = load_profile(profile_name)
    return run_inspection(image, profile, segmenter)
