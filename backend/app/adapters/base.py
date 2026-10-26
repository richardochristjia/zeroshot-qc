"""Adapter protocols (HANDOFF §5, verbatim) plus shared adapter errors."""

from typing import Protocol

from PIL import Image

from app.schemas import Detection, ProductProfile, RawMask, Verdict


class AdapterNotConfiguredError(RuntimeError):
    """Raised by a real adapter before any HTTP when required settings are empty."""


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
