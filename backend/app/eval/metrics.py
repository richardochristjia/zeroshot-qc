"""Pure eval metrics (M4): image-level scores, AUROC, and pixel IoU.

No I/O here: callers pass labels, verdicts, confidences, detection RLEs,
and ground-truth masks; everything below is a pure function of them.
Defective is the positive class. Good images are excluded from IoU —
there is no ground truth to overlap, so they contribute ``None``.
"""

from __future__ import annotations

import numpy as np
from pycocotools import mask as mask_api


def fail_score(verdict: str, confidence: float) -> float:
    """Score for AUROC: ``confidence`` on FAIL, ``1 - confidence`` on PASS."""
    if verdict == "FAIL":
        return confidence
    return 1.0 - confidence


def confusion(
    labels: list[bool], predictions: list[bool]
) -> dict[str, int]:
    """Counts with defective=True as the positive class."""
    table = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for actual, predicted in zip(labels, predictions):
        if actual and predicted:
            table["tp"] += 1
        elif not actual and not predicted:
            table["tn"] += 1
        elif not actual and predicted:
            table["fp"] += 1
        else:
            table["fn"] += 1
    return table


def precision_recall_f1(table: dict[str, int]) -> dict[str, float]:
    """Precision/recall/F1/accuracy from a confusion table; 0.0 on no data."""
    tp, fp, fn = table["tp"], table["fp"], table["fn"]
    total = table["tp"] + table["tn"] + table["fp"] + table["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + table["tn"]) / total if total else 0.0,
    }


def auroc(scores: list[float], labels: list[bool]) -> float:
    """Area under the ROC curve over fail scores (trapezoidal rule).

    A perfect ranker scores 1.0; a single-class sample scores 0.5
    (no ranking is measurable) instead of raising.
    """
    positives = sum(1 for label in labels if label)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return 0.5
    # Mann-Whitney U with average ranks so tied scores split credit
    # instead of depending on input order.
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    rank_sum = 0.0
    index = 0
    while index < len(order):
        end = index
        while end + 1 < len(order) and scores[order[end + 1]] == scores[order[index]]:
            end += 1
        average_rank = (index + 1 + end + 1) / 2.0
        for position in range(index, end + 1):
            if labels[order[position]]:
                rank_sum += average_rank
        index = end + 1
    stat = rank_sum - positives * (positives + 1) / 2.0
    return stat / (positives * negatives)


def image_metrics(
    labels: list[bool], predictions: list[bool], scores: list[float]
) -> dict[str, float]:
    """One dict with precision/recall/F1/accuracy/AUROC plus ``n``."""
    table = confusion(labels, predictions)
    return {
        **precision_recall_f1(table),
        "auroc": auroc(scores, labels),
        "n": float(len(labels)),
        **{key: float(value) for key, value in table.items()},
    }


def _decode_union(
    detection_rles: list[dict], width: int, height: int
) -> np.ndarray:
    union = np.zeros((height, width), dtype=bool)
    for mask_rle in detection_rles:
        rle = {
            "size": [int(v) for v in mask_rle["size"]],
            "counts": mask_rle["counts"].encode("utf-8")
            if isinstance(mask_rle["counts"], str)
            else mask_rle["counts"],
        }
        try:
            decoded = mask_api.decode(rle).astype(bool)
        except Exception:
            continue
        if decoded.shape != (height, width):
            continue
        union |= decoded
    return union


def pixel_iou(
    detection_rles: list[dict],
    ground_truth: np.ndarray,
    width: int,
    height: int,
) -> float | None:
    """IoU of the kept-detection union vs ground truth (defectives only).

    Returns ``None`` when the ground truth is empty — the good-image
    case, excluded from every mean. Undecodable or misshapen RLEs are
    skipped, never raised on.
    """
    truth = np.asarray(ground_truth).astype(bool)
    if not truth.any():
        return None
    union = _decode_union(detection_rles, width, height)
    intersection = np.logical_and(union, truth).sum()
    total = np.logical_or(union, truth).sum()
    return float(intersection / total) if total else 0.0


def mean_iou(values: list[float | None]) -> float | None:
    """Mean over defective images; ``None`` when no image contributed."""
    kept = [value for value in values if value is not None]
    if not kept:
        return None
    return float(sum(kept) / len(kept))


def summarize(records: list[dict]) -> dict:
    """Per-category plus overall metrics from per-image record dicts.

    Each record carries ``category``, ``label`` ("good"/"defective"),
    ``verdict`` ("PASS"/"FAIL"), ``fail_score`` (float), and ``iou``
    (float or None). Overall image metrics pool every image; overall
    IoU pools every defective image with a non-None IoU.
    """
    per_category: dict[str, dict] = {}
    for category in sorted({record["category"] for record in records}):
        group = [r for r in records if r["category"] == category]
        labels = [r["label"] == "defective" for r in group]
        predictions = [r["verdict"] == "FAIL" for r in group]
        scores = [float(r["fail_score"]) for r in group]
        metrics = image_metrics(labels, predictions, scores)
        metrics["iou"] = mean_iou([r["iou"] for r in group])
        metrics["n"] = float(len(group))
        per_category[category] = metrics
    labels = [r["label"] == "defective" for r in records]
    predictions = [r["verdict"] == "FAIL" for r in records]
    scores = [float(r["fail_score"]) for r in records]
    overall = image_metrics(labels, predictions, scores)
    overall["iou"] = mean_iou([r["iou"] for r in records])
    overall["n"] = float(len(records))
    return {"per_category": per_category, "overall": overall}
