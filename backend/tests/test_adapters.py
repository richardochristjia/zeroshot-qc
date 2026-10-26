"""Adapter tests: fake determinism, RLE acceptance, Verdict validation,
and the real adapters' no-network not-configured guard.

Run: cd backend && python3.11 -m pytest
"""

import base64
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pycocotools import mask as mask_api

from app.adapters.base import AdapterNotConfiguredError
from app.adapters.fakes import FakeImageGenerator, FakeJudge, FakeSegmenter
from app.adapters.muse_image import MuseImageGenerator
from app.adapters.muse_spark import MuseSparkJudge
from app.adapters.sam import SamSegmenter
from app.config import settings
from app.pipeline.cache import CachedSegmenter, DiskCache
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
        assert json.loads(json.dumps(rle)) == rle
        decodable = {
            "size": rle["size"],
            "counts": rle["counts"].encode("utf-8"),
        }
        decoded = mask_api.decode(decodable)
        assert decoded.shape == (IMAGE_H, IMAGE_W)
        assert int(decoded.sum()) > 0
        assert int(mask_api.area(decodable)) == int(decoded.sum())


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


class _StubResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def _configure_all(monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    monkeypatch.setattr(settings, "meta_api_key", "test-key")
    monkeypatch.setattr(settings, "meta_api_base_url", base_url)
    monkeypatch.setattr(settings, "sam_model_id", "sam-test")
    monkeypatch.setattr(settings, "judge_model_id", "judge-test")
    monkeypatch.setattr(settings, "image_model_id", "image-test")


def _call_adapter(
    name: str, image: Image.Image, profile: ProductProfile
) -> object:
    if name == "sam":
        return SamSegmenter().segment(image, PROMPTS)
    if name == "judge":
        return MuseSparkJudge().judge(image, image, None, [], profile)
    return MuseImageGenerator().add_defect(image, "a scratch", None)


@pytest.mark.parametrize("adapter_name", ["sam", "judge", "image"])
@pytest.mark.parametrize(
    "empty_field", ["meta_api_key", "meta_api_base_url", None]
)
def test_not_configured_single_empty_field(
    adapter_name: str,
    empty_field: str | None,
    image: Image.Image,
    profile: ProductProfile,
    monkeypatch: pytest.MonkeyPatch,
    no_http: list,
) -> None:
    # None parametrizes the adapter's own model field below.
    model_field = {
        "sam": "sam_model_id",
        "judge": "judge_model_id",
        "image": "image_model_id",
    }[adapter_name]
    _configure_all(monkeypatch, "https://example.test/meta")
    monkeypatch.setattr(settings, empty_field or model_field, "")
    with pytest.raises(AdapterNotConfiguredError):
        _call_adapter(adapter_name, image, profile)
    assert no_http == []


@pytest.mark.parametrize("adapter_name", ["sam", "judge", "image"])
def test_http_base_url_rejected_before_http(
    adapter_name: str,
    image: Image.Image,
    profile: ProductProfile,
    monkeypatch: pytest.MonkeyPatch,
    no_http: list,
) -> None:
    _configure_all(monkeypatch, "http://example.test/meta")
    with pytest.raises(AdapterNotConfiguredError):
        _call_adapter(adapter_name, image, profile)
    assert no_http == []


@pytest.mark.parametrize("adapter_name", ["sam", "judge", "image"])
def test_https_base_url_reaches_stubbed_http(
    adapter_name: str,
    image: Image.Image,
    profile: ProductProfile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_all(monkeypatch, "https://example.test/meta")
    calls: list = []

    def _stub(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((args, kwargs))
        if adapter_name == "sam":
            return _StubResponse({"masks": []})
        if adapter_name == "judge":
            return _StubResponse(
                {
                    "verdict": "PASS",
                    "confidence": 0.5,
                    "rulings": [],
                    "missed_defects": [],
                    "summary": "ok",
                }
            )
        buffer = io.BytesIO()
        Image.new("RGB", (2, 2), color=(10, 20, 30)).save(buffer, format="PNG")
        return _StubResponse(
            {"image": base64.b64encode(buffer.getvalue()).decode("ascii")}
        )

    monkeypatch.setattr(httpx, "post", _stub)
    result = _call_adapter(adapter_name, image, profile)
    assert len(calls) == 1
    if adapter_name == "sam":
        assert result == []
    elif adapter_name == "judge":
        assert isinstance(result, Verdict)
    else:
        assert isinstance(result, Image.Image)


@pytest.fixture
def sam_http(monkeypatch: pytest.MonkeyPatch):
    _configure_all(monkeypatch, "https://example.test/meta")
    state: dict = {"payload": {"masks": []}, "calls": 0}

    def _stub(*args, **kwargs):  # type: ignore[no-untyped-def]
        state["calls"] += 1
        return _StubResponse(state["payload"])

    monkeypatch.setattr(httpx, "post", _stub)
    return state


def test_sam_drops_mismatched_and_malformed_rle(
    image: Image.Image, sam_http: dict
) -> None:
    valid = FakeSegmenter().segment(image, PROMPTS)[0]
    donor = FakeSegmenter().segment(
        Image.new("RGB", (200, 200), color=(120, 120, 120)), PROMPTS
    )[0]
    sam_http["payload"] = {
        "masks": [
            {
                "label": valid.label,
                "score": valid.score,
                "mask_rle": valid.mask_rle,
            },
            {
                "label": "scratch",
                "score": 0.9,
                "mask_rle": donor.mask_rle,
            },
            {
                "label": "crack",
                "score": 0.9,
                "mask_rle": {"size": [IMAGE_H, IMAGE_W], "counts": 12345},
            },
            {
                "label": "dent",
                "score": 0.9,
                "mask_rle": {
                    "size": [IMAGE_H, IMAGE_W],
                    "counts": "x" * 20000,
                },
            },
        ]
    }
    result = SamSegmenter().segment(image, PROMPTS)
    assert [m.label for m in result] == [valid.label]
    assert result[0].mask_rle == valid.mask_rle


def test_sam_malformed_mask_never_reaches_disk_cache(
    image: Image.Image, sam_http: dict, tmp_path: Path
) -> None:
    donor = FakeSegmenter().segment(
        Image.new("RGB", (200, 200), color=(120, 120, 120)), PROMPTS
    )[0]
    sam_http["payload"] = {
        "masks": [
            {"label": "scratch", "score": 0.9, "mask_rle": donor.mask_rle}
        ]
    }
    cache_dir = tmp_path / "cache"
    cached = CachedSegmenter(SamSegmenter(), "sam-test", DiskCache(cache_dir))
    assert cached.segment(image, PROMPTS) == []
    for path in cache_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert donor.mask_rle["counts"] not in text
        assert "200" not in text
