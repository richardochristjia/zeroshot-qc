"""Muse Spark judge adapter via the Meta Model API (real HTTP).

Only ``judge`` is implemented in M1. The Meta request/response mapping
for it lives entirely in ``MuseSparkJudge._judge_via_meta_api`` so it
can be corrected in one place when the official Meta Model API docs
arrive (HANDOFF §2); every uncertain detail there is marked
TODO(meta-docs) and built only from the shared settings values.
``sop_to_profile`` is an explicit M5 stub (plan: SOP parsing lands M5).
"""

import base64
import io

import httpx
from PIL import Image

from app.adapters.base import AdapterNotConfiguredError
from app.config import settings
from app.schemas import Detection, ProductProfile, Verdict


class MuseSparkJudge:
    """Judge backed by Muse Spark over the Meta Model API."""

    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        if not settings.meta_api_key or not settings.meta_api_base_url or not settings.judge_model_id:
            raise AdapterNotConfiguredError(
                "Judge adapter is not configured: META_API_KEY, META_API_BASE_URL "
                "and JUDGE_MODEL_ID must all be set."
            )
        return self._judge_via_meta_api(image, overlay, reference, detections, profile)

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        # M5: SOP-to-profile parsing lands in M5; no behaviour in M1.
        raise NotImplementedError("sop_to_profile is not implemented until M5")

    def _judge_via_meta_api(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        # TODO(meta-docs): everything in this function is a placeholder
        # mapping to be corrected against the official Meta Model API
        # docs. Do not treat the endpoint, payload shape, auth scheme,
        # image encoding, structured-output mode, or response shape
        # below as fact.
        # TODO(meta-docs): endpoint path — the base URL from settings is
        # used verbatim until the docs name the judge path.
        url = settings.meta_api_base_url

        def _encode(img: Image.Image) -> str:
            # TODO(meta-docs): image encoding — PNG bytes, base64 text.
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("ascii")

        # TODO(meta-docs): request payload shape and field names,
        # including how images, detections, and rules are passed and
        # whether a structured-output / JSON mode exists.
        payload = {
            "model": settings.judge_model_id,
            "image": _encode(image),
            "overlay": _encode(overlay),
            "reference": _encode(reference) if reference is not None else None,
            "detections": [d.model_dump() for d in detections],
            "profile": profile.model_dump(),
        }
        # TODO(meta-docs): auth scheme — bearer key header assumed.
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        # TODO(meta-docs): response shape — a Verdict JSON object,
        # possibly nested under a result/verdict key, is assumed.
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("verdict"), dict):
            data = data["verdict"]
        return Verdict.model_validate(data)
