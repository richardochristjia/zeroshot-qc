"""Pure mask measurement functions (M2 Measure phase).

Every size number in later surfaces comes from here. No config, no I/O:
decode a COCO RLE dict, count pixels, and derive geometry with OpenCV.
"""

import warnings

import cv2
import numpy as np
from pycocotools import mask as mask_api

# Absolute worst-case decode size: a single mask declaring more pixels
# than this is rejected before pycocotools allocates it. Backstop for
# callers that cannot pre-validate against image dims (e.g. smoke
# measuring); 100 MP is far above any inspection image.
MAX_RLE_PIXELS = 100_000_000


def declared_rle_size(mask_rle: dict) -> tuple[int, int] | None:
    """Declared ``(height, width)`` from an RLE dict's ``size`` field.

    Returns ``None`` when the field is missing or unreadable, so callers
    fall through to the normal decode path (which raises a catchable
    error downstream).
    """
    if not isinstance(mask_rle, dict):
        return None
    size = mask_rle.get("size")
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        return None
    try:
        return (int(size[0]), int(size[1]))
    except (TypeError, ValueError):
        return None


def decode_rle(mask_rle: dict) -> np.ndarray:
    """Decode a COCO RLE dict to a binary (H, W) uint8 array.

    Accepts the JSON-safe text form of ``counts`` (as stored by the fake
    segmenter and the cache path) as well as raw bytes. Masks declaring
    more than ``MAX_RLE_PIXELS`` raise ``ValueError`` before decoding.
    """
    declared = declared_rle_size(mask_rle)
    if declared is not None and declared[0] * declared[1] > MAX_RLE_PIXELS:
        raise ValueError(
            f"RLE size {list(declared)} exceeds {MAX_RLE_PIXELS}-pixel "
            "cap; refusing to decode"
        )
    rle = {"size": list(mask_rle["size"]), "counts": mask_rle["counts"]}
    if isinstance(rle["counts"], str):
        rle["counts"] = rle["counts"].encode("utf-8")
    return mask_api.decode(rle).astype(np.uint8)


def decode_rle_for_image(
    mask_rle: dict, width: int, height: int, what: str
) -> np.ndarray | None:
    """Decode an RLE validated against image dims; ``None`` when skipped.

    The declared ``size`` is checked before decoding so a giant
    mismatched mask never allocates. Undecodable or mismatched RLE
    warns (naming ``what``) and yields ``None`` instead of raising.
    """
    declared = declared_rle_size(mask_rle)
    if declared is not None and declared != (height, width):
        warnings.warn(
            f"skipping RLE for {what}: declared size "
            f"{list(declared)} != image (height={height}, width={width})"
        )
        return None
    try:
        binary = decode_rle(mask_rle)
    except Exception as exc:
        warnings.warn(f"skipping undecodable RLE for {what}: {exc}")
        return None
    if binary.shape != (height, width):
        warnings.warn(
            f"skipping RLE for {what}: decoded shape "
            f"{tuple(binary.shape)} != image (height={height}, width={width})"
        )
        return None
    return binary


def measure_mask(
    mask_rle: dict, mm_per_px: float | None = None
) -> dict[str, int | float | tuple[int, int, int, int] | None]:
    """Measure one mask: pixel area, longest side, bbox, optional mm sizes.

    ``length_px`` is the longer side of ``cv2.minAreaRect`` over the
    foreground pixels (a point-span measure: a filled 100x50 rect gives
    99.0, not 100.0). ``bbox`` is ``(x, y, w, h)`` ints from
    ``cv2.boundingRect``. ``area_mm2``/``length_mm`` are set only when
    ``mm_per_px`` is given, else ``None``. An empty mask yields zero
    sizes without raising.
    """
    binary = decode_rle(mask_rle)
    area_px = int(binary.sum())
    if area_px == 0:
        bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
        length_px = 0.0
    else:
        x, y, w, h = cv2.boundingRect(binary)
        bbox = (int(x), int(y), int(w), int(h))
        _, (rect_w, rect_h), _ = cv2.minAreaRect(cv2.findNonZero(binary))
        length_px = float(max(rect_w, rect_h))
    if mm_per_px is None:
        area_mm2: float | None = None
        length_mm: float | None = None
    else:
        area_mm2 = area_px * mm_per_px**2
        length_mm = length_px * mm_per_px
    return {
        "area_px": area_px,
        "length_px": length_px,
        "bbox": bbox,
        "area_mm2": area_mm2,
        "length_mm": length_mm,
    }
