"""Metric tests (M4): correctness of the pure metric functions.

Run: cd backend && .venv/bin/python -m pytest -q
"""

import numpy as np
import pytest

from app.eval.metrics import (
    auroc,
    fail_score,
    image_metrics,
    mean_iou,
    pixel_iou,
    summarize,
)


def _square_rle(x0: int, y0: int, size: int) -> dict:
    from pycocotools import mask as mask_api

    binary = np.zeros((16, 16), dtype=np.uint8, order="F")
    binary[y0 : y0 + size, x0 : x0 + size] = 1
    encoded = mask_api.encode(binary)
    return {
        "size": [int(encoded["size"][0]), int(encoded["size"][1])],
        "counts": encoded["counts"].decode("utf-8"),
    }


def test_perfect_predictions_score_one() -> None:
    labels = [True, True, False, False]
    metrics = image_metrics(labels, [True, True, False, False], [0.9, 0.8, 0.1, 0.2])
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["accuracy"] == 1.0


def test_all_pass_on_defectives_gives_recall_zero() -> None:
    labels = [True, True, True]
    metrics = image_metrics(labels, [False, False, False], [0.1, 0.2, 0.3])
    assert metrics["recall"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["f1"] == 0.0


def test_fail_score_uses_confidence() -> None:
    assert fail_score("FAIL", 0.9) == 0.9
    assert fail_score("PASS", 0.9) == pytest.approx(0.1)


def test_perfect_ranker_auroc_one() -> None:
    assert auroc([0.9, 0.8, 0.2, 0.1], [True, True, False, False]) == 1.0


def test_single_class_auroc_is_neutral() -> None:
    assert auroc([0.9, 0.8], [True, True]) == 0.5
    assert auroc([0.1, 0.2], [False, False]) == 0.5


def test_all_tied_scores_auroc_is_neutral() -> None:
    assert auroc([1.0, 1.0, 1.0, 1.0], [False, False, True, True]) == 0.5


def test_identical_mask_iou_one() -> None:
    rle = _square_rle(2, 2, 4)
    truth = np.zeros((16, 16), dtype=bool)
    truth[2:6, 2:6] = True
    assert pixel_iou([rle], truth, 16, 16) == 1.0


def test_disjoint_mask_iou_zero() -> None:
    rle = _square_rle(0, 0, 2)
    truth = np.zeros((16, 16), dtype=bool)
    truth[10:14, 10:14] = True
    assert pixel_iou([rle], truth, 16, 16) == 0.0


def test_good_images_excluded_from_iou() -> None:
    empty = np.zeros((16, 16), dtype=bool)
    assert pixel_iou([_square_rle(0, 0, 2)], empty, 16, 16) is None
    assert mean_iou([None, None]) is None
    assert mean_iou([1.0, None, 0.5]) == 0.75


def test_summarize_groups_per_category_and_overall() -> None:
    records = [
        {
            "category": "a",
            "label": "defective",
            "verdict": "FAIL",
            "fail_score": 0.9,
            "iou": 1.0,
        },
        {
            "category": "a",
            "label": "good",
            "verdict": "PASS",
            "fail_score": 0.1,
            "iou": None,
        },
        {
            "category": "b",
            "label": "defective",
            "verdict": "PASS",
            "fail_score": 0.4,
            "iou": 0.0,
        },
    ]
    summary = summarize(records)
    assert summary["per_category"]["a"]["f1"] == 1.0
    assert summary["per_category"]["a"]["iou"] == 1.0
    assert summary["per_category"]["b"]["recall"] == 0.0
    assert summary["overall"]["n"] == 3.0
    assert summary["overall"]["iou"] == 0.5
