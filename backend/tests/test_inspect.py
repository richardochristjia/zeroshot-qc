"""Inspect orchestrator tests: merge, ordering, min_score filter, skips,
and cache-hit identity.

A stub segmenter with score/geometry control drives every case:
FakeSegmenter scores never drop below the default min_score (0.55-0.95
vs 0.3), so it cannot exercise the drop path (see check-2.md).

Run: cd backend && .venv/bin/python -m pytest -q
"""

import os

import numpy as np
import pytest
from PIL import Image
from pycocotools import mask as mask_api

from app.adapters.fakes import FakeSegmenter
from app.pipeline.cache import CachedSegmenter, DiskCache
from app.pipeline.inspect import (
    PROFILES_DIR,
    _mask_iou,
    inspect_image,
    load_profile,
    run_inspection,
)
from app.pipeline.measure import decode_rle
from app.schemas import ProductProfile, RawMask

IMG_W, IMG_H = 200, 120
PROMPTS = ["scratch", "crack"]
MODEL_ID = "sam-model-under-test"


def _rle_of(binary: np.ndarray) -> dict:
    """Encode a binary (H, W) array as JSON-safe text-counts COCO RLE.

    Must be Fortran-order: pycocotools.encode raises ValueError on
    C-contiguous arrays. Mirrors fakes.py and test_measure.py.
    """
    fortran = np.asfortranarray(binary.astype(np.uint8))
    encoded = mask_api.encode(fortran)
    return {
        "size": [int(encoded["size"][0]), int(encoded["size"][1])],
        "counts": encoded["counts"].decode("utf-8"),
    }


def _rect_binary(x0: int, y0: int, w: int, h: int) -> np.ndarray:
    binary = np.zeros((IMG_H, IMG_W), dtype=np.uint8)
    binary[y0 : y0 + h, x0 : x0 + w] = 1
    return binary


def _rect_mask(
    x0: int, y0: int, w: int, h: int, label: str, score: float
) -> RawMask:
    return RawMask(
        label=label, score=score, mask_rle=_rle_of(_rect_binary(x0, y0, w, h))
    )


class StubSegmenter:
    """Fixed mask list with call counting and prompt capture."""

    def __init__(self, masks: list[RawMask]) -> None:
        self._masks = masks
        self.calls = 0
        self.seen_prompts: list[str] | None = None

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        self.calls += 1
        self.seen_prompts = list(prompts)
        return list(self._masks)


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (IMG_W, IMG_H), color=(120, 120, 120))


@pytest.fixture
def profile() -> ProductProfile:
    return ProductProfile(
        id="bottle",
        name="Bottle",
        defect_prompts=PROMPTS,
        rules="No scratches or cracks.",
        mm_per_px=0.1,
    )


def test_merge_overlapping_masks_joins_labels_and_keeps_higher_score(
    image: Image.Image, profile: ProductProfile
) -> None:
    # B sits inside A: IoU = 4050/5000 = 0.81 > 0.5 -> merge.
    stub = StubSegmenter(
        [
            _rect_mask(10, 5, 100, 50, "scratch", 0.9),
            _rect_mask(15, 10, 90, 45, "crack", 0.7),
        ]
    )
    detections = run_inspection(image, profile, stub)
    assert stub.seen_prompts == PROMPTS
    assert len(detections) == 1
    merged = detections[0]
    assert merged.id == "d1"
    assert merged.label == "scratch+crack"
    assert merged.score == pytest.approx(0.9)
    assert merged.area_px == 100 * 50  # union == A since B is inside A
    assert isinstance(merged.mask_rle["counts"], str)


def test_merged_detection_carries_union_mask_rle(
    image: Image.Image, profile: ProductProfile
) -> None:
    # Partial overlap: IoU = 3000/5000 = 0.6 > 0.5 -> merge; the union
    # is strictly bigger than either input, so the re-encoded RLE must
    # cover it exactly.
    first = _rect_binary(10, 5, 100, 50)
    second = _rect_binary(40, 5, 100, 50)
    expected_union = np.logical_or(first, second)
    stub = StubSegmenter(
        [
            RawMask(label="scratch", score=0.9, mask_rle=_rle_of(first)),
            RawMask(label="crack", score=0.8, mask_rle=_rle_of(second)),
        ]
    )
    detections = run_inspection(image, profile, stub)
    assert len(detections) == 1
    decoded = decode_rle(detections[0].mask_rle)
    assert np.array_equal(decoded, expected_union.astype(np.uint8))
    assert detections[0].area_px == int(expected_union.sum())
    assert detections[0].length_mm == pytest.approx(
        detections[0].length_px * 0.1
    )


def test_low_iou_pair_stays_split_in_score_order(
    image: Image.Image, profile: ProductProfile
) -> None:
    # IoU = 2000/8000 = 0.25 < 0.5 -> no merge; lower score listed first
    # in the input to prove score-descending ids.
    stub = StubSegmenter(
        [
            _rect_mask(70, 5, 100, 50, "crack", 0.6),
            _rect_mask(10, 5, 100, 50, "scratch", 0.9),
        ]
    )
    detections = run_inspection(image, profile, stub)
    assert [d.id for d in detections] == ["d1", "d2"]
    assert [d.label for d in detections] == ["scratch", "crack"]
    assert [d.score for d in detections] == [pytest.approx(0.9), pytest.approx(0.6)]


def test_below_min_score_mask_is_dropped(
    image: Image.Image, profile: ProductProfile
) -> None:
    stub = StubSegmenter(
        [
            _rect_mask(10, 5, 100, 50, "scratch", 0.9),
            _rect_mask(10, 70, 50, 40, "crack", 0.29),
        ]
    )
    detections = run_inspection(image, profile, stub)
    assert [d.label for d in detections] == ["scratch"]


def test_min_score_boundary_equality_is_kept(
    image: Image.Image, profile: ProductProfile
) -> None:
    assert profile.min_score == pytest.approx(0.3)
    stub = StubSegmenter(
        [_rect_mask(10, 5, 100, 50, "scratch", 0.3)]
    )
    detections = run_inspection(image, profile, stub)
    assert len(detections) == 1
    assert detections[0].label == "scratch"


def test_empty_mask_list_gives_zero_detections(
    image: Image.Image, profile: ProductProfile
) -> None:
    assert run_inspection(image, profile, StubSegmenter([])) == []


def test_size_mismatched_rle_is_skipped_with_warning(
    image: Image.Image, profile: ProductProfile
) -> None:
    wrong_size = _rle_of(np.ones((10, 10), dtype=np.uint8))
    stub = StubSegmenter(
        [
            RawMask(label="scratch", score=0.9, mask_rle=wrong_size),
            _rect_mask(10, 5, 100, 50, "crack", 0.8),
        ]
    )
    with pytest.warns(UserWarning, match="skipping RLE"):
        detections = run_inspection(image, profile, stub)
    assert [d.label for d in detections] == ["crack"]


def test_undecodable_rle_is_skipped_with_warning(
    image: Image.Image, profile: ProductProfile
) -> None:
    bad = {"size": [IMG_H, IMG_W], "counts": "!!!not-valid-rle!!!"}
    stub = StubSegmenter(
        [
            RawMask(label="scratch", score=0.9, mask_rle=bad),
            _rect_mask(10, 5, 100, 50, "crack", 0.8),
        ]
    )
    with pytest.warns(UserWarning, match="skipping undecodable RLE"):
        detections = run_inspection(image, profile, stub)
    assert [d.label for d in detections] == ["crack"]


def test_cache_hit_rerun_returns_identical_detections_without_inner_call(
    image: Image.Image, profile: ProductProfile, tmp_path
) -> None:
    inner = StubSegmenter(
        [
            _rect_mask(10, 5, 100, 50, "scratch", 0.9),
            _rect_mask(70, 5, 100, 50, "crack", 0.6),
        ]
    )
    cached = CachedSegmenter(inner, MODEL_ID, DiskCache(tmp_path / "cache"))
    first = run_inspection(image, profile, cached)
    assert inner.calls == 1
    second = run_inspection(image, profile, cached)
    assert inner.calls == 1
    assert [d.model_dump() for d in first] == [d.model_dump() for d in second]
    assert len(second) == 2


def test_fake_segmenter_scores_never_drop_below_default_min_score(
    image: Image.Image, profile: ProductProfile
) -> None:
    # Locks the check-2.md rationale for the stub above: FakeSegmenter
    # cannot exercise the drop path under a default profile.
    for mask in FakeSegmenter().segment(image, PROMPTS):
        assert mask.score >= profile.min_score


def test_load_profile_unknown_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        load_profile("no-such-profile")


def test_load_profile_rejects_traversal_and_absolute_paths(
    tmp_path, profile: ProductProfile
) -> None:
    outside = tmp_path / "evil.json"
    outside.write_text(profile.model_dump_json(), encoding="utf-8")
    traversal = os.path.relpath(str(tmp_path / "evil"), str(PROFILES_DIR))
    absolute = str(tmp_path / "evil")
    assert "/" in traversal  # premise: the name really escapes PROFILES_DIR
    with pytest.raises(ValueError, match="unknown profile"):
        load_profile(traversal)
    with pytest.raises(ValueError, match="unknown profile"):
        load_profile(absolute)


def test_zero_area_mask_is_skipped(
    image: Image.Image, profile: ProductProfile
) -> None:
    empty = RawMask(
        label="scratch",
        score=0.9,
        mask_rle=_rle_of(np.zeros((IMG_H, IMG_W), dtype=np.uint8)),
    )
    stub = StubSegmenter(
        [empty, _rect_mask(10, 5, 100, 50, "crack", 0.8)]
    )
    with pytest.warns(UserWarning, match="zero-area"):
        detections = run_inspection(image, profile, stub)
    assert [d.label for d in detections] == ["crack"]


def test_giant_mismatched_rle_is_skipped_without_decoding(
    image: Image.Image, profile: ProductProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_decode = mask_api.decode
    decoded_giant: list[object] = []

    def _spy(rle):  # type: ignore[no-untyped-def]
        size = rle.get("size") if isinstance(rle, dict) else None
        if size == [30000, 30000]:
            decoded_giant.append(size)
            raise AssertionError("giant mismatched RLE must skip pre-decode")
        return real_decode(rle)

    monkeypatch.setattr(mask_api, "decode", _spy)
    giant = {"size": [30000, 30000], "counts": "zzzzzzzzzzzz"}
    stub = StubSegmenter(
        [
            RawMask(label="scratch", score=0.9, mask_rle=giant),
            _rect_mask(10, 5, 100, 50, "crack", 0.8),
        ]
    )
    with pytest.warns(UserWarning, match="skipping RLE"):
        detections = run_inspection(image, profile, stub)
    assert decoded_giant == []
    assert [d.label for d in detections] == ["crack"]


def test_iou_exactly_half_pair_stays_split(
    image: Image.Image, profile: ProductProfile
) -> None:
    # A is 2x2 (4 px), B is the left 2x1 half inside A (2 px):
    # IoU = 2/4 = 0.5 exactly, and the strict `>` rule must NOT merge.
    big = np.zeros((IMG_H, IMG_W), dtype=np.uint8)
    big[5:7, 10:12] = 1
    half = np.zeros((IMG_H, IMG_W), dtype=np.uint8)
    half[5:7, 10:11] = 1
    assert _mask_iou(big, half) == 0.5
    stub = StubSegmenter(
        [
            RawMask(label="scratch", score=0.9, mask_rle=_rle_of(big)),
            RawMask(label="crack", score=0.8, mask_rle=_rle_of(half)),
        ]
    )
    detections = run_inspection(image, profile, stub)
    assert [d.id for d in detections] == ["d1", "d2"]
    assert [d.label for d in detections] == ["scratch", "crack"]


def test_none_mm_per_px_yields_none_mm_fields(image: Image.Image) -> None:
    profile = ProductProfile(
        id="screw",
        name="Screw",
        defect_prompts=PROMPTS,
        rules="No scratches.",
    )
    assert profile.mm_per_px is None
    stub = StubSegmenter([_rect_mask(10, 5, 100, 50, "scratch", 0.9)])
    (detection,) = run_inspection(image, profile, stub)
    assert detection.area_px == 100 * 50
    assert detection.area_mm2 is None
    assert detection.length_mm is None


def test_inspect_image_loads_image_and_profile_from_disk(
    tmp_path, profile: ProductProfile
) -> None:
    image_path = tmp_path / "part.png"
    Image.new("RGB", (IMG_W, IMG_H), color=(120, 120, 120)).save(image_path)
    profile_path = tmp_path / "profiles" / "widget.json"
    profile_path.parent.mkdir()
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")
    stub = StubSegmenter([_rect_mask(10, 5, 100, 50, "scratch", 0.9)])
    import app.pipeline.inspect as inspect_mod

    monkey_profile_dir = inspect_mod.PROFILES_DIR
    inspect_mod.PROFILES_DIR = profile_path.parent
    try:
        detections = inspect_image(str(image_path), "widget", stub)
    finally:
        inspect_mod.PROFILES_DIR = monkey_profile_dir
    assert len(detections) == 1
    assert detections[0].id == "d1"
    assert detections[0].area_px == 100 * 50
