"""MVTec-layout dataset loader plus fixed-seed sampler (M4).

Expected layout (MVTec AD convention)::

    <root>/<category>/train/good/*.png
    <root>/<category>/test/good/*.png
    <root>/<category>/test/<defect_type>/*.png
    <root>/<category>/ground_truth/<defect_type>/<stem>_mask.png

The reference image is the first sorted ``train/good`` image. Test items
carry ``good``/``defective`` labels; defective items point at their
ground-truth mask. Sampling is deterministic: per category, up to
``n_good`` good plus ``n_defective`` defective test images drawn with a
seeded RNG, so the same seed always yields the same sample.

Missing or empty data raises :class:`DatasetError` with guidance text —
callers turn it into a clean message, never a traceback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


class DatasetError(Exception):
    """Raised when the dataset root cannot supply the requested sample."""


@dataclass(frozen=True)
class EvalItem:
    category: str
    image_path: Path
    label: str  # "good" | "defective"
    defect_type: str | None  # None for good images
    mask_path: Path | None  # None for good images


@dataclass(frozen=True)
class CategorySample:
    category: str
    reference_path: Path
    items: list[EvalItem]


def _iter_images(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def list_categories(root: str | Path) -> list[str]:
    """Sorted category names: subdirectories containing a ``test/`` split."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / "test").is_dir()
    )


def find_mask(root: Path, category: str, defect_type: str, stem: str) -> Path | None:
    """Locate the ground-truth mask for one defective test image.

    MVTec names masks ``<stem>_mask.png`` next to the defect folder;
    a same-stem fallback covers mirrors of that layout.
    """
    ground_truth = root / category / "ground_truth" / defect_type
    for candidate in (
        ground_truth / f"{stem}_mask.png",
        ground_truth / f"{stem}.png",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_category(root: str | Path, category: str) -> tuple[Path, list[EvalItem]]:
    """Load one category's reference image and every test item (unsampled)."""
    root = Path(root)
    category_dir = root / category
    train_good = category_dir / "train" / "good"
    references = _iter_images(train_good) if train_good.is_dir() else []
    if not references:
        raise DatasetError(
            f"category {category!r}: no reference image found under "
            f"{train_good} (expected MVTec layout "
            f"<root>/<category>/train/good/*.png)"
        )
    test_dir = category_dir / "test"
    if not test_dir.is_dir():
        raise DatasetError(
            f"category {category!r}: no test split under {test_dir}"
        )
    items: list[EvalItem] = []
    for child in sorted(test_dir.iterdir()):
        if not child.is_dir():
            continue
        for image_path in _iter_images(child):
            if child.name == "good":
                items.append(
                    EvalItem(category, image_path, "good", None, None)
                )
            else:
                items.append(
                    EvalItem(
                        category,
                        image_path,
                        "defective",
                        child.name,
                        find_mask(root, category, child.name, image_path.stem),
                    )
                )
    if not items:
        raise DatasetError(
            f"category {category!r}: no test images under {test_dir}"
        )
    return references[0], items


def sample_category(
    root: str | Path,
    category: str,
    n_good: int = 10,
    n_defective: int = 20,
    seed: int = 0,
) -> CategorySample:
    """Sample one category: up to ``n_good`` good + ``n_defective`` defective.

    The RNG is seeded per ``(seed, category)`` so the sample for a
    category does not shift when other categories are added or removed.
    Short pools yield all they have instead of raising.
    """
    reference_path, items = load_category(root, category)
    rng = random.Random(f"{seed}/{category}")
    good = [item for item in items if item.label == "good"]
    bad = [item for item in items if item.label == "defective"]
    rng.shuffle(good)
    rng.shuffle(bad)
    return CategorySample(
        category, reference_path, good[:n_good] + bad[:n_defective]
    )


def sample_dataset(
    root: str | Path,
    categories: list[str] | None = None,
    n_good: int = 10,
    n_defective: int = 20,
    seed: int = 0,
) -> list[CategorySample]:
    """Sample every requested category (default: all under ``root``)."""
    root = Path(root)
    if categories is None:
        categories = list_categories(root)
    if not categories:
        raise DatasetError(
            f"no MVTec categories found under {root} — download MVTec AD "
            f"(CC BY-NC-SA 4.0, non-commercial) into ./data/mvtec/ so that "
            f"<root>/<category>/train/good/ and <root>/<category>/test/ "
            f"exist, or point --mvtec-dir at a directory that has them"
        )
    unknown = [name for name in categories if not (root / name).is_dir()]
    if unknown:
        raise DatasetError(
            f"unknown categories {unknown}: no such directory under {root} "
            f"(available: {list_categories(root)})"
        )
    return [
        sample_category(root, name, n_good, n_defective, seed)
        for name in categories
    ]
