"""Judge tests (M3): scripted-rules flip, retry paths, consistency
forcing, reference handling, and judge-cache behavior on rule edits.

Run: cd backend && .venv/bin/python -m pytest -q
"""

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.adapters.fakes import FakeJudge, FakeSegmenter
from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge
from app.config import settings
from app.pipeline.cache import CachedJudge, DiskCache
from app.pipeline.inspect import enforce_consistency, run_inspection
from app.prompts import build_detections_table, render_judge_prompt
from app.schemas import (
    DefectRuling,
    Detection,
    ProductProfile,
    RawMask,
    Verdict,
)

IMAGE_W, IMAGE_H = 40, 30
PROMPTS = ["scratch", "crack"]
STRICT_RULES = "FAIL any scratch or crack."
LENIENT_RULES = "Lenient: minor scratches are acceptable."
JUDGE_MODEL = "judge-model-under-test"


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (IMAGE_W, IMAGE_H), color=(120, 120, 120))


@pytest.fixture
def profile() -> ProductProfile:
    return ProductProfile(
        id="bottle",
        name="Bottle",
        defect_prompts=PROMPTS,
        rules=STRICT_RULES,
    )


def _detections(image: Image.Image) -> list[Detection]:
    masks = FakeSegmenter().segment(image, PROMPTS)
    return [
        Detection(
            id=f"d{i + 1}",
            label=mask.label,
            score=mask.score,
            bbox=(0, 0, 4, 4),
            mask_rle=mask.mask_rle,
            area_px=16,
            length_px=4.0,
        )
        for i, mask in enumerate(masks)
    ]


class StubSegmenter:
    """Fixed mask list so the flip tests control detections exactly."""

    def __init__(self, masks: list[RawMask]) -> None:
        self._masks = masks

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        return list(self._masks)


class StubJudge:
    """Fixed verdict plus capture of what the pipeline passed in."""

    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict
        self.seen_reference: Image.Image | None | str = "unset"
        self.seen_rules: str | None = None

    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        self.seen_reference = reference
        self.seen_rules = profile.rules
        return self._verdict

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        raise NotImplementedError


def _pass_verdict() -> Verdict:
    return Verdict(
        verdict="PASS",
        confidence=0.9,
        rulings=[],
        missed_defects=[],
        summary="stub: pass",
    )


# Scripted-rules flip


def test_fake_judge_strict_rules_fail_first_candidate(
    image: Image.Image, profile: ProductProfile
) -> None:
    detections = _detections(image)
    verdict = FakeJudge().judge(image, image, None, detections, profile)
    assert verdict.verdict == "FAIL"
    assert verdict.rulings[0].detection_id == "d1"
    assert verdict.rulings[0].is_real_defect is True
    assert verdict.rulings[0].rule_violated == STRICT_RULES
    assert all(
        ruling.is_real_defect is False for ruling in verdict.rulings[1:]
    )


def test_fake_judge_lenient_rules_pass_same_detections(
    image: Image.Image, profile: ProductProfile
) -> None:
    detections = _detections(image)
    lenient = profile.model_copy(update={"rules": LENIENT_RULES})
    verdict = FakeJudge().judge(image, image, None, detections, lenient)
    assert verdict.verdict == "PASS"
    assert all(
        ruling.is_real_defect is False for ruling in verdict.rulings
    )


def test_rules_override_flips_pipeline_verdict_without_mutating_profile(
    image: Image.Image, profile: ProductProfile
) -> None:
    masks = FakeSegmenter().segment(image, PROMPTS)
    segmenter = StubSegmenter(masks)
    _, strict = run_inspection(image, profile, segmenter, judge=FakeJudge())
    assert strict.verdict == "FAIL"
    _, flipped = run_inspection(
        image, profile, segmenter, judge=FakeJudge(), rules=LENIENT_RULES
    )
    assert flipped.verdict == "PASS"
    assert profile.rules == STRICT_RULES


def test_fake_judge_empty_detections_passes(
    image: Image.Image, profile: ProductProfile
) -> None:
    verdict = FakeJudge().judge(image, image, None, [], profile)
    assert verdict.verdict == "PASS"
    assert verdict.rulings == []


# Retry paths


class _StubResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def _responses_envelope(payload: dict) -> dict:
    return {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(payload)}],
            }
        ]
    }


def _request_text(call_json: dict) -> str:
    parts = call_json.get("input", [{}])[0].get("content", [])
    return "\n".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("type") == "input_text"
    )


@pytest.fixture
def configured_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "meta_api_key", "test-key")
    monkeypatch.setattr(settings, "meta_api_base_url", "https://example.test/meta")
    monkeypatch.setattr(settings, "judge_model_id", JUDGE_MODEL)


def _valid_payload() -> dict:
    return {
        "verdict": "PASS",
        "confidence": 0.8,
        "rulings": [],
        "missed_defects": [],
        "summary": "ok",
    }


def _malformed_payload() -> dict:
    payload = _valid_payload()
    payload["confidence"] = 99  # violates ge=0, le=1
    return payload


def test_malformed_first_response_retries_once_then_validates(
    image: Image.Image,
    profile: ProductProfile,
    configured_judge: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    payloads = [_malformed_payload(), _valid_payload()]

    def _stub(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs.get("json") or {})
        return _StubResponse(_responses_envelope(payloads[len(calls) - 1]))

    monkeypatch.setattr(httpx, "post", _stub)
    verdict = MuseSparkJudge().judge(image, image, None, [], profile)
    assert verdict == Verdict.model_validate(_valid_payload())
    assert len(calls) == 2
    assert "failed validation" in _request_text(calls[1])
    assert STRICT_RULES in _request_text(calls[0])


def test_malformed_twice_raises_judge_validation_error(
    image: Image.Image,
    profile: ProductProfile,
    configured_judge: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []

    def _stub(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return _StubResponse(_responses_envelope(_malformed_payload()))

    monkeypatch.setattr(httpx, "post", _stub)
    with pytest.raises(JudgeValidationError, match="failed Verdict validation"):
        MuseSparkJudge().judge(image, image, None, [], profile)
    assert len(calls) == 2  # exactly one retry, never a loop


# Consistency rule (code, not prompt)


def test_real_defect_ruling_with_model_pass_forces_fail() -> None:
    model_says_pass = Verdict(
        verdict="PASS",
        confidence=0.9,
        rulings=[
            DefectRuling(
                detection_id="d1",
                is_real_defect=True,
                rule_violated="No scratches.",
                reason="a scratch",
            )
        ],
        missed_defects=[],
        summary="model wrongly passed",
    )
    forced = enforce_consistency(model_says_pass)
    assert forced.verdict == "FAIL"
    assert forced.rulings == model_says_pass.rulings


def test_missed_defects_with_model_pass_forces_fail() -> None:
    model_says_pass = Verdict(
        verdict="PASS",
        confidence=0.9,
        rulings=[],
        missed_defects=["unoutlined crack near the rim"],
        summary="model wrongly passed",
    )
    assert enforce_consistency(model_says_pass).verdict == "FAIL"


def test_real_defect_without_cited_rule_keeps_model_pass() -> None:
    uncovered = Verdict(
        verdict="PASS",
        confidence=0.9,
        rulings=[
            DefectRuling(
                detection_id="d1",
                is_real_defect=True,
                rule_violated=None,
                reason="real but no rule covers it",
            )
        ],
        missed_defects=[],
        summary="no rule covers it",
    )
    assert enforce_consistency(uncovered).verdict == "PASS"


def test_pipeline_forces_fail_on_model_pass_with_violation(
    image: Image.Image, profile: ProductProfile
) -> None:
    masks = FakeSegmenter().segment(image, PROMPTS)
    lying = Verdict(
        verdict="PASS",
        confidence=0.9,
        rulings=[
            DefectRuling(
                detection_id="d1",
                is_real_defect=True,
                rule_violated=STRICT_RULES,
                reason="model says pass anyway",
            )
        ],
        missed_defects=[],
        summary="model pass",
    )
    _, verdict = run_inspection(
        image, profile, StubSegmenter(masks), judge=StubJudge(lying)
    )
    assert verdict.verdict == "FAIL"


# Reference handling


def test_reference_present_and_absent_both_validate(
    image: Image.Image, profile: ProductProfile
) -> None:
    masks = FakeSegmenter().segment(image, PROMPTS)
    judge = StubJudge(_pass_verdict())
    _, without = run_inspection(
        image, profile, StubSegmenter(masks), judge=judge
    )
    assert Verdict.model_validate(without.model_dump()).verdict == "PASS"
    assert judge.seen_reference is None
    reference = Image.new("RGB", (IMAGE_W, IMAGE_H), color=(10, 200, 10))
    _, with_ref = run_inspection(
        image, profile, StubSegmenter(masks), judge=judge, reference=reference
    )
    assert Verdict.model_validate(with_ref.model_dump()).verdict == "PASS"
    assert judge.seen_reference is reference


def test_profile_reference_image_loads_from_disk(
    image: Image.Image, profile: ProductProfile, tmp_path: Path
) -> None:
    ref_path = tmp_path / "good.png"
    Image.new("RGB", (IMAGE_W, IMAGE_H), color=(10, 200, 10)).save(ref_path)
    on_disk = profile.model_copy(update={"reference_image": str(ref_path)})
    judge = StubJudge(_pass_verdict())
    run_inspection(image, on_disk, StubSegmenter([]), judge=judge)
    assert isinstance(judge.seen_reference, Image.Image)


def test_reference_override_wins_over_profile_reference(
    image: Image.Image, profile: ProductProfile, tmp_path: Path
) -> None:
    ref_path = tmp_path / "good.png"
    Image.new("RGB", (IMAGE_W, IMAGE_H), color=(10, 200, 10)).save(ref_path)
    on_disk = profile.model_copy(update={"reference_image": str(ref_path)})
    override = Image.new("RGB", (IMAGE_W, IMAGE_H), color=(200, 10, 10))
    judge = StubJudge(_pass_verdict())
    run_inspection(
        image, on_disk, StubSegmenter([]), judge=judge, reference=override
    )
    assert judge.seen_reference is override


def test_missing_profile_reference_image_raises_value_error(
    image: Image.Image, profile: ProductProfile, tmp_path: Path
) -> None:
    on_disk = profile.model_copy(
        update={"reference_image": str(tmp_path / "absent.png")}
    )
    with pytest.raises(ValueError, match="could not open reference image"):
        run_inspection(
            image, on_disk, StubSegmenter([]), judge=StubJudge(_pass_verdict())
        )


def _relative_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "mvtec").mkdir()
    Image.new("RGB", (IMAGE_W, IMAGE_H), color=(10, 200, 10)).save(
        tmp_path / "mvtec" / "good.png"
    )
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))


def test_relative_reference_resolves_from_data_dir_backend_cwd(
    image: Image.Image,
    profile: ProductProfile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _relative_ref(tmp_path, monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    rel = profile.model_copy(update={"reference_image": "mvtec/good.png"})
    judge = StubJudge(_pass_verdict())
    run_inspection(image, rel, StubSegmenter([]), judge=judge)
    assert isinstance(judge.seen_reference, Image.Image)


def test_relative_reference_resolves_from_data_dir_repo_root_cwd(
    image: Image.Image,
    profile: ProductProfile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _relative_ref(tmp_path, monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parent.parent.parent)
    rel = profile.model_copy(update={"reference_image": "mvtec/good.png"})
    judge = StubJudge(_pass_verdict())
    run_inspection(image, rel, StubSegmenter([]), judge=judge)
    assert isinstance(judge.seen_reference, Image.Image)


def test_missing_relative_reference_names_path(
    image: Image.Image,
    profile: ProductProfile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    rel = profile.model_copy(update={"reference_image": "mvtec/absent.png"})
    with pytest.raises(ValueError, match="absent.png"):
        run_inspection(
            image, rel, StubSegmenter([]), judge=StubJudge(_pass_verdict())
        )


# Judge cache on rule edits


class CountingJudge:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = FakeJudge()

    def judge(self, image, overlay, reference, detections, profile):  # type: ignore[no-untyped-def]
        self.calls += 1
        return self._inner.judge(image, overlay, reference, detections, profile)

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        return self._inner.sop_to_profile(sop_text, category_name)


def test_identical_rules_hit_changed_rules_miss(
    image: Image.Image, profile: ProductProfile, tmp_path: Path
) -> None:
    inner = CountingJudge()
    cached = CachedJudge(inner, JUDGE_MODEL, DiskCache(tmp_path / "cache"))
    detections = _detections(image)
    first = cached.judge(image, image, None, detections, profile)
    assert inner.calls == 1
    second = cached.judge(image, image, None, detections, profile)
    assert inner.calls == 1
    assert first.model_dump() == second.model_dump()
    edited = profile.model_copy(update={"rules": LENIENT_RULES})
    third = cached.judge(image, image, None, detections, edited)
    assert inner.calls == 2
    assert third.verdict == "PASS"
    assert first.verdict == "FAIL"


# Prompt rendering


def test_rendered_prompt_carries_rules_table_and_schema(
    profile: ProductProfile, image: Image.Image
) -> None:
    detections = _detections(image)
    prompt = render_judge_prompt(profile.rules, detections)
    assert STRICT_RULES in prompt
    assert "d1 | scratch" in prompt
    assert '"verdict"' in prompt
    assert "{schema}" not in prompt
    assert "{rules}" not in prompt
    assert "{detections_table}" not in prompt


def test_detections_table_empty_and_mm_dash() -> None:
    assert build_detections_table([]) == "(no candidates)"
    masks = FakeSegmenter().segment(
        Image.new("RGB", (IMAGE_W, IMAGE_H)), PROMPTS[:1]
    )
    detection = Detection(
        id="d1",
        label=masks[0].label,
        score=masks[0].score,
        bbox=(0, 0, 4, 4),
        mask_rle=masks[0].mask_rle,
        area_px=16,
        length_px=4.0,
    )
    assert detection.area_mm2 is None
    table = build_detections_table([detection])
    assert "d1 | scratch" in table
    assert table.rstrip().endswith("- | -")


def test_rules_containing_slot_literal_render_verbatim() -> None:
    rules = "reject if {detections_table} appears"
    assert rules in render_judge_prompt(rules, [])
