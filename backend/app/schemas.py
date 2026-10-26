"""All Pydantic models (HANDOFF §6), verbatim."""

from typing import Literal

from pydantic import BaseModel, Field


class RawMask(BaseModel):
    label: str  # the prompt that produced it
    score: float
    mask_rle: dict  # COCO RLE


class Detection(BaseModel):
    id: str  # "d1", "d2", ... stable within one inspection
    label: str
    score: float
    bbox: tuple[int, int, int, int]  # x, y, w, h in px
    mask_rle: dict
    area_px: int
    length_px: float  # longest side of min-area rotated rect
    area_mm2: float | None = None
    length_mm: float | None = None


class ProductProfile(BaseModel):
    id: str  # e.g. "bottle"
    name: str
    defect_prompts: list[str]  # fed to SAM 3.1
    rules: str  # plain English, shown to the judge verbatim
    mm_per_px: float | None = None
    min_score: float = 0.3  # drop SAM detections below this
    reference_image: str | None = None  # path to a known-good image


class DefectRuling(BaseModel):
    detection_id: str
    is_real_defect: bool  # false = glare, texture, shadow, etc.
    rule_violated: str | None  # quote the rule, or null
    reason: str


class Verdict(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    confidence: float = Field(ge=0, le=1)
    rulings: list[DefectRuling]
    missed_defects: list[str]  # defects the judge sees that SAM did not flag
    summary: str  # 1–2 sentences for the UI


class InspectionResult(BaseModel):
    id: str
    profile_id: str
    detections: list[Detection]
    verdict: Verdict
    overlay_url: str
    timings_ms: dict[str, int]  # segment, judge, total
