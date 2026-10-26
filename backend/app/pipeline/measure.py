"""Pure mask measurement functions (M2 Measure phase).

Every size number in later surfaces comes from here. No config, no I/O:
decode a COCO RLE dict, count pixels, and derive geometry with OpenCV.
"""

import cv2
import numpy as np
from pycocotools import mask as mask_api


def decode_rle(mask_rle: dict) -> np.ndarray:
    """Decode a COCO RLE dict to a binary (H, W) uint8 array.

    Accepts the JSON-safe text form of ``counts`` (as stored by the fake
    segmenter and the cache path) as well as raw bytes.
    """
    rle = {"size": list(mask_rle["size"]), "counts": mask_rle["counts"]}
    if isinstance(rle["counts"], str):
        rle["counts"] = rle["counts"].encode("utf-8")
    return mask_api.decode(rle).astype(np.uint8)


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
