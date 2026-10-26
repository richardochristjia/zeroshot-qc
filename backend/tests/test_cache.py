"""Cache tests: hit without inner call, prompt/model/profile misses,
persistence across instances, and that no API key reaches the disk.

Run: cd backend && python3.11 -m pytest
"""

from pathlib import Path

import pytest
from PIL import Image

from app.adapters.fakes import FakeJudge, FakeSegmenter
from app.config import settings
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache
from app.schemas import Detection, ProductProfile, RawMask

IMAGE_W, IMAGE_H = 40, 30
PROMPTS = ["scratch", "crack"]
SAM_MODEL = "sam-model-under-test"
JUDGE_MODEL = "judge-model-under-test"
SENTINEL_KEY = "SENTINEL-API-KEY-must-never-be-cached-0123456789"


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


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


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


class CountingSegmenter:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = FakeSegmenter()

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        self.calls += 1
        return self._inner.segment(image, prompts)


class CountingJudge:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = FakeJudge()

    def judge(self, image, overlay, reference, detections, profile):  # type: ignore[no-untyped-def]
        self.calls += 1
        return self._inner.judge(image, overlay, reference, detections, profile)

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        return self._inner.sop_to_profile(sop_text, category_name)


def test_segment_hit_calls_inner_once_with_identical_results(
    image: Image.Image, cache_dir: Path
) -> None:
    inner = CountingSegmenter()
    cached = CachedSegmenter(inner, SAM_MODEL, DiskCache(cache_dir))
    first = cached.segment(image, PROMPTS)
    second = cached.segment(image, PROMPTS)
    assert inner.calls == 1
    assert [m.model_dump() for m in first] == [m.model_dump() for m in second]


def test_segment_changed_prompt_is_miss(
    image: Image.Image, cache_dir: Path
) -> None:
    inner = CountingSegmenter()
    cached = CachedSegmenter(inner, SAM_MODEL, DiskCache(cache_dir))
    cached.segment(image, PROMPTS)
    assert inner.calls == 1
    cached.segment(image, ["scratch"])
    assert inner.calls == 2
    cached.segment(image, ["scratch"])
    assert inner.calls == 2


def test_segment_changed_model_id_is_miss(
    image: Image.Image, cache_dir: Path
) -> None:
    first_inner = CountingSegmenter()
    CachedSegmenter(first_inner, SAM_MODEL, DiskCache(cache_dir)).segment(
        image, PROMPTS
    )
    assert first_inner.calls == 1
    other_inner = CountingSegmenter()
    CachedSegmenter(other_inner, "other-sam-model", DiskCache(cache_dir)).segment(
        image, PROMPTS
    )
    assert other_inner.calls == 1


def test_judge_hit_calls_inner_once(
    image: Image.Image, profile: ProductProfile, cache_dir: Path
) -> None:
    inner = CountingJudge()
    cached = CachedJudge(inner, JUDGE_MODEL, DiskCache(cache_dir))
    detections = _detections(image)
    first = cached.judge(image, image, None, detections, profile)
    second = cached.judge(image, image, None, detections, profile)
    assert inner.calls == 1
    assert first.model_dump() == second.model_dump()


def test_judge_changed_profile_is_miss(
    image: Image.Image, profile: ProductProfile, cache_dir: Path
) -> None:
    inner = CountingJudge()
    cached = CachedJudge(inner, JUDGE_MODEL, DiskCache(cache_dir))
    detections = _detections(image)
    cached.judge(image, image, None, detections, profile)
    assert inner.calls == 1
    changed_rules = profile.model_copy(
        update={"rules": "Scratches are acceptable."}
    )
    cached.judge(image, image, None, detections, changed_rules)
    assert inner.calls == 2
    changed_prompts = profile.model_copy(
        update={"defect_prompts": ["dent"]}
    )
    cached.judge(image, image, None, detections, changed_prompts)
    assert inner.calls == 3


def test_hit_survives_fresh_wrapper_and_cache_instances(
    image: Image.Image, cache_dir: Path
) -> None:
    first_inner = CountingSegmenter()
    first = CachedSegmenter(first_inner, SAM_MODEL, DiskCache(cache_dir)).segment(
        image, PROMPTS
    )
    assert first_inner.calls == 1
    second_inner = CountingSegmenter()
    second = CachedSegmenter(second_inner, SAM_MODEL, DiskCache(cache_dir)).segment(
        image, PROMPTS
    )
    assert second_inner.calls == 0
    assert [m.model_dump() for m in first] == [m.model_dump() for m in second]


def test_cache_files_never_contain_sentinel_api_key(
    image: Image.Image,
    profile: ProductProfile,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "meta_api_key", SENTINEL_KEY)
    seg_inner = CountingSegmenter()
    judge_inner = CountingJudge()
    cache = DiskCache(cache_dir)
    CachedSegmenter(seg_inner, SAM_MODEL, cache).segment(image, PROMPTS)
    CachedJudge(judge_inner, JUDGE_MODEL, cache).judge(
        image, image, None, _detections(image), profile
    )
    files = sorted(cache_dir.glob("*.json"))
    assert files, "expected cache entries on disk"
    for path in files:
        assert SENTINEL_KEY not in path.name
        assert SENTINEL_KEY not in path.read_text(encoding="utf-8")


def test_adapter_exception_propagates_uncached(
    image: Image.Image, cache_dir: Path
) -> None:
    class FlakySegmenter:
        def __init__(self) -> None:
            self.calls = 0

        def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("adapter boom")
            return FakeSegmenter().segment(image, prompts)

    inner = FlakySegmenter()
    cached = CachedSegmenter(inner, SAM_MODEL, DiskCache(cache_dir))
    with pytest.raises(RuntimeError, match="adapter boom"):
        cached.segment(image, PROMPTS)
    assert inner.calls == 1
    cached.segment(image, PROMPTS)
    assert inner.calls == 2
    cached.segment(image, PROMPTS)
    assert inner.calls == 2


def _solid(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (IMAGE_W, IMAGE_H), color=color)


def test_segment_changed_image_is_miss_then_hit(cache_dir: Path) -> None:
    inner = CountingSegmenter()
    cached = CachedSegmenter(inner, SAM_MODEL, DiskCache(cache_dir))
    first_image = _solid((120, 120, 120))
    other_image = _solid((30, 60, 90))
    cached.segment(first_image, PROMPTS)
    assert inner.calls == 1
    cached.segment(other_image, PROMPTS)
    assert inner.calls == 2
    cached.segment(other_image, PROMPTS)
    assert inner.calls == 2
    cached.segment(first_image, PROMPTS)
    assert inner.calls == 2


def test_segment_prompt_order_is_miss(
    image: Image.Image, cache_dir: Path
) -> None:
    inner = CountingSegmenter()
    cached = CachedSegmenter(inner, SAM_MODEL, DiskCache(cache_dir))
    cached.segment(image, ["scratch", "crack"])
    assert inner.calls == 1
    cached.segment(image, ["crack", "scratch"])
    assert inner.calls == 2
    cached.segment(image, ["crack", "scratch"])
    assert inner.calls == 2


def test_judge_changed_detections_is_miss(
    image: Image.Image, profile: ProductProfile, cache_dir: Path
) -> None:
    inner = CountingJudge()
    cached = CachedJudge(inner, JUDGE_MODEL, DiskCache(cache_dir))
    detections = _detections(image)
    cached.judge(image, image, None, detections, profile)
    assert inner.calls == 1
    changed = [
        detections[0].model_copy(update={"score": 0.11}),
        detections[1],
    ]
    cached.judge(image, image, None, changed, profile)
    assert inner.calls == 2
    cached.judge(image, image, None, changed, profile)
    assert inner.calls == 2


def test_judge_changed_overlay_is_miss(
    image: Image.Image, profile: ProductProfile, cache_dir: Path
) -> None:
    inner = CountingJudge()
    cached = CachedJudge(inner, JUDGE_MODEL, DiskCache(cache_dir))
    detections = _detections(image)
    overlay = _solid((120, 120, 120))
    other_overlay = _solid((200, 30, 30))
    cached.judge(image, overlay, None, detections, profile)
    assert inner.calls == 1
    cached.judge(image, other_overlay, None, detections, profile)
    assert inner.calls == 2
    cached.judge(image, other_overlay, None, detections, profile)
    assert inner.calls == 2


def test_judge_reference_none_to_image_and_changed_image_are_misses(
    image: Image.Image, profile: ProductProfile, cache_dir: Path
) -> None:
    inner = CountingJudge()
    cached = CachedJudge(inner, JUDGE_MODEL, DiskCache(cache_dir))
    detections = _detections(image)
    reference_a = _solid((10, 200, 10))
    reference_b = _solid((10, 10, 220))
    cached.judge(image, image, None, detections, profile)
    assert inner.calls == 1
    cached.judge(image, image, reference_a, detections, profile)
    assert inner.calls == 2
    cached.judge(image, image, reference_a, detections, profile)
    assert inner.calls == 2
    cached.judge(image, image, reference_b, detections, profile)
    assert inner.calls == 3
    cached.judge(image, image, reference_b, detections, profile)
    assert inner.calls == 3
    cached.judge(image, image, None, detections, profile)
    assert inner.calls == 3


def test_judge_changed_model_id_is_miss(
    image: Image.Image, profile: ProductProfile, cache_dir: Path
) -> None:
    detections = _detections(image)
    first_inner = CountingJudge()
    CachedJudge(first_inner, JUDGE_MODEL, DiskCache(cache_dir)).judge(
        image, image, None, detections, profile
    )
    assert first_inner.calls == 1
    other_inner = CountingJudge()
    CachedJudge(other_inner, "other-judge-model", DiskCache(cache_dir)).judge(
        image, image, None, detections, profile
    )
    assert other_inner.calls == 1


def test_corrupt_entry_counts_as_miss(
    image: Image.Image, cache_dir: Path
) -> None:
    inner = CountingSegmenter()
    cache = DiskCache(cache_dir)
    cached = CachedSegmenter(inner, SAM_MODEL, cache)
    first = cached.segment(image, PROMPTS)
    assert inner.calls == 1
    for path in cache_dir.glob("*.json"):
        path.write_text("not json {{{", encoding="utf-8")
    second = cached.segment(image, PROMPTS)
    assert inner.calls == 2
    assert [m.model_dump() for m in first] == [m.model_dump() for m in second]
    third = cached.segment(image, PROMPTS)
    assert inner.calls == 2
    assert [m.model_dump() for m in first] == [m.model_dump() for m in third]
