"""Muse Spark judge adapter via the Meta Model API (real HTTP).

Only ``judge`` is implemented in M1. The Meta request/response mapping
for it lives entirely in ``MuseSparkJudge._judge_via_meta_api`` so it
can be corrected in one place when the official Meta Model API docs
arrive (HANDOFF §2); every uncertain detail there is marked
TODO(meta-docs) and built only from the shared settings values.
M5: ``sop_to_profile`` drafts a profile with the judge's retry-once
validation pattern via ``prompts/sop_to_profile.md``.

M3: ``judge`` renders the HANDOFF §7 prompt, validates the response
against ``Verdict``, retries once with the validation error appended,
and raises ``JudgeValidationError`` on the second failure.
"""

import re

import httpx
from PIL import Image
from pydantic import ValidationError

from app.adapters.base import encode_image_b64, require_configured
from app.config import settings
from app.prompts import render_judge_prompt, render_sop_prompt
from app.schemas import Detection, ProductProfile, Verdict


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
        # TODO(meta-docs): everything in this function is a placeholder
        # mapping to be corrected against the official Meta Model API
        # docs. Do not treat the endpoint, payload shape, auth scheme,
        # structured-output mode, or response shape below as fact.
        # TODO(meta-docs): endpoint path — the base URL from settings is
        # used verbatim until the docs name the SOP parsing path.
        url = settings.meta_api_base_url

        # TODO(meta-docs): request payload shape and field names, and
        # whether a structured-output / JSON mode exists.
        payload = {
            "model": settings.judge_model_id,
            "prompt": prompt,
        }
        # TODO(meta-docs): auth scheme — Bearer [REDACTED] header assumed.
        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        # TODO(meta-docs): response shape — a ProductProfile JSON object,
        # possibly nested under a result/profile key, is assumed.
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("profile"), dict):
            data = data["profile"]
        return data

    def _judge_via_meta_api(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
        prompt: str,
    ) -> object:
        # TODO(meta-docs): everything in this function is a placeholder
        # mapping to be corrected against the official Meta Model API
        # docs. Do not treat the endpoint, payload shape, auth scheme,
        # image encoding, structured-output mode, or response shape
        # below as fact.
        # TODO(meta-docs): endpoint path — the base URL from settings is
        # used verbatim until the docs name the judge path.
        url = settings.meta_api_base_url

        # TODO(meta-docs): request payload shape and field names,
        # including how images, prompt, detections, and rules are
        # passed and whether a structured-output / JSON mode exists.
        payload = {
            "model": settings.judge_model_id,
            "prompt": prompt,
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
        return data
