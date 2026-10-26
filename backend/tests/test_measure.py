"""Measurement tests: known-size rectangle, mm scaling, None mm fields,
degenerate (empty) mask, and RLE decode forms.

Run: cd backend && .venv/bin/python -m pytest -q
"""

import numpy as np
import pytest
from pycocotools import mask as mask_api

from app.pipeline.measure import decode_rle, measure_mask

RECT_X, RECT_Y, RECT_W, RECT_H = 10, 5, 100, 50
IMG_W, IMG_H = 200, 120


def _rle_of(binary: np.ndarray) -> dict:
    """Encode a binary (H, W) array as JSON-safe COCO RLE.

    Must be Fortran-order: pycocotools.encode raises ValueError on
    C-contiguous arrays. Mirrors fakes.py.
    """
    fortran = np.asfortranarray(binary.astype(np.uint8))
    encoded = mask_api.encode(fortran)
    return {
        "size": [int(encoded["size"][0]), int(encoded["size"][1])],
        "counts": encoded["counts"].decode("utf-8"),
    }


def _rect_rle() -> dict:
    binary = np.zeros((IMG_H, IMG_W), dtype=np.uint8)
    binary[RECT_Y : RECT_Y + RECT_H, RECT_X : RECT_X + RECT_W] = 1
    return _rle_of(binary)


def _empty_rle() -> dict:
    return _rle_of(np.zeros((IMG_H, IMG_W), dtype=np.uint8))


def test_known_rectangle_exact_px_values() -> None:
    result = measure_mask(_rect_rle())
    assert result["area_px"] == RECT_W * RECT_H
    # minAreaRect is point-span: a filled 100x50 rect measures 99.0, not 100.0.
    assert result["length_px"] == pytest.approx(99.0)
    assert result["bbox"] == (RECT_X, RECT_Y, RECT_W, RECT_H)


def test_mm_fields_none_by_default() -> None:
    result = measure_mask(_rect_rle())
    assert result["area_mm2"] is None
    assert result["length_mm"] is None


def test_mm_scaling() -> None:
    result = measure_mask(_rect_rle(), mm_per_px=0.1)
    assert result["length_mm"] == pytest.approx(9.9)
    assert result["area_mm2"] == pytest.approx(5000 * 0.1**2)


def test_degenerate_empty_mask_zeroes_without_raising() -> None:
    result = measure_mask(_empty_rle())
    assert result["area_px"] == 0
    assert result["length_px"] == 0.0
    assert result["bbox"] == (0, 0, 0, 0)
    assert result["area_mm2"] is None
    assert result["length_mm"] is None


def test_degenerate_empty_mask_with_mm_scale() -> None:
    result = measure_mask(_empty_rle(), mm_per_px=0.1)
    assert result["area_mm2"] == pytest.approx(0.0)
    assert result["length_mm"] == pytest.approx(0.0)


def test_decode_rle_accepts_text_and_bytes_counts() -> None:
    rle = _rect_rle()
    from_text = decode_rle(rle)
    from_bytes = decode_rle({"size": rle["size"], "counts": rle["counts"].encode("utf-8")})
    assert from_text.shape == (IMG_H, IMG_W)
    assert int(from_text.sum()) == RECT_W * RECT_H
    assert np.array_equal(from_text, from_bytes)


def test_encode_requires_fortran_order() -> None:
    binary = np.zeros((IMG_H, IMG_W), dtype=np.uint8)
    assert binary.flags["C_CONTIGUOUS"]
    with pytest.raises(ValueError):
        mask_api.encode(binary)


def test_decode_rle_rejects_giant_size_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoded: list[dict] = []

    def _spy(rle):  # type: ignore[no-untyped-def]
        decoded.append(rle)
        raise AssertionError("giant RLE must be refused before decoding")

    monkeypatch.setattr(mask_api, "decode", _spy)
    with pytest.raises(ValueError, match="exceeds"):
        decode_rle({"size": [30000, 30000], "counts": "zzzzzzzzzzzz"})
    assert decoded == []
