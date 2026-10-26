"""Direct HANDOFF section-6 schema contract tests.

Run: cd backend && .venv/bin/python -m pytest tests/test_schemas.py
"""

import pytest
from pydantic import ValidationError

from app.schemas import DefectRuling, Detection, ProductProfile, Verdict


def _verdict_payload(**overrides: object) -> dict:
    payload: dict = {
        "verdict": "PASS",
        "confidence": 0.5,
        "rulings": [],
        "missed_defects": [],
        "summary": "ok",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_verdict_confidence_out_of_range_rejected(confidence: float) -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_payload(confidence=confidence))


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_verdict_confidence_bounds_accepted(confidence: float) -> None:
    verdict = Verdict.model_validate(_verdict_payload(confidence=confidence))
    assert verdict.confidence == confidence


@pytest.mark.parametrize("verdict", ["PASS", "FAIL"])
def test_verdict_literal_accepted(verdict: str) -> None:
    assert Verdict.model_validate(_verdict_payload(verdict=verdict)).verdict == verdict


def test_verdict_literal_rejects_other_values() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_payload(verdict="MAYBE"))


def test_defect_ruling_without_rule_violated_raises() -> None:
    with pytest.raises(ValidationError):
        DefectRuling.model_validate(
            {"detection_id": "d1", "is_real_defect": True, "reason": "x"}
        )


def test_defect_ruling_rule_violated_none_and_string_validate() -> None:
    none_ruling = DefectRuling(
        detection_id="d1", is_real_defect=False, rule_violated=None, reason="glare"
    )
    assert none_ruling.rule_violated is None
    text_ruling = DefectRuling(
        detection_id="d1",
        is_real_defect=True,
        rule_violated="No scratches.",
        reason="scratch seen",
    )
    assert text_ruling.rule_violated == "No scratches."


def test_product_profile_min_score_defaults_to_0_3() -> None:
    profile = ProductProfile(
        id="bottle", name="Bottle", defect_prompts=[], rules="No scratches."
    )
    assert profile.min_score == 0.3


def test_detection_mm_fields_default_to_none() -> None:
    detection = Detection(
        id="d1",
        label="scratch",
        score=0.9,
        bbox=(0, 0, 4, 4),
        mask_rle={"size": [30, 40], "counts": "abc"},
        area_px=16,
        length_px=4.0,
    )
    assert detection.area_mm2 is None
    assert detection.length_mm is None
