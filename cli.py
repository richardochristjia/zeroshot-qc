"""ZeroShot QC command line (M3: segment plus judge).

Canonical run: python cli.py inspect <image> --profile NAME [--fake]
Fake mode uses the deterministic fake adapters (cache ids
"fake-sam" / "fake-judge", same as smoke); real mode is the default.
`--no-judge` keeps the M2 segmentation-only output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Bootstrap the backend root onto sys.path so `python cli.py ...`
# from the repo root can import `app.*` (smoke-style bootstrap).
_BACKEND_ROOT = Path(__file__).resolve().parent / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from PIL import Image  # noqa: E402

from app.adapters.base import AdapterNotConfiguredError  # noqa: E402
from app.adapters.muse_spark import JudgeValidationError  # noqa: E402
from app.config import settings  # noqa: E402
from app.pipeline.inspect import load_profile, run_inspection  # noqa: E402
from app.pipeline.overlay import make_overlay  # noqa: E402
from app.pipeline.wiring import build_judge, build_segmenter  # noqa: E402


def _format_mm(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def _print_detection_line(detection) -> None:
    print(
        f"{detection.id} {detection.label} score={detection.score:.2f} "
        f"area_px={detection.area_px} length_px={detection.length_px:.1f} "
        f"area_mm2={_format_mm(detection.area_mm2)} "
        f"length_mm={_format_mm(detection.length_mm)}"
    )


def _print_verdict_block(verdict) -> None:
    print(f"verdict: {verdict.verdict} confidence={verdict.confidence:.2f}")
    for ruling in verdict.rulings:
        violated = ruling.rule_violated if ruling.rule_violated else "-"
        print(
            f"ruling {ruling.detection_id}: "
            f"real_defect={ruling.is_real_defect} "
            f"rule_violated={violated} reason={ruling.reason}"
        )
    for missed in verdict.missed_defects:
        print(f"missed: {missed}")
    print(f"summary: {verdict.summary}")


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        profile = load_profile(args.profile)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    image_path = Path(args.image)
    try:
        with Image.open(image_path) as raw:
            image = raw.convert("RGB").copy()
    except Exception as exc:
        print(f"error: could not open image {image_path}: {exc}", file=sys.stderr)
        return 1
    reference = None
    if args.reference is not None:
        reference_path = Path(args.reference)
        try:
            with Image.open(reference_path) as raw:
                reference = raw.convert("RGB").copy()
        except Exception as exc:
            print(
                f"error: could not open reference image {reference_path}: {exc}",
                file=sys.stderr,
            )
            return 1
    segmenter = build_segmenter(args.fake)
    try:
        if args.no_judge:
            detections = run_inspection(image, profile, segmenter)
            verdict = None
        else:
            judge = build_judge(args.fake)
            detections, verdict = run_inspection(
                image,
                profile,
                segmenter,
                judge=judge,
                rules=args.rules,
                reference=reference,
            )
    except AdapterNotConfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (JudgeValidationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    overlay_dir = Path(settings.data_dir) / "runs" / "cli"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    overlay = make_overlay(image, detections)
    overlay_path = overlay_dir / f"{image_path.stem}_overlay.png"
    overlay.save(overlay_path, format="PNG")
    if not detections:
        print("no detections")
    for detection in detections:
        _print_detection_line(detection)
    print(f"overlay: {overlay_path}")
    if verdict is not None:
        _print_verdict_block(verdict)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ZeroShot QC command line")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Segment an image and save the overlay")
    inspect.add_argument("image", help="Path to the image to inspect")
    inspect.add_argument("--profile", required=True, help="Profile name in backend/profiles/")
    inspect.add_argument(
        "--no-judge",
        action="store_true",
        help="Stop after segmentation with the M2 output (no verdict).",
    )
    inspect.add_argument(
        "--rules",
        default=None,
        help="Inline rules text replacing the profile rules for this run only.",
    )
    inspect.add_argument(
        "--reference",
        default=None,
        help="Path to a known-good reference image (else profile reference).",
    )
    inspect.add_argument(
        "--fake",
        action="store_true",
        help="Use the deterministic fake adapters instead of the real Meta API.",
    )
    inspect.set_defaults(func=cmd_inspect)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
