"""Synthetic defect generation CLI (M5).

``python -m app.synth.generate --profile bottle --defect scratch --n 10``

Loads one good image (the profile's reference image, else the committed
MVTec-layout fixture's good image), asks the image generator for ``n``
defective variants, and writes image+mask pairs to
``data/synth/{profile}/{defect}/``::

    data/synth/{profile}/_reference.png        copy of the good image
    data/synth/{profile}/{defect}/{i:03d}.png
    data/synth/{profile}/{defect}/{i:03d}_mask.png

Masks: generators exposing ``add_defect_with_mask`` (the fake) have
their mask stored verbatim; anything else (the real Muse Image mapping,
which returns no mask until inpainting support is confirmed) falls back
to a grayscale image-diff threshold against the good image. An empty
diff keeps the image, omits the mask, and logs the omission. The
threshold used is logged per image.

``--fake`` (the default) paints seeded shapes offline; ``--no-fake``
calls the real Muse Image adapter and needs keys in ``.env``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from app.adapters.fakes import FakeImageGenerator
from app.adapters.muse_image import MuseImageGenerator
from app.config import settings
from app.schemas import ProductProfile

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
PROFILES_DIR = BACKEND_DIR / "profiles"
FIXTURE_GOOD = (
    BACKEND_DIR / "tests" / "fixtures" / "mvtec" / "widget" / "train" / "good"
)

DIFF_THRESHOLD = 25.0


def load_good_image(profile_id: str) -> tuple[Image.Image, ProductProfile]:
    """Load the profile plus its good image (reference, else fixture)."""
    profile_path = PROFILES_DIR / f"{profile_id}.json"
    try:
        profile = ProductProfile.model_validate(
            json.loads(profile_path.read_text(encoding="utf-8"))
        )
    except OSError as exc:
        raise ValueError(
            f"unknown profile {profile_id!r}: no {profile_path} "
            f"(available: {sorted(p.stem for p in PROFILES_DIR.glob('*.json'))})"
        ) from exc
    if profile.reference_image:
        candidate = Path(profile.reference_image)
        if not candidate.is_absolute():
            candidate = BACKEND_DIR.parent / candidate
        if candidate.is_file():
            with Image.open(candidate) as raw:
                return raw.convert("RGB").copy(), profile
    fallbacks = sorted(FIXTURE_GOOD.glob("*.png"))
    if not fallbacks:
        raise ValueError(
            f"profile {profile_id!r} sets no reference_image and the "
            f"committed fixture under {FIXTURE_GOOD} is missing"
        )
    with Image.open(fallbacks[0]) as raw:
        return raw.convert("RGB").copy(), profile


def diff_mask(
    good: Image.Image, defective: Image.Image, threshold: float = DIFF_THRESHOLD
) -> np.ndarray:
    """Boolean defect mask from the per-pixel max-channel abs diff."""
    good_arr = np.asarray(good.convert("RGB")).astype(np.int16)
    bad_arr = np.asarray(defective.convert("RGB").resize(good.size)).astype(np.int16)
    return (np.abs(good_arr - bad_arr).max(axis=2) > threshold)


def generate_pairs(
    profile_id: str,
    defect: str,
    n: int,
    *,
    generator=None,
    out_root: str | Path | None = None,
    seed: int = 0,
    threshold: float = DIFF_THRESHOLD,
) -> list[tuple[Path, Path | None]]:
    """Generate ``n`` image+mask pairs; return ``(image, mask|None)`` paths."""
    if n < 1:
        raise ValueError(f"--n must be >= 1, got {n}")
    if generator is None:
        generator = FakeImageGenerator()
    good, _ = load_good_image(profile_id)
    root = Path(out_root) if out_root is not None else Path(settings.data_dir) / "synth"
    defect_dir = root / profile_id / defect
    defect_dir.mkdir(parents=True, exist_ok=True)
    reference_path = root / profile_id / "_reference.png"
    if not reference_path.is_file():
        good.save(reference_path)
    pairs: list[tuple[Path, Path | None]] = []
    for index in range(n):
        item_seed = f"{seed}/{index}"
        mask_file: Path = defect_dir / f"{index:03d}_mask.png"
        mask_path: Path | None = mask_file
        image_path = defect_dir / f"{index:03d}.png"
        if hasattr(generator, "add_defect_with_mask"):
            image, mask_image = generator.add_defect_with_mask(
                good, defect, seed=item_seed
            )
            print(f"{image_path}: mask=exact")
            if not bool((np.asarray(mask_image.convert("L")) > 0).any()):
                print(f"{image_path}: empty exact mask, omitting mask")
                mask_file.unlink(missing_ok=True)
                mask_path = None
            else:
                mask_image.save(mask_file)
        else:
            image = generator.add_defect(good, defect, None)
            mask = diff_mask(good, image, threshold)
            print(f"{image_path}: mask=diff(threshold={threshold})")
            if not bool(mask.any()):
                print(f"{image_path}: empty diff, omitting mask")
                mask_file.unlink(missing_ok=True)
                mask_path = None
            else:
                Image.fromarray((mask * 255).astype(np.uint8)).save(mask_file)
        image.save(image_path)
        pairs.append((image_path, mask_path))
    return pairs


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m app.synth.generate --profile P --defect D --n K``."""
    parser = argparse.ArgumentParser(description="Generate synthetic defects.")
    parser.add_argument("--profile", required=True, help="Profile id in backend/profiles/")
    parser.add_argument("--defect", required=True, help="Defect description")
    parser.add_argument("--n", type=int, required=True, help="Pair count")
    parser.add_argument(
        "--fake",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Seeded offline shapes (default) vs the real Muse Image adapter.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--synth-dir", default=str(Path(settings.data_dir) / "synth")
    )
    args = parser.parse_args(argv)
    try:
        generator = FakeImageGenerator() if args.fake else MuseImageGenerator()
        if not args.fake:
            from app.adapters.base import require_configured

            require_configured(
                model_id=settings.image_model_id,
                model_field="IMAGE_MODEL_ID",
                adapter="Image",
            )
        pairs = generate_pairs(
            args.profile,
            args.defect,
            args.n,
            generator=generator,
            out_root=args.synth_dir,
            seed=args.seed,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI reports, never tracebacks
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(pairs)} pairs to {args.synth_dir}/{args.profile}/{args.defect}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
