"""Muse Spark judge adapter via the Meta Model API (real HTTP).

The Meta request/response mapping for ``judge`` lives entirely in
``MuseSparkJudge._judge_via_meta_api``: Responses API, bearer key,
images as base64 PNG data URLs. Confirmed against the live API
(2026-10-27 inspect walkthrough, 2026-10-28 SOP draft).
M5: ``sop_to_profile`` drafts a profile with the judge's retry-once
validation pattern via ``prompts/sop_to_profile.md``.

M3: ``judge`` renders the HANDOFF §7 prompt, validates the response
against ``Verdict``, retries once with the validation error appended,
and raises ``JudgeValidationError`` on the second failure.
"""

import json
import re

import httpx
from PIL import Image
from pydantic import ValidationError

from app.adapters.base import (
    encode_image_b64,
    extract_responses_text,
    require_configured,
)
from app.config import settings
from app.prompts import render_judge_prompt, render_sop_prompt
from app.schemas import Detection, ProductProfile, Verdict


def _responses_payload(model_id: str, prompt: str, images: list[Image.Image]) -> dict:
    """Build a Responses API ``POST {base}/responses`` payload.

    Follows the Meta docs pasted for the manual checks: Muse Spark is
    reached over the Responses API with text plus image input parts.
    """

    content: list[dict] = [{"type": "input_text", "text": prompt}]
    for image in images:
        content.append(
            {
                "type": "input_image",
                "image_url": "data:image/png;base64," + encode_image_b64(image),
            }
        )
    return {"model": model_id, "input": [{"role": "user", "content": content}]}


def _verdict_json(data: object) -> object:
    """Extract the JSON object from a Responses envelope.

    Returns ``{"_raw": text}`` when the output text is not JSON so
    Verdict validation fails (and the retry path engages) instead of
    raising a raw decode error the caller cannot recover from.
    """

    text = extract_responses_text(data).strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"_raw": text[:2000]}
    if isinstance(parsed, dict) and isinstance(parsed.get("verdict"), dict):
        return parsed["verdict"]
    return parsed


def _slugify_category(category_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", category_name.strip().lower()).strip("_")
    return slug or "product"


class JudgeValidationError(ValueError):
    """Both judge attempts returned output that failed Verdict validation."""


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
        prompt = render_judge_prompt(profile.rules, detections)
        try:
            data = self._judge_via_meta_api(
                image, overlay, reference, detections, profile, prompt
            )
            return Verdict.model_validate(data)
        except ValidationError as first_error:
            retry_prompt = (
                f"{prompt}\n\nYour previous response failed validation:\n"
                f"{first_error}\nReturn only JSON matching the schema."
            )
            try:
                data = self._judge_via_meta_api(
                    image, overlay, reference, detections, profile, retry_prompt
                )
                return Verdict.model_validate(data)
            except ValidationError as second_error:
                raise JudgeValidationError(
                    "judge output failed Verdict validation twice: "
                    f"{second_error}"
                ) from second_error

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        """Draft a ProductProfile from an SOP paragraph (M5).

        Same retry-once validation pattern as :meth:`judge`: a first
        failure reruns with the validation error appended, a second
        raises :class:`JudgeValidationError`. Never saves anything.
        """
        require_configured(
            model_id=settings.judge_model_id,
            model_field="JUDGE_MODEL_ID",
            adapter="Judge",
        )
        prompt = render_sop_prompt(sop_text, category_name)
        try:
            return self._validate_profile(
                self._sop_via_meta_api(prompt), category_name
            )
        except ValidationError as first_error:
            retry_prompt = (
                f"{prompt}\n\nYour previous response failed validation:\n"
                f"{first_error}\nReturn only JSON matching the schema."
            )
            try:
                return self._validate_profile(
                    self._sop_via_meta_api(retry_prompt), category_name
                )
            except ValidationError as second_error:
                raise JudgeValidationError(
                    "sop_to_profile output failed ProductProfile "
                    f"validation twice: {second_error}"
                ) from second_error

    @staticmethod
    def _validate_profile(data: object, category_name: str) -> ProductProfile:
        profile = ProductProfile.model_validate(data)
        if not profile.id.strip():
            profile = profile.model_copy(
                update={
                    "id": _slugify_category(category_name),
                    "name": category_name,
                }
            )
        return profile

    def _sop_via_meta_api(self, prompt: str) -> object:
        url = settings.meta_api_base_url.rstrip("/") + "/responses"
        payload = _responses_payload(settings.judge_model_id, prompt, [])
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("profile"), dict):
            return data["profile"]
        return _verdict_json(data)

    def _judge_via_meta_api(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
        prompt: str,
    ) -> object:
        url = settings.meta_api_base_url.rstrip("/") + "/responses"
        images = [image, overlay]
        if reference is not None:
            images.append(reference)
        payload = _responses_payload(settings.judge_model_id, prompt, images)
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        response.raise_for_status()
        return _verdict_json(response.json())
