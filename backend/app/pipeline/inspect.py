"""Segmentation orchestrator (M2 Inspect phase) plus the M3 judge step.

Single flow: load image (RGB) + named profile, segment, drop masks
below ``profile.min_score``, greedily merge duplicates with IoU above
0.5, assign stable ``d1, d2, ...`` ids in score order, measure each.
With a judge supplied, render the overlay and judge the detections
against the effective rules, then force FAIL in code per the
consistency rule (HANDOFF §7 step 8).
"""

import json
import re
import warnings
from pathlib import Path

import numpy as np
from PIL import Image
from pycocotools import mask as mask_api

from app.adapters.base import Judge, Segmenter
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


def _load_reference_image(path: str) -> Image.Image:
    """Load a known-good reference image; missing files are a caller error."""
    try:
        with Image.open(path) as raw:
            return raw.convert("RGB").copy()
    except Exception as exc:
        raise ValueError(f"could not open reference image {path}: {exc}") from exc


def enforce_consistency(verdict: Verdict) -> Verdict:
    """Force FAIL in code when the rulings demand it (HANDOFF §7 step 8).

    The model's own verdict word is not trusted: any ruling with
    ``is_real_defect`` and a cited rule, or any missed defect, means
    FAIL. Returns the input unchanged when it already agrees.
    """
    must_fail = any(
        ruling.is_real_defect and ruling.rule_violated
        for ruling in verdict.rulings
    ) or bool(verdict.missed_defects)
    if must_fail and verdict.verdict != "FAIL":
        return verdict.model_copy(update={"verdict": "FAIL"})
    return verdict


def run_inspection(
    image: Image.Image,
    profile: ProductProfile,
    segmenter: Segmenter,
    judge: Judge | None = None,
    rules: str | None = None,
    reference: Image.Image | None = None,
) -> list[Detection] | tuple[list[Detection], Verdict]:
    """Segment, filter, merge, measure, and optionally judge.

    Without a judge this is the M2 path and returns score-ordered
    detections. With a judge it also renders the overlay, judges the
    detections, enforces the consistency rule, and returns
    ``(detections, verdict)``.

    ``rules`` replaces ``profile.rules`` for this call only (the
    profile object is never mutated); ``reference`` overrides
    ``profile.reference_image`` for this call, which is otherwise
    loaded from disk when set.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    raw_masks = segmenter.segment(image, profile.defect_prompts)
    kept = [m for m in raw_masks if m.score >= profile.min_score]
    decoded = _decode_valid_masks(kept, width, height)
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
    verdict = judge.judge(
        image, overlay, effective_reference, detections, effective_profile
    )
    return detections, enforce_consistency(verdict)


def inspect_image(
    image_path: str | Path, profile_name: str, segmenter: Segmenter
) -> list[Detection]:
    """Load image + named profile from disk, then run the inspection."""
    image = Image.open(image_path).convert("RGB")
    profile = load_profile(profile_name)
    return run_inspection(image, profile, segmenter)
