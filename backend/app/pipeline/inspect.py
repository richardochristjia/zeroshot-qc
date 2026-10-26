"""Segmentation orchestrator (M2 Inspect phase).

Single flow: load image (RGB) + named profile, segment, drop masks
below ``profile.min_score``, greedily merge duplicates with IoU above
0.5, assign stable ``d1, d2, ...`` ids in score order, measure each.
No judge call in M2.
"""

import json
import warnings
from pathlib import Path

import numpy as np
from PIL import Image
from pycocotools import mask as mask_api

from app.adapters.base import Segmenter
from app.pipeline.measure import decode_rle, measure_mask
from app.schemas import Detection, ProductProfile, RawMask

MERGE_IOU_THRESHOLD = 0.5

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


def load_profile(name: str) -> ProductProfile:
    """Load ``backend/profiles/<name>.json`` and validate as ProductProfile.

    Anchored to this module file so repo-root and ``backend/`` CWDs
    resolve identically.
    """
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
    """Decode masks, skipping undecodable or size-mismatched ones with a warning."""
    valid: list[tuple[RawMask, np.ndarray]] = []
    for mask in masks:
        try:
            binary = decode_rle(mask.mask_rle)
        except Exception as exc:
            warnings.warn(f"skipping undecodable RLE for {mask.label!r}: {exc}")
            continue
        if binary.shape != (height, width):
            warnings.warn(
                f"skipping RLE for {mask.label!r}: decoded shape "
                f"{tuple(binary.shape)} != image (height={height}, width={width})"
            )
            continue
        valid.append((mask, binary))
    return valid


def run_inspection(
    image: Image.Image, profile: ProductProfile, segmenter: Segmenter
) -> list[Detection]:
    """Segment, filter, merge, and measure. Returns score-ordered detections."""
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
    return detections


def inspect_image(
    image_path: str | Path, profile_name: str, segmenter: Segmenter
) -> list[Detection]:
    """Load image + named profile from disk, then run the inspection."""
    image = Image.open(image_path).convert("RGB")
    profile = load_profile(profile_name)
    return run_inspection(image, profile, segmenter)
