"""Adapter tests: fake determinism, RLE acceptance, Verdict validation,
and the real adapters' no-network not-configured guard.

Run: cd backend && python3.11 -m pytest
Note: pycocotools decode/area raise on this host (see risks.md), so RLE
acceptance here is encoder acceptance plus structural checks only.
"""

import json

import httpx
import numpy as np
import pytest
from PIL import Image
from pycocotools import mask as mask_api

from app.adapters.base import AdapterNotConfiguredError
from app.adapters.fakes import FakeImageGenerator, FakeJudge, FakeSegmenter
from app.adapters.muse_image import MuseImageGenerator
from app.adapters.muse_spark import MuseSparkJudge
from app.adapters.sam import SamSegmenter
from app.config import settings
from app.schemas import Detection, ProductProfile, Verdict

IMAGE_W, IMAGE_H = 40, 30
PROMPTS = ["scratch", "crack"]


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (IMAGE_W, IMAGE_H), color=(120, 120, 120))


@pytest.fixture
def profile() -> ProductProfile:
    return ProductProfile(
        id="bottle",
        name="Bottle",
        defect_prompts=PROMPTS,
        rules="No scratches or cracks.",
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


def test_fake_segmenter_determinism(image: Image.Image) -> None:
    first = FakeSegmenter().segment(image, PROMPTS)
    second = FakeSegmenter().segment(image, PROMPTS)
    assert [m.model_dump() for m in first] == [m.model_dump() for m in second]


def test_fake_segmenter_one_mask_per_prompt(image: Image.Image) -> None:
    masks = FakeSegmenter().segment(image, PROMPTS)
    assert [m.label for m in masks] == PROMPTS
    assert all(0.0 <= m.score <= 1.0 for m in masks)


def test_fake_segmenter_rle_acceptance_and_structure(image: Image.Image) -> None:
    masks = FakeSegmenter().segment(image, PROMPTS)
    assert masks
    for mask in masks:
        rle = mask.mask_rle
        assert rle["size"] == [IMAGE_H, IMAGE_W]
        assert isinstance(rle["counts"], str)
        json.dumps(rle)
        assert rle["counts"].encode("utf-8")
        assert rle["counts"].encode("utf-8").decode("utf-8") == rle["counts"]
        blank = np.zeros((IMAGE_H, IMAGE_W), dtype=np.uint8, order="F")
        encoded = mask_api.encode(blank)
        assert [int(encoded["size"][0]), int(encoded["size"][1])] == rle["size"]
        assert isinstance(encoded["counts"], bytes)


def test_fake_judge_validates_first_try(
    image: Image.Image, profile: ProductProfile
) -> None:
    detections = _detections(image)
    verdict = FakeJudge().judge(image, image, None, detections, profile)
    assert isinstance(verdict, Verdict)
    Verdict.model_validate(verdict.model_dump())
    assert len(verdict.rulings) == len(detections)
    for ruling in verdict.rulings:
        dumped = ruling.model_dump()
        assert "rule_violated" in dumped
    assert 0.0 <= verdict.confidence <= 1.0


def test_fake_judge_determinism(image: Image.Image, profile: ProductProfile) -> None:
    detections = _detections(image)
    judge = FakeJudge()
    first = judge.judge(image, image, None, detections, profile)
    second = judge.judge(image, image, None, detections, profile)
    assert first.model_dump() == second.model_dump()


def test_fake_image_generator_same_size_deterministic(image: Image.Image) -> None:
    generator = FakeImageGenerator()
    first = generator.add_defect(image, "a scratch", None)
    second = generator.add_defect(image, "a scratch", None)
    assert first.size == image.size
    assert first.tobytes() == second.tobytes()


@pytest.fixture
def empty_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in (
        "meta_api_key",
        "meta_api_base_url",
        "sam_model_id",
        "judge_model_id",
        "image_model_id",
    ):
        monkeypatch.setattr(settings, field, "")


@pytest.fixture
def no_http(monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list = []

    def _forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("HTTP must not be called when not configured")

    monkeypatch.setattr(httpx, "post", _forbidden)
    return calls


def test_sam_not_configured_raises_without_http(
    image: Image.Image, empty_settings: None, no_http: list
) -> None:
    with pytest.raises(AdapterNotConfiguredError):
        SamSegmenter().segment(image, PROMPTS)
    assert no_http == []


def test_judge_not_configured_raises_without_http(
    image: Image.Image, profile: ProductProfile, empty_settings: None, no_http: list
) -> None:
    with pytest.raises(AdapterNotConfiguredError):
        MuseSparkJudge().judge(image, image, None, [], profile)
    assert no_http == []


def test_image_not_configured_raises_without_http(
    image: Image.Image, empty_settings: None, no_http: list
) -> None:
    with pytest.raises(AdapterNotConfiguredError):
        MuseImageGenerator().add_defect(image, "a scratch", None)
    assert no_http == []


def test_sam_empty_model_id_alone_raises_without_http(
    image: Image.Image, monkeypatch: pytest.MonkeyPatch, no_http: list
) -> None:
    monkeypatch.setattr(settings, "meta_api_key", "test-key")
    monkeypatch.setattr(settings, "meta_api_base_url", "unused-base-url")
    monkeypatch.setattr(settings, "sam_model_id", "")
    with pytest.raises(AdapterNotConfiguredError):
        SamSegmenter().segment(image, PROMPTS)
    assert no_http == []


def test_sop_to_profile_is_m5_stub() -> None:
    with pytest.raises(NotImplementedError):
        MuseSparkJudge().sop_to_profile("Some SOP text.", "bottle")
