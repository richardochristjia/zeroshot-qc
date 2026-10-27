"""SAM 3.1 adapter via the Meta Model API (real HTTP implementation).

Request mapping follows the Meta docs pasted for the manual checks:
SAM 3.1 is reached over the Responses API (``POST {base}/responses``)
with the model id ``sam-3.1``; the response carries geometry as text.
The exact geometry JSON keys are still defensive (several candidate
shapes are accepted) because the docs point at the Media segmentation
guide for the full schema: an unparseable reply raises with the raw
text attached so the shape can be pinned from one live response.
"""

import base64
import io
import json

import httpx
import numpy as np
from PIL import Image, ImageDraw
from pycocotools import mask as mask_utils

from app.adapters.base import encode_image_b64, extract_responses_text, require_configured
from app.config import settings
from app.schemas import RawMask

_GEOMETRY_KEYS = ("masks", "results", "detections", "instances", "boxes")


def _is_valid_mask_rle(mask_rle: object, height: int, width: int) -> bool:
    if not isinstance(mask_rle, dict):
        return False
    size = mask_rle.get("size")
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        return False
    if list(size) != [height, width]:
        return False
    counts = mask_rle.get("counts")
    if not isinstance(counts, (str, bytes)):
        return False
    if len(counts) == 0:
        return False
    if len(counts) > max(4096, height * width * 10):
        return False
    return True


def _binary_to_rle(binary: np.ndarray) -> dict:
    encoded = mask_utils.encode(np.asfortranarray(binary.astype(np.uint8)))
    counts = encoded["counts"]
    if isinstance(counts, bytes):
        counts = counts.decode("ascii")
    return {"size": [int(binary.shape[0]), int(binary.shape[1])], "counts": counts}


def _mask_from_base64_png(raw: str, height: int, width: int) -> dict | None:
    try:
        decoded = base64.b64decode(raw)
        with Image.open(io.BytesIO(decoded)) as parsed:
            gray = parsed.convert("L").resize((width, height))
    except Exception:
        return None
    return _binary_to_rle(np.array(gray) > 127)


def _mask_from_polygons(polygons: object, height: int, width: int) -> dict | None:
    if not isinstance(polygons, list) or not polygons:
        return None
    canvas = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(canvas)
    drew = False
    rings = polygons if isinstance(polygons[0], list) else [polygons]
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 6:
            continue
        flat = [float(v) for v in ring]
        if len(flat) % 2:
            continue
        points = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
        draw.polygon(points, fill=1)
        drew = True
    if not drew:
        return None
    return _binary_to_rle(np.array(canvas) > 0)


def _scale_coords(values: list[float], extent: int) -> list[float]:
    if all(abs(v) <= 1.0 for v in values):
        return [v * extent for v in values]
    if max(values) > extent and max(values) <= 1000:
        return [v * extent / 1000.0 for v in values]
    return list(values)


def _box_to_xywh(box: object, width: int, height: int) -> tuple[int, int, int, int] | None:
    if isinstance(box, dict):
        try:
            return (
                int(box["x"]),
                int(box["y"]),
                int(box["w"]),
                int(box["h"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        nums = [float(v) for v in box]
    except (TypeError, ValueError):
        return None
    xs = _scale_coords([nums[0], nums[2]], width)
    ys = _scale_coords([nums[1], nums[3]], height)
    if xs[1] > xs[0] and ys[1] > ys[0]:
        x0, x1, y0, y1 = xs[0], xs[1], ys[0], ys[1]
    else:
        x0, y0 = xs[0], ys[0]
        x1, y1 = xs[0] + xs[1], ys[0] + ys[1]
    x0 = max(0, min(width - 1, int(round(x0))))
    y0 = max(0, min(height - 1, int(round(y0))))
    x1 = max(x0 + 1, min(width, int(round(x1))))
    y1 = max(y0 + 1, min(height, int(round(y1))))
    return (x0, y0, x1 - x0, y1 - y0)


def _mask_from_box(box: tuple[int, int, int, int], width: int, height: int) -> dict:
    x, y, w, h = box
    binary = np.zeros((height, width), dtype=np.uint8)
    binary[y : y + h, x : x + w] = 1
    return _binary_to_rle(binary)


def _entries_from_text(text: str) -> list[dict] | None:
    """Parse geometry entries, or None when the shape is unrecognized.

    An explicitly empty answer (``[]`` or an empty candidate list) is a
    valid no-detections result, not an unknown shape.
    """

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, list):
        return [e for e in parsed if isinstance(e, dict)]
    if isinstance(parsed, dict):
        for key in _GEOMETRY_KEYS:
            value = parsed.get(key)
            if isinstance(value, list):
                return [e for e in value if isinstance(e, dict)]
        if not parsed:
            return []
    return None


class SamSegmenter:
    """Segmenter backed by SAM 3.1 over the Meta Model API."""

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        require_configured(model_id=settings.sam_model_id, model_field="SAM_MODEL_ID", adapter="SAM")
        return self._segment_via_meta_api(image, prompts)

    def _segment_via_meta_api(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        url = settings.meta_api_base_url.rstrip("/") + "/responses"
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        image_url = "data:image/png;base64," + encode_image_b64(image)
        content: list[dict] = [{"type": "input_image", "image_url": image_url}]
        for prompt in prompts:
            content.append(
                {"type": "input_text", "text": f"Segment every instance of: {prompt}"}
            )
        payload = {
            "model": settings.sam_model_id,
            "input": [{"role": "user", "content": content}],
        }
        response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        response.raise_for_status()
        data = response.json()
        return self._parse_geometries(data, prompts, image.width, image.height)

    @staticmethod
    def _parse_geometries(
        data: object, prompts: list[str], width: int, height: int
    ) -> list[RawMask]:
        text = extract_responses_text(data).strip()
        if not text:
            return []
        entries = _entries_from_text(text)
        if entries is None:
            raise RuntimeError(
                "SAM response text did not match any known geometry shape; "
                f"raw text (truncated): {text[:2000]}"
            )
        result: list[RawMask] = []
        for entry in entries:
            try:
                score = float(entry.get("score", 1.0))
            except (TypeError, ValueError):
                continue
            label = str(entry.get("label", entry.get("prompt", prompts[0] if prompts else "defect")))
            mask_rle: object | None = None
            raw_mask = entry.get("mask_rle", entry.get("mask", entry.get("polygon")))
            if isinstance(raw_mask, dict) and "counts" in raw_mask:
                counts = raw_mask.get("counts")
                if isinstance(counts, bytes):
                    raw_mask = {**raw_mask, "counts": counts.decode("ascii")}
                if _is_valid_mask_rle(raw_mask, height, width):
                    mask_rle = raw_mask
            elif isinstance(raw_mask, str):
                mask_rle = _mask_from_base64_png(raw_mask, height, width)
            elif isinstance(raw_mask, list):
                mask_rle = _mask_from_polygons(raw_mask, height, width)
            box = _box_to_xywh(entry.get("box", entry.get("bbox")), width, height)
            if mask_rle is None and box is not None:
                mask_rle = _mask_from_box(box, width, height)
            if mask_rle is None:
                continue
            if box is None:
                box = (0, 0, width, height)
            result.append(RawMask(label=label, score=score, mask_rle=mask_rle))
        return result
