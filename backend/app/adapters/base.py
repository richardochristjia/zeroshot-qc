"""Adapter protocols (HANDOFF §5, verbatim) plus shared adapter errors."""

import base64
import io
from typing import Protocol
from urllib.parse import urlsplit

from PIL import Image

from app.config import settings
from app.schemas import Detection, ProductProfile, RawMask, Verdict


class AdapterNotConfiguredError(RuntimeError):
    """Raised by a real adapter before any HTTP when required settings are empty."""


def encode_image_b64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def require_configured(*, model_id: str, model_field: str, adapter: str) -> None:
    if not settings.meta_api_key or not settings.meta_api_base_url or not model_id:
        raise AdapterNotConfiguredError(
            f"{adapter} adapter is not configured: META_API_KEY, META_API_BASE_URL "
            f"and {model_field} must all be set."
        )
    if urlsplit(settings.meta_api_base_url).scheme != "https":
        raise AdapterNotConfiguredError(
            f"{adapter} adapter is not configured: META_API_BASE_URL must use https."
        )


class Segmenter(Protocol):
    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        """Return one RawMask per instance found, for every prompt."""


class Judge(Protocol):
    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict: ...

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile: ...


class ImageGenerator(Protocol):
    def add_defect(
        self, good_image: Image.Image, defect_description: str, mask: Image.Image | None
    ) -> Image.Image:
        """Edit a good image to add a defect. Use inpainting with `mask` if Muse Image
        supports it; otherwise fall back to an image-edit prompt and return mask=None."""
