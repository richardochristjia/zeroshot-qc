"""SAM 3.1 adapter via the Meta Model API (real HTTP implementation).

The Meta request/response mapping lives entirely in
``SamSegmenter._segment_via_meta_api`` so it can be corrected in one
place when the official Meta Model API docs arrive (HANDOFF §2).
Nothing about the endpoint, payload, auth, or image encoding is
presented as fact: every uncertain detail is marked TODO(meta-docs)
and built only from the shared settings values.
"""

import base64
import io
from urllib.parse import urlsplit

import httpx
from PIL import Image

from app.adapters.base import AdapterNotConfiguredError
from app.config import settings
from app.schemas import RawMask


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


class SamSegmenter:
    """Segmenter backed by SAM 3.1 over the Meta Model API."""

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        if not settings.meta_api_key or not settings.meta_api_base_url or not settings.sam_model_id:
            raise AdapterNotConfiguredError(
                "SAM adapter is not configured: META_API_KEY, META_API_BASE_URL "
                "and SAM_MODEL_ID must all be set."
            )
        if urlsplit(settings.meta_api_base_url).scheme != "https":
            raise AdapterNotConfiguredError(
                "SAM adapter is not configured: META_API_BASE_URL must use https."
            )
        return self._segment_via_meta_api(image, prompts)

    def _segment_via_meta_api(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        # TODO(meta-docs): everything in this function is a placeholder
        # mapping to be corrected against the official Meta Model API
        # docs. Do not treat the endpoint, payload shape, auth scheme,
        # image encoding, or response shape below as fact.
        # TODO(meta-docs): endpoint path — the base URL from settings is
        # used verbatim until the docs name the segmentation path.
        url = settings.meta_api_base_url
        # TODO(meta-docs): image encoding — PNG bytes, base64 text.
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        # TODO(meta-docs): request payload shape and field names.
        payload = {
            "model": settings.sam_model_id,
            "image": image_b64,
            "prompts": prompts,
        }
        # TODO(meta-docs): auth scheme — bearer key header assumed.
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        # TODO(meta-docs): response shape — a top-level masks list whose
        # entries carry label/score/mask_rle is assumed.
        data = response.json()
        masks = data.get("masks", []) if isinstance(data, dict) else []
        result: list[RawMask] = []
        for entry in masks:
            if not isinstance(entry, dict):
                continue
            try:
                label = str(entry["label"])
                score = float(entry["score"])
                mask_rle = dict(entry["mask_rle"])
            except (KeyError, TypeError, ValueError):
                continue
            if not _is_valid_mask_rle(mask_rle, image.height, image.width):
                continue
            result.append(RawMask(label=label, score=score, mask_rle=mask_rle))
        return result
