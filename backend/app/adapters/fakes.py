"""Deterministic fake adapters for tests and fake-mode smoke.

Same inputs always give the same outputs. No fake reads config or
touches the network. The fake segmenter is seeded by a hash of the
image bytes plus the prompt list and returns one RawMask per prompt.
Mask RLE counts are stored in the JSON-safe text form of the COCO
compressed RLE (the encoder's bytes decoded as UTF-8) so cache/API
serialization cannot break on them.
"""

import hashlib

import numpy as np
from PIL import Image, ImageDraw
from pycocotools import mask as mask_api

from app.schemas import DefectRuling, Detection, ProductProfile, RawMask, Verdict


def _seed_digest(image: Image.Image, prompts: list[str]) -> bytes:
    digest = hashlib.sha256()
    digest.update(image.tobytes())
    for prompt in prompts:
        digest.update(b"\x00")
        digest.update(prompt.encode("utf-8"))
    return digest.digest()


def _seeded_box(width: int, height: int, digest: bytes) -> tuple[int, int, int, int]:
    box_w = max(1, min(width, 1 + digest[0] % max(1, width // 2 + 1)))
    box_h = max(1, min(height, 1 + digest[1] % max(1, height // 2 + 1)))
    x0 = digest[2] % max(1, width - box_w + 1) if width > box_w else 0
    y0 = digest[3] % max(1, height - box_h + 1) if height > box_h else 0
    return x0, y0, box_w, box_h


class FakeSegmenter:
    """One deterministic RawMask per prompt, geometry clamped to the image."""

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        width, height = image.size
        seed = _seed_digest(image, prompts)
        masks: list[RawMask] = []
        for index, prompt in enumerate(prompts):
            per_prompt = hashlib.sha256(seed + index.to_bytes(4, "big")).digest()
            x0, y0, box_w, box_h = _seeded_box(width, height, per_prompt)
            binary = np.zeros((height, width), dtype=np.uint8, order="F")
            binary[y0 : y0 + box_h, x0 : x0 + box_w] = 1
            encoded = mask_api.encode(binary)
            mask_rle = {
                "size": [int(encoded["size"][0]), int(encoded["size"][1])],
                "counts": encoded["counts"].decode("utf-8"),
            }
            score = 0.55 + (per_prompt[4] / 255.0) * 0.4
            masks.append(RawMask(label=prompt, score=score, mask_rle=mask_rle))
        return masks


class FakeJudge:
    """Verdict that validates first-try: one ruling per input detection."""

    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        rulings = [
            DefectRuling(
                detection_id=detection.id,
                is_real_defect=False,
                rule_violated=None,
                reason="Fake judge: no rule violation found for this candidate.",
            )
            for detection in detections
        ]
        return Verdict(
            verdict="PASS",
            confidence=0.9,
            rulings=rulings,
            missed_defects=[],
            summary="Fake judge: all candidates dismissed, part passes.",
        )

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        return ProductProfile(
            id=category_name,
            name=category_name,
            defect_prompts=[],
            rules=sop_text,
        )


class FakeImageGenerator:
    """Deterministic same-size image with a hash-seeded mark."""

    def add_defect(
        self, good_image: Image.Image, defect_description: str, mask: Image.Image | None
    ) -> Image.Image:
        result = good_image.copy()
        width, height = result.size
        per_input = hashlib.sha256(
            good_image.tobytes() + b"\x00" + defect_description.encode("utf-8")
        ).digest()
        if result.mode in ("RGB", "RGBA") and width >= 2 and height >= 2:
            x0, y0, box_w, box_h = _seeded_box(width, height, per_input)
            draw = ImageDraw.Draw(result)
            draw.rectangle([x0, y0, x0 + box_w - 1, y0 + box_h - 1], fill=(255, 0, 0))
        return result
