"""Labeled overlay renderer (M2 Overlay phase).

One function: an image plus ``Detection``s becomes a labeled PIL image.
The caller saves it — output naming stays in the callers, not here.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.pipeline.measure import decode_rle_for_image
from app.schemas import Detection

_TINT_COLORS: dict[str, tuple[int, int, int]] = {
    "scratch": (255, 80, 80),
    "crack": (80, 200, 80),
    "dent": (80, 120, 255),
}

_FALLBACK_COLOR = (255, 200, 0)


def make_overlay(image: Image.Image, detections: list[Detection]) -> Image.Image:
    """Tint each detection's mask and stamp ``id`` + label near its bbox origin.

    Per-label tint reuses the smoke palette, looked up on the full label
    string (merged ``"a+b"`` labels hit the fallback). Detections whose
    RLE is undecodable or decodes to a shape other than the image are
    skipped with a warning. An empty list yields the unmarked image.
    """
    base = image.convert("RGB")
    width, height = base.size
    overlay_arr = np.array(base, dtype=np.float32)
    drawn: list[Detection] = []
    for det in detections:
        binary = decode_rle_for_image(
            det.mask_rle, width, height, f"detection {det.id!r} ({det.label!r})"
        )
        if binary is None:
            continue
        sel = binary.astype(bool)
        if sel.any():
            tint = np.array(
                _TINT_COLORS.get(det.label, _FALLBACK_COLOR), dtype=np.float32
            )
            overlay_arr[sel] = overlay_arr[sel] * 0.45 + tint * 0.55
        drawn.append(det)
    overlay = Image.fromarray(
        np.clip(overlay_arr, 0, 255).astype(np.uint8), mode="RGB"
    )
    if drawn:
        font = ImageFont.load_default()
        draw = ImageDraw.Draw(overlay)
        for det in drawn:
            x, y, _, _ = det.bbox
            tx = min(max(int(x), 0), max(width - 1, 0))
            ty = min(max(int(y), 0), max(height - 1, 0))
            draw.text(
                (tx, ty),
                f"{det.id} {det.label}",
                font=font,
                fill=(255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0),
            )
    return overlay
