"""Muse Spark judge adapter via the Meta Model API (real HTTP).

Only ``judge`` is implemented in M1. The Meta request/response mapping
for it lives entirely in ``MuseSparkJudge._judge_via_meta_api`` so it
can be corrected in one place when the official Meta Model API docs
arrive (HANDOFF §2); every uncertain detail there is marked
TODO(meta-docs) and built only from the shared settings values.
``sop_to_profile`` is an explicit M5 stub (plan: SOP parsing lands M5).
"""

import httpx
from PIL import Image

from app.adapters.base import encode_image_b64, require_configured
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
        require_configured(
            model_id=settings.judge_model_id, model_field="JUDGE_MODEL_ID", adapter="Judge"
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

        # TODO(meta-docs): request payload shape and field names,
        # including how images, detections, and rules are passed and
        # whether a structured-output / JSON mode exists.
        payload = {
            "model": settings.judge_model_id,
            "image": encode_image_b64(image),
            "overlay": encode_image_b64(overlay),
            "reference": encode_image_b64(reference) if reference is not None else None,
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
