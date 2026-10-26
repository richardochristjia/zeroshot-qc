"""Muse Image generator adapter via the Meta Model API (real HTTP).

Present but unexercised in M1 (first exercised in M5). The Meta
request/response mapping lives entirely in
``MuseImageGenerator._add_defect_via_meta_api`` so it can be corrected
in one place when the official Meta Model API docs arrive (HANDOFF §2);
every uncertain detail there is marked TODO(meta-docs) and built only
from the shared settings values.
"""

import base64
import io

import httpx
from PIL import Image

from app.adapters.base import encode_image_b64, require_configured
from app.config import settings


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
        # TODO(meta-docs): everything in this function is a placeholder
        # mapping to be corrected against the official Meta Model API
        # docs. Do not treat the endpoint, payload shape, auth scheme,
        # image encoding, inpainting support, or response shape below
        # as fact.
        # TODO(meta-docs): endpoint path — the base URL from settings is
        # used verbatim until the docs name the image-edit path.
        url = settings.meta_api_base_url

        # TODO(meta-docs): request payload shape and field names,
        # including whether inpainting with `mask` is supported.
        payload = {
            "model": settings.image_model_id,
            "image": encode_image_b64(good_image),
            "mask": encode_image_b64(mask) if mask is not None else None,
            "defect_description": defect_description,
        }
        # TODO(meta-docs): auth scheme — bearer key header assumed.
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        # TODO(meta-docs): response shape — base64 image text under an
        # image key is assumed.
        data = response.json()
        image_b64 = data["image"] if isinstance(data, dict) else ""
        return Image.open(io.BytesIO(base64.b64decode(image_b64)))
