"""Deterministic generator for the committed MVTec-layout fixture (M4).

Writes two tiny synthetic categories (flat gray parts, pure-red painted
defects, exact masks) in MVTec layout::

    backend/tests/fixtures/mvtec/<category>/train/good/*.png
    backend/tests/fixtures/mvtec/<category>/test/good/*.png
    backend/tests/fixtures/mvtec/<category>/test/scratch/*.png
    backend/tests/fixtures/mvtec/<category>/ground_truth/scratch/*_mask.png

Every image is flat gray 128 so PNGs stay tiny and the scripted eval
fakes behave deterministically. Defects keep a 4px margin from the
image border, which also keeps them clear of the scripted segmenter's
fixed false-positive box at the top-left 2x2 corner. 16 of the 20
defective images carry a large defect, 4 a tiny 2x2 one — the tiny
cases are what separate the reference-backed judge from the plain one.

Re-running this script byte-reproduces the committed PNGs for the same
Pillow version; CI never needs to run it (the PNGs are committed).
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image

SIZE = (48, 48)
SHADE = 128
DEFECT = (255, 0, 0)
MARGIN = 4
N_TRAIN_GOOD = 2
N_TEST_GOOD = 10
N_LARGE = 16
N_SMALL = 4
CATEGORIES = ("widget", "gizmo")


def _flat() -> Image.Image:
    return Image.new("RGB", SIZE, (SHADE, SHADE, SHADE))


def _paint(gray: Image.Image, mask: Image.Image, x0: int, y0: int, w: int, h: int) -> None:
    gray_pixels = gray.load()
    mask_pixels = mask.load()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            gray_pixels[x, y] = DEFECT
            mask_pixels[x, y] = 255


def generate(root: str | Path, categories: tuple[str, ...] = CATEGORIES) -> list[Path]:
    """Generate the fixture under ``root``; returns the written files."""
    root = Path(root)
    written: list[Path] = []

    def _save(image: Image.Image, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        written.append(path)

    for category in categories:
        rng = random.Random(f"fixture/{category}")
        base = root / category
        for index in range(N_TRAIN_GOOD):
            _save(_flat(), base / "train" / "good" / f"{index:03d}.png")
        for index in range(N_TEST_GOOD):
            _save(_flat(), base / "test" / "good" / f"{index:03d}.png")
        sizes = [
            (
                rng.randint(6, 12),
                rng.randint(6, 12),
            )
            for _ in range(N_LARGE)
        ] + [(2, 2)] * N_SMALL
        # Shuffle so tiny defects are not always last; the seeded order
        # is still deterministic.
        order_rng = random.Random(f"fixture/{category}/order")
        order_rng.shuffle(sizes)
        for index, (w, h) in enumerate(sizes):
            x0 = rng.randint(MARGIN, SIZE[0] - MARGIN - w)
            y0 = rng.randint(MARGIN, SIZE[1] - MARGIN - h)
            gray = _flat()
            mask = Image.new("L", SIZE, 0)
            _paint(gray, mask, x0, y0, w, h)
            name = f"{index:03d}.png"
            _save(gray, base / "test" / "scratch" / name)
            _save(mask, base / "ground_truth" / "scratch" / f"{index:03d}_mask.png")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the M4 fixture PNGs.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent),
        help="Fixture root to write (default: the directory of this script).",
    )
    args = parser.parse_args()
    written = generate(args.root)
    print(f"wrote {len(written)} files under {args.root}")


if __name__ == "__main__":
    main()
