"""Inspect orchestrator tests: merge, ordering, min_score filter, skips,
and cache-hit identity.

A stub segmenter with score/geometry control drives every case:
FakeSegmenter scores never drop below the default min_score (0.55-0.95
vs 0.3), so it cannot exercise the drop path.

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
from app.pipeline.inspect import judge_box_to_pixels
from app.schemas import MissedDefect, ProductProfile, RawMask, Verdict

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
    # FakeSegmenter cannot exercise the drop path under a default
    # profile, hence the stub above.
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


# --- part_crop ---------------------------------------------------------


class PartSegmenter:
    """Returns ``part`` for the part noun (when given) and nothing for defects."""

    def __init__(self, part: RawMask | None) -> None:
        self._part = part

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        if prompts == ["bottle"] and self._part is not None:
            return [self._part]
        return []


class SizeJudge:
    def __init__(self) -> None:
        self.sizes: tuple | None = None

    def judge(self, image, overlay, reference, detections, profile):  # type: ignore[no-untyped-def]
        from app.schemas import Verdict

        ref = reference.size if reference is not None else None
        self.sizes = (image.size, overlay.size, ref)
        return Verdict(
            verdict="PASS", confidence=0.9, rulings=[], missed_defects=[],
            part_matches=True, summary="ok",
        )


def _crop_run(profile, image, part, reference=None, part_crop=True):  # type: ignore[no-untyped-def]
    judge = SizeJudge()
    run_inspection(
        image, profile, PartSegmenter(part), judge=judge,
        reference=reference, part_crop=part_crop,
    )
    return judge.sizes


def test_part_crop_judges_padded_part_box(image, profile) -> None:  # type: ignore[no-untyped-def]
    part = _rect_mask(50, 30, 50, 40, "bottle", 0.9)
    # pad = 8% of 50 = 4 -> x 46..104, y 26..74
    assert _crop_run(profile, image, part) == ((58, 48), (58, 48), None)
    assert _crop_run(profile, image, part, part_crop=False) == (
        (IMG_W, IMG_H), (IMG_W, IMG_H), None,
    )


def test_part_crop_ignores_stray_small_mask(image, profile) -> None:  # type: ignore[no-untyped-def]
    part = _rect_mask(50, 30, 50, 40, "bottle", 0.9)
    stray = _rect_mask(2, 2, 4, 4, "bottle", 0.35)

    class TwoMasks:
        def segment(self, image, prompts):  # type: ignore[no-untyped-def]
            return [stray, part] if prompts == ["bottle"] else []

    judge = SizeJudge()
    run_inspection(image, profile, TwoMasks(), judge=judge, part_crop=True)
    assert judge.sizes == ((58, 48), (58, 48), None)


def test_part_crop_part_not_found_judges_full_image(image, profile) -> None:  # type: ignore[no-untyped-def]
    assert _crop_run(profile, image, None) == ((IMG_W, IMG_H), (IMG_W, IMG_H), None)


def test_part_crop_skipped_when_part_fills_frame(image, profile) -> None:  # type: ignore[no-untyped-def]
    part = _rect_mask(2, 2, IMG_W - 4, IMG_H - 4, "bottle", 0.9)
    assert _crop_run(profile, image, part) == ((IMG_W, IMG_H), (IMG_W, IMG_H), None)


def test_part_crop_reference_uses_own_box_or_stays_whole(image, profile) -> None:  # type: ignore[no-untyped-def]
    part = _rect_mask(50, 30, 50, 40, "bottle", 0.9)
    # the same segmenter answers for the reference, so it gets the same box
    assert _crop_run(profile, image, part, reference=image)[2] == (58, 48)
    assert _crop_run(profile, image, None, reference=image)[2] == (IMG_W, IMG_H)


@pytest.mark.parametrize(
    "box,expected",
    [
        ([0, 0, 1000, 1000], (46, 26, 58, 48)),
        ([500, 500, 1000, 1000], (75, 50, 29, 24)),
        ([600, 0, 400, 1000], None),  # inverted
        ([0, 0, 1001, 10], None),  # out of range
        ([0, 0, float("nan"), 10], None),
        ([10, 10, 10, 20], None),  # zero width
        ([0, 0, 1], None),  # wrong length
        (None, None),
    ],
)
def test_judge_box_to_pixels(box, expected) -> None:  # type: ignore[no-untyped-def]
    assert judge_box_to_pixels(box, (46, 26, 104, 74)) == expected


class MissedJudge:
    def __init__(self, boxes) -> None:  # type: ignore[no-untyped-def]
        self.boxes = boxes

    def judge(self, image, overlay, reference, detections, profile):  # type: ignore[no-untyped-def]
        return Verdict(
            verdict="PASS", confidence=0.7, rulings=[],
            missed_defects=[MissedDefect(description="d", box=b) for b in self.boxes],
            part_matches=True, summary="s",
        )


def test_judge_boxes_become_j_detections_and_invalid_still_fails(image, profile) -> None:  # type: ignore[no-untyped-def]
    part = _rect_mask(50, 30, 50, 40, "bottle", 0.9)
    dets, verdict = run_inspection(
        image, profile, PartSegmenter(part),
        judge=MissedJudge([[0, 0, 1000, 1000], [9, 9, 3, 3]]), part_crop=True,
    )
    assert verdict.verdict == "FAIL"
    assert [(d.id, d.source, d.bbox) for d in dets] == [("j1", "judge", (46, 26, 58, 48))]
    dets, verdict = run_inspection(
        image, profile, PartSegmenter(part), judge=MissedJudge([None]), part_crop=True
    )
    assert dets == [] and verdict.verdict == "FAIL"


def test_overlay_outlines_judge_detection_without_tint() -> None:
    from app.pipeline.overlay import make_overlay
    from app.schemas import Detection

    rle = _rle_of(_rect_binary(10, 10, 20, 20))
    det = Detection(
        id="j1", label="judge", score=0.5, bbox=(10, 10, 20, 20), mask_rle=rle,
        area_px=400, length_px=20.0, source="judge",
    )
    base = Image.new("RGB", (IMG_W, IMG_H), (10, 10, 10))
    out = make_overlay(base, [det])
    assert out.getpixel((10, 28)) == (179, 38, 30)  # outline
    assert out.getpixel((20, 24)) == (10, 10, 10)  # interior untouched
