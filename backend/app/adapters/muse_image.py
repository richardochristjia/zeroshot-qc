"""Muse Image generator adapter via the Meta Model API (real HTTP).

The request mapping follows the Meta docs pasted for the manual
checks: one-off edits go to ``POST {base}/images/edits`` as multipart
(image, optional mask, prompt, model); the reply is expected to carry
base64 image bytes.
"""

import base64
import io

import httpx
from PIL import Image

from app.adapters.base import require_configured
from app.config import settings


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _extract_image_b64(data: object) -> str:
    """Find base64 image bytes in an images-endpoint reply.

    Accepts a bare base64 string, a dict holding it under a common key,
    or a ``{"data": [{"b64_json": ...}]}`` list shape.
    """

    if isinstance(data, str) and len(data) > 100:
        return data
    if isinstance(data, dict):
        for key in ("b64_json", "image", "image_base64", "base64"):
            value = data.get(key)
            if isinstance(value, str) and len(value) > 100:
                return value
        items = data.get("data")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return _extract_image_b64(items[0])
    return ""


class MuseImageGenerator:
    """ImageGenerator backed by Muse Image over the Meta Model API."""

    def add_defect(
        self, good_image: Image.Image, defect_description: str, mask: Image.Image | None
    ) -> Image.Image:
        require_configured(
            model_id=settings.image_model_id, model_field="IMAGE_MODEL_ID", adapter="Image"
        )
        return self._add_defect_via_meta_api(good_image, defect_description, mask)

    def _add_defect_via_meta_api(
        self, good_image: Image.Image, defect_description: str, mask: Image.Image | None
    ) -> Image.Image:
        # Single-shot edit per the Meta docs pasted for the manual
        # checks (Muse Image one-off calls go to /v1/images/edits).
        # Field names follow that endpoint's standard multipart shape.
        url = settings.meta_api_base_url.rstrip("/") + "/images/edits"
        files = {"image": ("image.png", _png_bytes(good_image), "image/png")}
        if mask is not None:
            files["mask"] = ("mask.png", _png_bytes(mask), "image/png")
        form = {"model": settings.image_model_id, "prompt": defect_description}
        # TODO(meta-docs): auth scheme — bearer key header assumed.
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(
            url, files=files, data=form, headers=headers, timeout=180.0
        )
        response.raise_for_status()
        image_b64 = _extract_image_b64(response.json())
        if not image_b64:
            raise RuntimeError(
                "image-edit response carried no recognizable base64 image."
            )
        return Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
