"""Scripted eval-only fakes (M4): deterministic stand-ins with SAM-like shape.

The stock :mod:`app.adapters.fakes` fire on every image, so all three
ablation modes would score identically on the fixture. These scripted
fakes instead separate the modes *by construction* while still routing
every image through the real :func:`app.pipeline.inspect.run_inspection`
plus cache:

- :class:`ScriptedFixtureSegmenter` returns one mask per pure-red
  fixture-defect component plus one fixed 2x2 false-positive box at the
  top-left corner (a stand-in for a SAM false alarm).
- :class:`ReferenceAwareJudge` keeps large detections outright, drops
  tiny ones it cannot tell from false alarms — unless a reference image
  is supplied, in which case it keeps the tiny detections whose pixels
  actually differ from the reference (the tiny real defects) and still
  drops the hallucinated box.

Never used outside eval: production paths keep the wiring-selected
adapters. The wiring-bug risk this construction could mask is covered
by asserting per mode whether the judge ran, not just that numbers
differ (see ``test_eval_run.py``).
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from pycocotools import mask as mask_api

from app.schemas import DefectRuling, Detection, ProductProfile, RawMask, Verdict

REAL_SCORE = 0.9
FALSE_POSITIVE_SCORE = 0.55
FALSE_POSITIVE_BOX = (0, 0, 2, 2)  # x, y, w, h — fixture keeps a 4px margin
KEEP_AREA_PX = 8
REFERENCE_DIFF_MEAN = 8.0


def _encode(binary: np.ndarray) -> dict:
    fortran = np.asfortranarray(binary.astype(np.uint8))
    encoded = mask_api.encode(fortran)
    return {
        "size": [int(encoded["size"][0]), int(encoded["size"][1])],
        "counts": encoded["counts"].decode("utf-8"),
    }


def _red_components(image: Image.Image) -> list[np.ndarray]:
    pixels = np.asarray(image.convert("RGB")).astype(np.int16)
    red = (
        (pixels[:, :, 0] > 200)
        & (pixels[:, :, 1] < 100)
        & (pixels[:, :, 2] < 100)
    ).astype(np.uint8)
    count, labels = cv2.connectedComponents(red)[:2]
    return [(labels == index).astype(np.uint8) for index in range(1, count)]


class ScriptedFixtureSegmenter:
    """One mask per red component plus a fixed false-positive box."""

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        label = prompts[0] if prompts else "defect"
        masks = [
            RawMask(label=label, score=REAL_SCORE, mask_rle=_encode(part))
            for part in _red_components(image)
        ]
        width, height = image.size
        box = np.zeros((height, width), dtype=np.uint8)
        x, y, w, h = FALSE_POSITIVE_BOX
        box[y : y + h, x : x + w] = 1
        masks.append(
            RawMask(
                label="false-positive",
                score=FALSE_POSITIVE_SCORE,
                mask_rle=_encode(box),
            )
        )
        return masks


def _region_differs(
    image: Image.Image, reference: Image.Image, bbox: tuple[int, int, int, int]
) -> bool:
    x, y, w, h = (int(v) for v in bbox)
    current = np.asarray(image.convert("RGB")).astype(np.float32)
    baseline = np.asarray(
        reference.convert("RGB").resize(image.size)
    ).astype(np.float32)
    crop = current[y : y + h, x : x + w]
    ref_crop = baseline[y : y + h, x : x + w]
    if crop.size == 0:
        return False
    return bool(np.abs(crop - ref_crop).mean() > REFERENCE_DIFF_MEAN)


class ReferenceAwareJudge:
    """Size filter without a reference; reference diff check with one."""

    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        kept = [
            detection
            for detection in detections
            if detection.area_px >= KEEP_AREA_PX
            or (
                reference is not None
                and _region_differs(image, reference, detection.bbox)
            )
        ]
        dismissed = [d for d in detections if d not in kept]
        rulings = [
            DefectRuling(
                detection_id=detection.id,
                is_real_defect=True,
                rule_violated=profile.rules,
                reason="Scripted judge: candidate kept after size/reference check.",
            )
            for detection in kept
        ] + [
            DefectRuling(
                detection_id=detection.id,
                is_real_defect=False,
                rule_violated=None,
                reason="Scripted judge: tiny candidate matching the reference.",
            )
            for detection in dismissed
        ]
        with_reference = reference is not None
        if kept:
            return Verdict(
                verdict="FAIL",
                confidence=0.95 if with_reference else 0.8,
                rulings=rulings,
                missed_defects=[],
                summary=(
                    "Scripted judge: real defect confirmed"
                    + (" against the reference." if with_reference else ".")
                ),
            )
        return Verdict(
            verdict="PASS",
            confidence=0.95 if with_reference else 0.8,
            rulings=rulings,
            missed_defects=[],
            summary="Scripted judge: no real defect found.",
        )

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        return ProductProfile(
            id=category_name,
            name=category_name,
            defect_prompts=[],
            rules=sop_text,
        )
