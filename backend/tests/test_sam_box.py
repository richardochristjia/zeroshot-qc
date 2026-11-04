"""SAM box prompts: prompt string and decoding of a recorded live reply."""

from pathlib import Path

import numpy as np
import pytest
from pycocotools import mask as mask_api

from app.adapters.sam import SamSegmenter, box_prompt

FIXTURE = Path(__file__).parent / "fixtures" / "sam_box_response.txt"


def test_box_prompt_uses_inclusive_corners_and_image_size() -> None:
    assert box_prompt([(10, 20, 5, 4), (0, 0, 1, 1)], (900, 800)) == (
        "<0f>1<|box;x1=10;y1=20;x2=14;y2=23;w=900;h=800|>,"
        "2<|box;x1=0;y1=0;x2=0;y2=0;w=900;h=800|>"
    )


@pytest.mark.parametrize("count", [0, 17])
def test_box_prompt_rejects_bad_counts(count: int) -> None:
    with pytest.raises(ValueError):
        box_prompt([(0, 0, 2, 2)] * count, (10, 10))


def test_recorded_reply_decodes_to_mask_inside_the_box() -> None:
    text = FIXTURE.read_text()
    prompt = box_prompt([(616, 417, 145, 228)], (900, 900))
    (mask,) = SamSegmenter._parse_geometries({"output": [{"content": [{"text": text}]}]}, [prompt], 900, 900)
    assert mask.label == "1"
    binary = mask_api.decode(
        {"size": mask.mask_rle["size"], "counts": mask.mask_rle["counts"].encode()}
    )
    ys, xs = np.nonzero(binary)
    assert len(xs) > 0
    assert xs.min() >= 616 and xs.max() <= 760 and ys.min() >= 417 and ys.max() <= 644


def test_empty_reply_is_no_masks() -> None:
    assert SamSegmenter._parse_geometries({"output": [{"content": [{"text": " "}]}]}, ["<0f>1<|box;x1=0|>"], 10, 10) == []
