"""All Pydantic models (HANDOFF §6), verbatim."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    source: Literal["sam", "judge"] = "sam"


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


class MissedDefect(BaseModel):
    description: str
    box: list[float] | None = None  # x1, y1, x2, y2 in 0-1000 judged-image coordinates

    @field_validator("box", mode="before")
    @classmethod
    def _malformed_box_is_none(cls, value):
        # A box the judge garbled keeps the description and drops the location.
        try:
            return [float(v) for v in value] if value is not None else None
        except (TypeError, ValueError):
            return None


class Verdict(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    confidence: float = Field(ge=0, le=1)
    rulings: list[DefectRuling]
    missed_defects: list[MissedDefect]  # defects the judge sees that SAM did not flag
    part_matches: bool  # false = not the profile's product
    summary: str  # 1–2 sentences for the UI

    @field_validator("missed_defects", mode="before")
    @classmethod
    def _plain_strings(cls, value):
        # Old recorded verdicts stored bare strings.
        if isinstance(value, list):
            return [{"description": v} if isinstance(v, str) else v for v in value]
        return value


class RuleRevision(BaseModel):
    rules: str
    rationale: str = ""


class InspectionResult(BaseModel):
    id: str
    profile_id: str
    detections: list[Detection]
    verdict: Verdict
    overlay_url: str
    timings_ms: dict[str, int]  # segment, judge, total
    demo: bool = False  # placeholder models answered (no API key, cache miss)
