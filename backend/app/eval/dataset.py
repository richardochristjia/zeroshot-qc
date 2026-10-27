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


def list_synth_categories(root: str | Path) -> list[str]:
    """Profile names: subdirs with defect-type image folders (M5 synth layout)."""
    root = Path(root)
    if not root.is_dir():
        return []
    names = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if any(
            subdir.is_dir() and _iter_images(subdir)
            for subdir in child.iterdir()
        ):
            names.append(child.name)
    return sorted(names)


def load_synth_category(
    root: str | Path, profile: str
) -> tuple[Path, list[EvalItem]]:
    """Load one synth profile's reference plus every defective pair (M5).

    Layout (written by ``app.synth.generate``)::

        <root>/<profile>/_reference.png
        <root>/<profile>/<defect_type>/{stem}.png
        <root>/<profile>/<defect_type>/{stem}_mask.png
    """
    root = Path(root)
    reference = root / profile / "_reference.png"
    if not reference.is_file():
        raise DatasetError(
            f"synthetic profile {profile!r}: no reference image at "
            f"{reference} (expected the synth layout "
            f"<root>/<profile>/_reference.png plus "
            f"<root>/<profile>/<defect>/*.png from app.synth.generate)"
        )
    items: list[EvalItem] = []
    profile_dir = root / profile
    for child in sorted(profile_dir.iterdir()):
        if not child.is_dir():
            continue
        for image_path in _iter_images(child):
            if image_path.stem.endswith("_mask"):
                continue
            mask_path = child / f"{image_path.stem}_mask{image_path.suffix}"
            items.append(
                EvalItem(
                    profile,
                    image_path,
                    "defective",
                    child.name,
                    mask_path if mask_path.is_file() else None,
                )
            )
    if not items:
        raise DatasetError(
            f"synthetic profile {profile!r}: no defect images under {profile_dir}"
        )
    return reference, items


def sample_synth_category(
    root: str | Path,
    profile: str,
    n_defective: int = 20,
    seed: int = 0,
) -> CategorySample:
    """Sample one synth profile: up to ``n_defective`` images per defect type.

    The RNG is seeded per ``(seed, profile, defect_type)`` so the sample
    is deterministic. Every item is defective: synth pairs carry no
    good images, so there is no ``n_good`` to honor.
    """
    reference, items = load_synth_category(root, profile)
    by_defect: dict[str, list[EvalItem]] = {}
    for item in items:
        by_defect.setdefault(item.defect_type or "defect", []).append(item)
    sampled: list[EvalItem] = []
    for defect_type in sorted(by_defect):
        pool = by_defect[defect_type]
        rng = random.Random(f"{seed}/{profile}/{defect_type}")
        rng.shuffle(pool)
        sampled.extend(pool[:n_defective])
    return CategorySample(profile, reference, sampled)


def sample_synth_dataset(
    root: str | Path,
    categories: list[str] | None = None,
    n_good: int = 10,
    n_defective: int = 20,
    seed: int = 0,
) -> list[CategorySample]:
    """Sample every requested synth profile (default: all under ``root``).

    Mirrors :func:`sample_dataset`'s signature (``n_good`` is accepted
    and ignored — synth pairs are all defective) so the eval runner can
    swap sources without reshaping the call.
    """
    del n_good  # synth pairs are all defective; nothing good to sample
    root = Path(root)
    if categories is None:
        categories = list_synth_categories(root)
    if not categories:
        raise DatasetError(
            f"no synthetic profiles found under {root} — generate some with "
            f"python -m app.synth.generate --profile <name> --defect <text> "
            f"--n <k> so that <root>/<profile>/_reference.png and "
            f"<root>/<profile>/<defect>/*.png exist, or point --synth-dir "
            f"at a directory that has them"
        )
    unknown = [name for name in categories if not (root / name).is_dir()]
    if unknown:
        raise DatasetError(
            f"unknown synthetic profiles {unknown}: no such directory under "
            f"{root} (available: {list_synth_categories(root)})"
        )
    return [
        sample_synth_category(root, name, n_defective, seed) for name in categories
    ]


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
