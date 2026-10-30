"""Build backend/demo/ (the committed keyless-demo bundle) from data/.

Run from ``backend/`` with real keys in the repo-root ``.env``:
``.venv/bin/python scripts/build_demo.py``. Copies profile references
verbatim (their bytes are part of the judge cache key), downscales eval
and synth images, then inspects a few samples with the real adapters so
the cache holds exactly the entries the samples replay. The API key is
never written; cache entries hold only result JSON.
"""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.pipeline.cache import DiskCache  # noqa: E402
from app.pipeline.inspect import PROFILES_DIR, load_profile, run_inspection  # noqa: E402
from app.pipeline.wiring import build_judge, build_segmenter  # noqa: E402

SRC = Path(settings.data_dir)
OUT = Path(__file__).resolve().parents[1] / "demo"
RUNS = [
    "20261027T090316Z-sam_only",
    "20261027T091346Z-sam_judge",
    "20261027T094406Z-sam_judge_ref",
]
# (profile, test subdir, index) -> one good and one defective each
SAMPLES = [
    ("bottle", "good", "bottle/test/good/000.png", "Bottle, good"),
    ("bottle", "broken_large", "bottle/test/broken_large/000.png", "Bottle, broken"),
    ("screw", "good", "screw/test/good/000.png", "Screw, good"),
    ("screw", "scratch_head", "screw/test/scratch_head/000.png", "Screw, scratched head"),
    ("metal_nut", "good", "metal_nut/test/good/000.png", "Metal nut, good"),
    ("metal_nut", "bent", "metal_nut/test/bent/000.png", "Metal nut, bent"),
]
MAX_BYTES = 40 * 1024 * 1024
LICENSE = """# MVTec AD attribution

The images under `mvtec/`, `samples/` and `synth/` derive from the MVTec
Anomaly Detection dataset (MVTec AD), (c) MVTec Software GmbH, licensed
under CC BY-NC-SA 4.0: https://creativecommons.org/licenses/by-nc-sa/4.0/
Dataset: https://www.mvtec.com/company/research/datasets/mvtec-ad

This is a downscaled subset (profile references are original bytes).
Non-commercial use only; derivatives must keep this licence.
"""


def _save_small(src: Path, dst: Path, side: int, nearest: bool = False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.load()
        im.thumbnail((side, side), Image.NEAREST if nearest else Image.LANCZOS)
        im.save(dst, format="PNG")


def main() -> None:
    if not settings.meta_api_key:
        sys.exit("META_API_KEY is empty: fill the repo-root .env, then rerun.")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    refs = {load_profile(p.stem).reference_image for p in PROFILES_DIR.glob("*.json")}
    for ref in sorted(r for r in refs if r):
        (OUT / ref).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / ref, OUT / ref)

    images: set[str] = set()
    for run in RUNS:
        shutil.copytree(SRC / "runs" / run, OUT / "runs" / run)
        for line in (SRC / "runs" / run / "results.jsonl").read_text().splitlines():
            if line.strip():
                images.add(json.loads(line)["image"])
    for img in sorted(images):
        _save_small(SRC / "mvtec" / img, OUT / "mvtec" / img, 256)

    for f in sorted((SRC / "synth" / "bottle").rglob("*.png")):
        _save_small(f, OUT / f.relative_to(SRC), 512, nearest=f.name.endswith("_mask.png"))

    cache = DiskCache(OUT / "cache")
    segmenter = build_segmenter(False, cache)
    judge = build_judge(False, cache)
    # Resolve references against the bundle so the judge sees the shipped bytes.
    object.__setattr__(settings, "data_dir", str(OUT))
    manifest = []
    for pid, kind, rel, label in SAMPLES:
        name = f"{pid}-{kind}.png"
        _save_small(SRC / "mvtec" / rel, OUT / "samples" / name, 512)
        with Image.open(OUT / "samples" / name) as im:
            img = im.convert("RGB").copy()
        _, verdict = run_inspection(img, load_profile(pid), segmenter, judge=judge)
        manifest.append(
            {"id": f"{pid}-{kind}", "label": label, "profile_id": pid,
             "file": f"samples/{name}", "expect": verdict.verdict}
        )
        print(f"{name}: {verdict.verdict}")
    (OUT / "samples.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "LICENSE-MVTEC.md").write_text(LICENSE)

    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"bundle: {size / 1e6:.1f} MB")
    if size > MAX_BYTES:
        sys.exit("bundle exceeds 40 MB")


if __name__ == "__main__":
    main()
