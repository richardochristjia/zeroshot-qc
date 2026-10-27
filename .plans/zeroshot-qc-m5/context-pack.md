# Context pack

BASE: main
CHANGED: 14 files, +840/-21

## What this change does
M5 adds synthetic defect generation (`python -m app.synth.generate`, fake seeded shapes offline) plus SOP-to-profile drafting (`POST /api/profiles/from-sop`, draft only, never saved), and lets eval score synthetic pairs (`--data synth`) through the existing sampler/metrics/ablations. Plan: `.plans/zeroshot-qc-m5/plan.md`.

## Files
- `backend/app/synth/__init__.py` — new package marker for the synth generator
- `backend/app/synth/generate.py:88` — `generate_pairs` CLI core; exact-mask verbatim vs diff-threshold fallback (`diff_mask` at `backend/app/synth/generate.py:79`, `DIFF_THRESHOLD = 25.0` at `backend/app/synth/generate.py:47`); layout writer for `data/synth/{profile}/{defect}/`
- `backend/app/adapters/fakes.py` — `FakeImageGenerator.add_defect_with_mask` upgrade: seeded rectangle/ellipse/bar shapes with exact masks; `add_defect` delegates
- `backend/app/prompts/sop_to_profile.md` — new SOP-to-profile prompt template (id/name/defect_prompts/rules rules, `{schema}` placeholder)
- `backend/app/prompts/__init__.py` — `render_sop_prompt` renders the new template with the `ProductProfile` JSON schema
- `backend/app/adapters/muse_spark.py:73` — `sop_to_profile` with judge-style retry-once validation; `_validate_profile` at `backend/app/adapters/muse_spark.py:106` slug-fills empty id; `_sop_via_meta_api` at `backend/app/adapters/muse_spark.py:117` (still `TODO(meta-docs)`); reuses `JudgeValidationError` at `backend/app/adapters/muse_spark.py:33`
- `backend/app/main.py:33` — `POST /api/profiles/from-sop` (`SopDraftRequest` at `backend/app/main.py:14`, `_get_sop_judge` seam at `backend/app/main.py:19`); double validation failure → 422
- `backend/app/eval/dataset.py` — `list_synth_categories` / `load_synth_category` / `sample_synth_category` / `sample_synth_dataset` synth layout reader (all-defective, `n_good` accepted-and-ignored)
- `backend/app/eval/run.py:42` — `DATA_CHOICES`, `source` param at `backend/app/eval/run.py:115`, `--data` at `backend/app/eval/run.py:245`, `--synth-dir` at `backend/app/eval/run.py:249`, `summary["source"]` at `backend/app/eval/run.py:196`
- `backend/tests/test_synth.py` — determinism, verbatim masks, diff fallback, empty-diff behavior, layout paths, `diff_mask` unit
- `backend/tests/test_sop.py` — unsaved draft, garbage-twice 422, retry-once, double-failure error, unconfigured-adapter guard, empty-body 422
- `backend/tests/test_adapters.py` — former `NotImplementedError` stub test now asserts `AdapterNotConfiguredError` without HTTP
- `docs/EVAL_NOTES.md` — synthetic section (layout, fake vs real, all-defective metric caveats)
- `.agents/RECORD.md` — 3 approved entries (synth pairs, diff-mask, from-sop draft)

## API contracts
- `POST /api/profiles/from-sop` → 200 `ProductProfile`, never writes to `backend/profiles/`; double validation failure → 422 `{"detail": ...}` mirroring the judge's error shape; empty `sop_text`/`category_name` → 422 via `SopDraftRequest` (`Field(min_length=1)`)
  declared in `backend/app/main.py:14` (request), `backend/app/schemas.py:26` (`ProductProfile`)
- CLI: `python -m app.synth.generate --profile P --defect D --n K [--fake/--no-fake] [--seed S] [--synth-dir D]`; exit 2 on `ValueError`/any error, never tracebacks
  declared in `backend/app/synth/generate.py:147`
- Eval: `python -m app.eval.run --data synth|mvtec [--synth-dir D]`; synth root layout `<root>/<profile>/_reference.png` + `<root>/<profile>/<defect>/*.png` / `*_mask.png`
  declared in `backend/app/eval/run.py:245`, reader in `backend/app/eval/dataset.py`

## Test entry points
- `backend/tests/test_synth.py` — `cd backend && .venv/bin/python -m pytest -q backend/tests/test_synth.py`
- `backend/tests/test_sop.py` — `cd backend && .venv/bin/python -m pytest -q backend/tests/test_sop.py`
- `backend/tests/test_adapters.py` (sop guard) — `cd backend && .venv/bin/python -m pytest -q`
- Full suite: `cd backend && .venv/bin/python -m pytest -q` (project venv, never host global)

## Acceptance criteria
1. `python -m app.synth.generate --profile bottle --defect scratch --n 10` in fake mode writes 10 image+mask pairs; rerun is deterministic. Check: CLI runs in Verification.
2. Eval `--data synth` completes all three modes with a `summary.json`. Check: eval run in Verification.
3. `POST /api/profiles/from-sop` returns a valid draft and saves nothing; garbage twice returns 422. Check: TestClient calls in Verification.
4. `pytest` green; `data/` outputs gitignored; no secrets in new source. Check: suite plus grep guard.
5. manual: the same three against the real models with keys plus docs. Human steps: set `.env`, generate with the real image model and eyeball quality, paste a real SOP paragraph and judge the draft.

## Do not re-derive
- `backend/app/adapters/muse_image.py` is UNCHANGED in this branch: the plan said the real mapping stays isolated behind `TODO(meta-docs)`, and it does — the fake upgrade landed in `backend/app/adapters/fakes.py` instead. Reviewers expecting a `muse_image.py` diff will not find one.
- Exact-mask vs diff-mask decision is capability-sniffing: `hasattr(generator, "add_defect_with_mask")` in `backend/app/synth/generate.py` — the fake stores verbatim, the real adapter falls back to diff threshold 25.0 logged per image.
- Empty diff keeps the image, omits the mask (`mask_path = None`), and logs; it is not an error.
- Synth pairs are ALL defective: `sample_synth_dataset` accepts `n_good` and ignores it, so recall ≈ 1.0 and AUROC is 0.5 by construction — not a regression.
- `from-sop` never persists: no `profiles/` write on any path; `_get_sop_judge` in `backend/app/main.py:19` is the test seam.
- Empty-string id is backfilled from `category_name` via `_slugify_category`, not rejected.
- `data/` is gitignored (`.gitignore:1-2`); generated `data/synth/` pairs must never be committed.

## Diff
```diff
diff --git a/.agents/RECORD.md b/.agents/RECORD.md
index a88cfd4..921981a 100644
--- a/.agents/RECORD.md
+++ b/.agents/RECORD.md
@@ -53,3 +53,6 @@ Entries are added or amended **only with human approval**.
 - (eval) Eval currently samples 10 good plus 20 defective images per category with a fixed seed and scores precision, recall, F1, accuracy, AUROC over the fail score, and pixel IoU on defectives.
 - (eval) Ablation modes currently differ only in judge wiring: any-detection FAIL without a judge, judge without a reference image, and judge with the category reference image.
 - (eval) Eval runs currently persist per-image results.jsonl plus a summary.json of per-category and overall metrics under data/runs/{run_id}.
+- (synth) Synth generation currently writes deterministic image+mask pairs under data/synth/{profile}/{defect}/, storing exact generator masks verbatim and deriving missing ones by image-diff threshold.
+- (eval) Eval currently accepts --data synth to score synthetic pairs through the same sampler, metrics, and ablation modes as MVTec.
+- (profiles) New profiles are currently draftable from an SOP paragraph via POST /api/profiles/from-sop, which persists nothing and returns 422 when validation fails twice.
diff --git a/backend/app/adapters/fakes.py b/backend/app/adapters/fakes.py
index aeafe8a..4278927 100644
--- a/backend/app/adapters/fakes.py
+++ b/backend/app/adapters/fakes.py
@@ -127,18 +127,55 @@ class FakeJudge:
 
 
 class FakeImageGenerator:
-    """Deterministic same-size image with a hash-seeded mark."""
+    """Seeded visible shapes with exact masks (M5).
+
+    ``add_defect`` keeps the ``ImageGenerator`` contract (image only);
+    ``add_defect_with_mask`` additionally returns the exact defect mask
+    (white shape on black, same size as the image) so the synth
+    generator can store it verbatim instead of deriving one by diff.
+    Same inputs always give the same outputs. No config, no network.
+    """
 
     def add_defect(
         self, good_image: Image.Image, defect_description: str, mask: Image.Image | None
     ) -> Image.Image:
-        result = good_image.copy()
-        width, height = result.size
-        per_input = hashlib.sha256(
-            good_image.tobytes() + b"\x00" + defect_description.encode("utf-8")
+        image, _ = self.add_defect_with_mask(good_image, defect_description)
+        return image
+
+    def add_defect_with_mask(
+        self, good_image: Image.Image, defect_description: str, *, seed: str = ""
+    ) -> tuple[Image.Image, Image.Image]:
+        base = good_image.convert("RGB").copy()
+        width, height = base.size
+        digest = hashlib.sha256(
+            b"\x00".join(
+                (
+                    base.tobytes(),
+                    defect_description.encode("utf-8"),
+                    seed.encode("utf-8"),
+                )
+            )
         ).digest()
-        if result.mode in ("RGB", "RGBA") and width >= 2 and height >= 2:
-            x0, y0, box_w, box_h = _seeded_box(width, height, per_input)
-            draw = ImageDraw.Draw(result)
-            draw.rectangle([x0, y0, x0 + box_w - 1, y0 + box_h - 1], fill=(255, 0, 0))
-        return result
+        box_w = max(4, min(width, 4 + digest[0] % (max(4, width // 3 + 1))))
+        box_h = max(4, min(height, 4 + digest[1] % (max(4, height // 3 + 1))))
+        x0 = digest[2] % max(1, width - box_w + 1) if width > box_w else 0
+        y0 = digest[3] % max(1, height - box_h + 1) if height > box_h else 0
+        x1, y1 = x0 + box_w - 1, y0 + box_h - 1
+        shape = digest[4] % 3  # 0: rectangle, 1: ellipse, 2: diagonal bar
+        paint = (255, 0, 0)
+        result = base.copy()
+        mask = Image.new("L", (width, height), 0)
+        if shape == 0:
+            ImageDraw.Draw(result).rectangle([x0, y0, x1, y1], fill=paint)
+            ImageDraw.Draw(mask).rectangle([x0, y0, x1, y1], fill=255)
+        elif shape == 1:
+            ImageDraw.Draw(result).ellipse([x0, y0, x1, y1], fill=paint)
+            ImageDraw.Draw(mask).ellipse([x0, y0, x1, y1], fill=255)
+        else:
+            ImageDraw.Draw(result).line(
+                [x0, y0, x1, y1], fill=paint, width=max(1, min(box_w, box_h) // 3)
+            )
+            ImageDraw.Draw(mask).line(
+                [x0, y0, x1, y1], fill=255, width=max(1, min(box_w, box_h) // 3)
+            )
+        return result, mask
diff --git a/backend/app/adapters/muse_spark.py b/backend/app/adapters/muse_spark.py
index e3b9e7c..5564d69 100644
--- a/backend/app/adapters/muse_spark.py
+++ b/backend/app/adapters/muse_spark.py
@@ -5,23 +5,31 @@ for it lives entirely in ``MuseSparkJudge._judge_via_meta_api`` so it
 can be corrected in one place when the official Meta Model API docs
 arrive (HANDOFF §2); every uncertain detail there is marked
 TODO(meta-docs) and built only from the shared settings values.
-``sop_to_profile`` is an explicit M5 stub (plan: SOP parsing lands M5).
+M5: ``sop_to_profile`` drafts a profile with the judge's retry-once
+validation pattern via ``prompts/sop_to_profile.md``.
 
 M3: ``judge`` renders the HANDOFF §7 prompt, validates the response
 against ``Verdict``, retries once with the validation error appended,
 and raises ``JudgeValidationError`` on the second failure.
 """
 
+import re
+
 import httpx
 from PIL import Image
 from pydantic import ValidationError
 
 from app.adapters.base import encode_image_b64, require_configured
 from app.config import settings
-from app.prompts import render_judge_prompt
+from app.prompts import render_judge_prompt, render_sop_prompt
 from app.schemas import Detection, ProductProfile, Verdict
 
 
+def _slugify_category(category_name: str) -> str:
+    slug = re.sub(r"[^a-z0-9]+", "_", category_name.strip().lower()).strip("_")
+    return slug or "product"
+
+
 class JudgeValidationError(ValueError):
     """Both judge attempts returned output that failed Verdict validation."""
 
@@ -63,8 +71,74 @@ class MuseSparkJudge:
                 ) from second_error
 
     def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
-        # M5: SOP-to-profile parsing lands in M5; no behaviour in M1.
-        raise NotImplementedError("sop_to_profile is not implemented until M5")
+        """Draft a ProductProfile from an SOP paragraph (M5).
+
+        Same retry-once validation pattern as :meth:`judge`: a first
+        failure reruns with the validation error appended, a second
+        raises :class:`JudgeValidationError`. Never saves anything.
+        """
+        require_configured(
+            model_id=settings.judge_model_id,
+            model_field="JUDGE_MODEL_ID",
+            adapter="Judge",
+        )
+        prompt = render_sop_prompt(sop_text, category_name)
+        try:
+            return self._validate_profile(
+                self._sop_via_meta_api(prompt), category_name
+            )
+        except ValidationError as first_error:
+            retry_prompt = (
+                f"{prompt}\n\nYour previous response failed validation:\n"
+                f"{first_error}\nReturn only JSON matching the schema."
+            )
+            try:
+                return self._validate_profile(
+                    self._sop_via_meta_api(retry_prompt), category_name
+                )
+            except ValidationError as second_error:
+                raise JudgeValidationError(
+                    "sop_to_profile output failed ProductProfile "
+                    f"validation twice: {second_error}"
+                ) from second_error
+
+    @staticmethod
+    def _validate_profile(data: object, category_name: str) -> ProductProfile:
+        profile = ProductProfile.model_validate(data)
+        if not profile.id.strip():
+            profile = profile.model_copy(
+                update={
+                    "id": _slugify_category(category_name),
+                    "name": category_name,
+                }
+            )
+        return profile
+
+    def _sop_via_meta_api(self, prompt: str) -> object:
+        # TODO(meta-docs): everything in this function is a placeholder
+        # mapping to be corrected against the official Meta Model API
+        # docs. Do not treat the endpoint, payload shape, auth scheme,
+        # structured-output mode, or response shape below as fact.
+        # TODO(meta-docs): endpoint path — the base URL from settings is
+        # used verbatim until the docs name the SOP parsing path.
+        url = settings.meta_api_base_url
+
+        # TODO(meta-docs): request payload shape and field names, and
+        # whether a structured-output / JSON mode exists.
+        payload = {
+            "model": settings.judge_model_id,
+            "prompt": prompt,
+        }
+        # TODO(meta-docs): auth scheme — Bearer [REDACTED] header assumed.
+        headers = {"Authorization": f"Bearer {settings.meta_api_key}"}
+        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
+        response.raise_for_status()
+        # TODO(meta-docs): response shape — a ProductProfile JSON object,
+        # possibly nested under a result/profile key, is assumed.
+        data = response.json()
+        if isinstance(data, dict) and isinstance(data.get("profile"), dict):
+            data = data["profile"]
+        return data
 
     def _judge_via_meta_api(
         self,
diff --git a/backend/app/eval/dataset.py b/backend/app/eval/dataset.py
index 272d152..57fc4fa 100644
--- a/backend/app/eval/dataset.py
+++ b/backend/app/eval/dataset.py
@@ -149,6 +149,129 @@ def sample_category(
     )
 
 
+def list_synth_categories(root: str | Path) -> list[str]:
+    """Profile names: subdirs with defect-type image folders (M5 synth layout)."""
+    root = Path(root)
+    if not root.is_dir():
+        return []
+    names = []
+    for child in root.iterdir():
+        if not child.is_dir() or child.name.startswith("_"):
+            continue
+        if any(
+            subdir.is_dir() and _iter_images(subdir)
+            for subdir in child.iterdir()
+        ):
+            names.append(child.name)
+    return sorted(names)
+
+
+def load_synth_category(
+    root: str | Path, profile: str
+) -> tuple[Path, list[EvalItem]]:
+    """Load one synth profile's reference plus every defective pair (M5).
+
+    Layout (written by ``app.synth.generate``)::
+
+        <root>/<profile>/_reference.png
+        <root>/<profile>/<defect_type>/{stem}.png
+        <root>/<profile>/<defect_type>/{stem}_mask.png
+    """
+    root = Path(root)
+    reference = root / profile / "_reference.png"
+    if not reference.is_file():
+        raise DatasetError(
+            f"synthetic profile {profile!r}: no reference image at "
+            f"{reference} (expected the synth layout "
+            f"<root>/<profile>/_reference.png plus "
+            f"<root>/<profile>/<defect>/*.png from app.synth.generate)"
+        )
+    items: list[EvalItem] = []
+    profile_dir = root / profile
+    for child in sorted(profile_dir.iterdir()):
+        if not child.is_dir():
+            continue
+        for image_path in _iter_images(child):
+            if image_path.stem.endswith("_mask"):
+                continue
+            mask_path = child / f"{image_path.stem}_mask{image_path.suffix}"
+            items.append(
+                EvalItem(
+                    profile,
+                    image_path,
+                    "defective",
+                    child.name,
+                    mask_path if mask_path.is_file() else None,
+                )
+            )
+    if not items:
+        raise DatasetError(
+            f"synthetic profile {profile!r}: no defect images under {profile_dir}"
+        )
+    return reference, items
+
+
+def sample_synth_category(
+    root: str | Path,
+    profile: str,
+    n_defective: int = 20,
+    seed: int = 0,
+) -> CategorySample:
+    """Sample one synth profile: up to ``n_defective`` images per defect type.
+
+    The RNG is seeded per ``(seed, profile, defect_type)`` so the sample
+    is deterministic. Every item is defective: synth pairs carry no
+    good images, so there is no ``n_good`` to honor.
+    """
+    reference, items = load_synth_category(root, profile)
+    by_defect: dict[str, list[EvalItem]] = {}
+    for item in items:
+        by_defect.setdefault(item.defect_type or "defect", []).append(item)
+    sampled: list[EvalItem] = []
+    for defect_type in sorted(by_defect):
+        pool = by_defect[defect_type]
+        rng = random.Random(f"{seed}/{profile}/{defect_type}")
+        rng.shuffle(pool)
+        sampled.extend(pool[:n_defective])
+    return CategorySample(profile, reference, sampled)
+
+
+def sample_synth_dataset(
+    root: str | Path,
+    categories: list[str] | None = None,
+    n_good: int = 10,
+    n_defective: int = 20,
+    seed: int = 0,
+) -> list[CategorySample]:
+    """Sample every requested synth profile (default: all under ``root``).
+
+    Mirrors :func:`sample_dataset`'s signature (``n_good`` is accepted
+    and ignored — synth pairs are all defective) so the eval runner can
+    swap sources without reshaping the call.
+    """
+    del n_good  # synth pairs are all defective; nothing good to sample
+    root = Path(root)
+    if categories is None:
+        categories = list_synth_categories(root)
+    if not categories:
+        raise DatasetError(
+            f"no synthetic profiles found under {root} — generate some with "
+            f"python -m app.synth.generate --profile <name> --defect <text> "
+            f"--n <k> so that <root>/<profile>/_reference.png and "
+            f"<root>/<profile>/<defect>/*.png exist, or point --synth-dir "
+            f"at a directory that has them"
+        )
+    unknown = [name for name in categories if not (root / name).is_dir()]
+    if unknown:
+        raise DatasetError(
+            f"unknown synthetic profiles {unknown}: no such directory under "
+            f"{root} (available: {list_synth_categories(root)})"
+        )
+    return [
+        sample_synth_category(root, name, n_defective, seed) for name in categories
+    ]
+
+
 def sample_dataset(
     root: str | Path,
     categories: list[str] | None = None,
diff --git a/backend/app/eval/run.py b/backend/app/eval/run.py
index 267c780..55b79f0 100644
--- a/backend/app/eval/run.py
+++ b/backend/app/eval/run.py
@@ -29,7 +29,7 @@ import numpy as np
 from PIL import Image
 
 from app.config import settings
-from app.eval.dataset import DatasetError, sample_dataset
+from app.eval.dataset import DatasetError, sample_dataset, sample_synth_dataset
 from app.eval.fakes import ReferenceAwareJudge, ScriptedFixtureSegmenter
 from app.eval.metrics import fail_score, pixel_iou, summarize
 from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache
@@ -39,6 +39,7 @@ from app.schemas import ProductProfile
 
 MODES = ("sam_only", "sam_judge", "sam_judge_ref")
 ADAPTER_CHOICES = ("real", "fake", "scripted")
+DATA_CHOICES = ("mvtec", "synth")
 
 EVAL_RULES = "FAIL any visible scratch, stain, or surface damage; PASS otherwise."
 
@@ -111,6 +112,7 @@ def run_eval(
     root: str | Path,
     categories: list[str] | None = None,
     mode: str = "sam_judge_ref",
+    source: str = "mvtec",
     seed: int = 0,
     n_good: int = 10,
     n_defective: int = 20,
@@ -125,8 +127,13 @@ def run_eval(
     """Run one ablation mode; write ``results.jsonl`` + ``summary.json``."""
     if mode not in MODES:
         raise ValueError(f"unknown mode {mode!r}: expected one of {MODES}")
+    if source not in DATA_CHOICES:
+        raise ValueError(f"unknown source {source!r}: expected one of {DATA_CHOICES}")
     root = Path(root)
-    samples = sample_dataset(root, categories, n_good, n_defective, seed)
+    if source == "synth":
+        samples = sample_synth_dataset(root, categories, n_good, n_defective, seed)
+    else:
+        samples = sample_dataset(root, categories, n_good, n_defective, seed)
     cache = DiskCache(cache_dir)
     segmenter, judge = _resolve_adapters(
         adapter, cache, segmenter_inner, judge_inner
@@ -186,6 +193,7 @@ def run_eval(
     summary = {
         "run_id": run_id,
         "mode": mode,
+        "source": source,
         "adapter": adapter,
         "seed": seed,
         "categories": [sample.category for sample in samples],
@@ -234,8 +242,12 @@ def main(argv: list[str] | None = None) -> int:
     parser.add_argument("--n-good", type=int, default=10)
     parser.add_argument("--n-defective", type=int, default=20)
     parser.add_argument("--adapter", choices=ADAPTER_CHOICES, default="scripted")
+    parser.add_argument("--data", choices=DATA_CHOICES, default="mvtec")
     parser.add_argument("--rules", default=EVAL_RULES)
     parser.add_argument("--mvtec-dir", default=settings.mvtec_dir)
+    parser.add_argument(
+        "--synth-dir", default=str(Path(settings.data_dir) / "synth")
+    )
     parser.add_argument(
         "--cache-dir", default=str(Path(settings.data_dir) / "cache")
     )
@@ -249,9 +261,10 @@ def main(argv: list[str] | None = None) -> int:
     )
     try:
         _, summary = run_eval(
-            root=args.mvtec_dir,
+            root=args.synth_dir if args.data == "synth" else args.mvtec_dir,
             categories=args.categories,
             mode=args.mode,
+            source=args.data,
             seed=args.seed,
             n_good=args.n_good,
             n_defective=args.n_defective,
diff --git a/backend/app/main.py b/backend/app/main.py
index 03dbab5..d3e8268 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -1,12 +1,25 @@
 """FastAPI application entry point. Health endpoint lives here in M1."""
 
-from fastapi import FastAPI
+from fastapi import FastAPI, HTTPException
 from fastapi.middleware.cors import CORSMiddleware
+from pydantic import BaseModel, Field
 
+from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge
 from app.config import settings
+from app.schemas import ProductProfile
 
 app = FastAPI()
 
+
+class SopDraftRequest(BaseModel):
+    sop_text: str = Field(min_length=1)
+    category_name: str = Field(min_length=1)
+
+
+def _get_sop_judge() -> MuseSparkJudge:
+    """Indirection so tests can substitute a fake without touching HTTP."""
+    return MuseSparkJudge()
+
 _origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
 app.add_middleware(
     CORSMiddleware,
@@ -17,6 +30,19 @@ app.add_middleware(
 )
 
 
+@app.post("/api/profiles/from-sop", response_model=ProductProfile)
+def profiles_from_sop(body: SopDraftRequest) -> ProductProfile:
+    """Draft a profile from an SOP paragraph (M5). Never saves anything.
+
+    Two consecutive validation failures surface as 422, mirroring the
+    judge's error shape.
+    """
+    try:
+        return _get_sop_judge().sop_to_profile(body.sop_text, body.category_name)
+    except JudgeValidationError as exc:
+        raise HTTPException(status_code=422, detail=str(exc)) from exc
+
+
 @app.get("/api/health")
 def health() -> dict:
     return {
diff --git a/backend/app/prompts/__init__.py b/backend/app/prompts/__init__.py
index 86a1cfc..b47447a 100644
--- a/backend/app/prompts/__init__.py
+++ b/backend/app/prompts/__init__.py
@@ -12,9 +12,10 @@ import json
 import re
 from pathlib import Path
 
-from app.schemas import Detection, Verdict
+from app.schemas import Detection, ProductProfile, Verdict
 
 _JUDGE_TEMPLATE = Path(__file__).resolve().parent / "judge.md"
+_SOP_TEMPLATE = Path(__file__).resolve().parent / "sop_to_profile.md"
 
 
 def _format_mm(value: float | None) -> str:
@@ -38,6 +39,21 @@ def build_detections_table(detections: list[Detection]) -> str:
     return "\n".join(lines)
 
 
+def render_sop_prompt(sop_text: str, category_name: str) -> str:
+    """Render ``sop_to_profile.md`` with the profile schema and SOP text."""
+    template = _SOP_TEMPLATE.read_text(encoding="utf-8")
+    values = {
+        "{schema}": json.dumps(ProductProfile.model_json_schema(), sort_keys=True),
+        "{sop_text}": sop_text,
+        "{category_name}": category_name,
+    }
+    return re.sub(
+        r"\{schema\}|\{sop_text\}|\{category_name\}",
+        lambda match: values[match.group(0)],
+        template,
+    )
+
+
 def render_judge_prompt(rules: str, detections: list[Detection]) -> str:
     """Render ``judge.md`` with the Verdict schema, rules, and table."""
     template = _JUDGE_TEMPLATE.read_text(encoding="utf-8")
diff --git a/backend/app/prompts/sop_to_profile.md b/backend/app/prompts/sop_to_profile.md
new file mode 100644
index 0000000..9e95112
--- /dev/null
+++ b/backend/app/prompts/sop_to_profile.md
@@ -0,0 +1,16 @@
+You are a quality-engineering assistant. Turn the factory SOP paragraph below into a product inspection profile.
+
+Rules for the draft:
+- `id` must be the category name below, lowercased with spaces as underscores.
+- `name` must be the category name below verbatim.
+- `defect_prompts` lists the defect types the SOP names (short noun phrases for a segmenter, e.g. "scratch", "crack"). When the SOP names none, use ["defect"].
+- `rules` restates the SOP's pass/fail criteria as plain English, quoting its thresholds.
+- `mm_per_px` is null unless the SOP states a pixel-to-mm scale. `min_score` is 0.3. `reference_image` is null.
+
+Return only JSON matching this schema: {schema}
+
+CATEGORY:
+{category_name}
+
+SOP:
+{sop_text}
diff --git a/backend/app/synth/__init__.py b/backend/app/synth/__init__.py
new file mode 100644
index 0000000..010c6d9
--- /dev/null
+++ b/backend/app/synth/__init__.py
@@ -0,0 +1,3 @@
+"""Synthetic defect image generation (M5)."""
+
+from __future__ import annotations
diff --git a/backend/app/synth/generate.py b/backend/app/synth/generate.py
new file mode 100644
index 0000000..528d353
--- /dev/null
+++ b/backend/app/synth/generate.py
@@ -0,0 +1,181 @@
+"""Synthetic defect generation CLI (M5).
+
+``python -m app.synth.generate --profile bottle --defect scratch --n 10``
+
+Loads one good image (the profile's reference image, else the committed
+MVTec-layout fixture's good image), asks the image generator for ``n``
+defective variants, and writes image+mask pairs to
+``data/synth/{profile}/{defect}/``::
+
+    data/synth/{profile}/_reference.png        copy of the good image
+    data/synth/{profile}/{defect}/{i:03d}.png
+    data/synth/{profile}/{defect}/{i:03d}_mask.png
+
+Masks: generators exposing ``add_defect_with_mask`` (the fake) have
+their mask stored verbatim; anything else (the real Muse Image mapping,
+which returns no mask until inpainting support is confirmed) falls back
+to a grayscale image-diff threshold against the good image. An empty
+diff keeps the image, omits the mask, and logs the omission. The
+threshold used is logged per image.
+
+``--fake`` (the default) paints seeded shapes offline; ``--no-fake``
+calls the real Muse Image adapter and needs keys in ``.env``.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import sys
+from pathlib import Path
+
+import numpy as np
+from PIL import Image
+
+from app.adapters.fakes import FakeImageGenerator
+from app.adapters.muse_image import MuseImageGenerator
+from app.config import settings
+from app.schemas import ProductProfile
+
+APP_DIR = Path(__file__).resolve().parent.parent
+BACKEND_DIR = APP_DIR.parent
+PROFILES_DIR = BACKEND_DIR / "profiles"
+FIXTURE_GOOD = (
+    BACKEND_DIR / "tests" / "fixtures" / "mvtec" / "widget" / "train" / "good"
+)
+
+DIFF_THRESHOLD = 25.0
+
+
+def load_good_image(profile_id: str) -> tuple[Image.Image, ProductProfile]:
+    """Load the profile plus its good image (reference, else fixture)."""
+    profile_path = PROFILES_DIR / f"{profile_id}.json"
+    try:
+        profile = ProductProfile.model_validate(
+            json.loads(profile_path.read_text(encoding="utf-8"))
+        )
+    except OSError as exc:
+        raise ValueError(
+            f"unknown profile {profile_id!r}: no {profile_path} "
+            f"(available: {sorted(p.stem for p in PROFILES_DIR.glob('*.json'))})"
+        ) from exc
+    if profile.reference_image:
+        candidate = Path(profile.reference_image)
+        if not candidate.is_absolute():
+            candidate = BACKEND_DIR.parent / candidate
+        if candidate.is_file():
+            with Image.open(candidate) as raw:
+                return raw.convert("RGB").copy(), profile
+    fallbacks = sorted(FIXTURE_GOOD.glob("*.png"))
+    if not fallbacks:
+        raise ValueError(
+            f"profile {profile_id!r} sets no reference_image and the "
+            f"committed fixture under {FIXTURE_GOOD} is missing"
+        )
+    with Image.open(fallbacks[0]) as raw:
+        return raw.convert("RGB").copy(), profile
+
+
+def diff_mask(
+    good: Image.Image, defective: Image.Image, threshold: float = DIFF_THRESHOLD
+) -> np.ndarray:
+    """Boolean defect mask from the per-pixel max-channel abs diff."""
+    good_arr = np.asarray(good.convert("RGB")).astype(np.int16)
+    bad_arr = np.asarray(defective.convert("RGB").resize(good.size)).astype(np.int16)
+    return (np.abs(good_arr - bad_arr).max(axis=2) > threshold)
+
+
+def generate_pairs(
+    profile_id: str,
+    defect: str,
+    n: int,
+    *,
+    generator=None,
+    out_root: str | Path | None = None,
+    seed: int = 0,
+    threshold: float = DIFF_THRESHOLD,
+) -> list[tuple[Path, Path | None]]:
+    """Generate ``n`` image+mask pairs; return ``(image, mask|None)`` paths."""
+    if n < 1:
+        raise ValueError(f"--n must be >= 1, got {n}")
+    if generator is None:
+        generator = FakeImageGenerator()
+    good, _ = load_good_image(profile_id)
+    root = Path(out_root) if out_root is not None else Path(settings.data_dir) / "synth"
+    defect_dir = root / profile_id / defect
+    defect_dir.mkdir(parents=True, exist_ok=True)
+    reference_path = root / profile_id / "_reference.png"
+    if not reference_path.is_file():
+        good.save(reference_path)
+    pairs: list[tuple[Path, Path | None]] = []
+    for index in range(n):
+        item_seed = f"{seed}/{index}"
+        mask_path: Path | None = defect_dir / f"{index:03d}_mask.png"
+        image_path = defect_dir / f"{index:03d}.png"
+        if hasattr(generator, "add_defect_with_mask"):
+            image, mask_image = generator.add_defect_with_mask(
+                good, defect, seed=item_seed
+            )
+            mask_image.save(mask_path)
+            print(f"{image_path}: mask=exact")
+        else:
+            image = generator.add_defect(good, defect, None)
+            mask = diff_mask(good, image, threshold)
+            print(f"{image_path}: mask=diff(threshold={threshold})")
+            if not bool(mask.any()):
+                print(f"{image_path}: empty diff, omitting mask")
+                mask_path = None
+            else:
+                Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
+        image.save(image_path)
+        pairs.append((image_path, mask_path))
+    return pairs
+
+
+def main(argv: list[str] | None = None) -> int:
+    """CLI: ``python -m app.synth.generate --profile P --defect D --n K``."""
+    parser = argparse.ArgumentParser(description="Generate synthetic defects.")
+    parser.add_argument("--profile", required=True, help="Profile id in backend/profiles/")
+    parser.add_argument("--defect", required=True, help="Defect description")
+    parser.add_argument("--n", type=int, required=True, help="Pair count")
+    parser.add_argument(
+        "--fake",
+        action=argparse.BooleanOptionalAction,
+        default=True,
+        help="Seeded offline shapes (default) vs the real Muse Image adapter.",
+    )
+    parser.add_argument("--seed", type=int, default=0)
+    parser.add_argument(
+        "--synth-dir", default=str(Path(settings.data_dir) / "synth")
+    )
+    args = parser.parse_args(argv)
+    try:
+        generator = FakeImageGenerator() if args.fake else MuseImageGenerator()
+        if not args.fake:
+            from app.adapters.base import require_configured
+
+            require_configured(
+                model_id=settings.image_model_id,
+                model_field="IMAGE_MODEL_ID",
+                adapter="Image",
+            )
+        pairs = generate_pairs(
+            args.profile,
+            args.defect,
+            args.n,
+            generator=generator,
+            out_root=args.synth_dir,
+            seed=args.seed,
+        )
+    except ValueError as exc:
+        print(f"error: {exc}", file=sys.stderr)
+        return 2
+    except Exception as exc:  # noqa: BLE001 - CLI reports, never tracebacks
+        print(f"error: {exc}", file=sys.stderr)
+        return 2
+    print(f"wrote {len(pairs)} pairs to {args.synth_dir}/{args.profile}/{args.defect}/")
+    return 0
+
+
+if __name__ == "__main__":
+    raise SystemExit(main())
diff --git a/backend/tests/test_adapters.py b/backend/tests/test_adapters.py
index cd5f7dd..b61a223 100644
--- a/backend/tests/test_adapters.py
+++ b/backend/tests/test_adapters.py
@@ -177,9 +177,14 @@ def test_sam_empty_model_id_alone_raises_without_http(
     assert no_http == []
 
 
-def test_sop_to_profile_is_m5_stub() -> None:
-    with pytest.raises(NotImplementedError):
+def test_sop_not_configured_raises_without_http(
+    empty_settings: None, no_http: list
+) -> None:
+    # M5 implements the former NotImplementedError stub: unconfigured
+    # now means AdapterNotConfiguredError before any HTTP, like judge.
+    with pytest.raises(AdapterNotConfiguredError):
         MuseSparkJudge().sop_to_profile("Some SOP text.", "bottle")
+    assert no_http == []
 
 
 class _StubResponse:
diff --git a/backend/tests/test_sop.py b/backend/tests/test_sop.py
new file mode 100644
index 0000000..266a566
--- /dev/null
+++ b/backend/tests/test_sop.py
@@ -0,0 +1,188 @@
+"""SOP import tests (M5): unsaved drafts, the 422 path, retry behavior.
+
+Run: cd backend && .venv/bin/python -m pytest -q
+"""
+
+import httpx
+import pytest
+from fastapi.testclient import TestClient
+from PIL import Image
+
+import app.main as main_module
+from app.adapters.base import AdapterNotConfiguredError
+from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge
+from app.config import settings
+from app.main import app
+from app.schemas import ProductProfile
+
+client = TestClient(app)
+
+IMAGE_W, IMAGE_H = 40, 30
+SOP = (
+    "Bottle inspection: FAIL a bottle with any scratch longer than 5mm "
+    "or any contamination stain; PASS otherwise."
+)
+CATEGORY = "bottle"
+
+DRAFT = {
+    "id": "bottle",
+    "name": "bottle",
+    "defect_prompts": ["scratch", "contamination stain"],
+    "rules": SOP,
+    "mm_per_px": None,
+    "min_score": 0.3,
+    "reference_image": None,
+}
+
+
+@pytest.fixture
+def image() -> Image.Image:
+    return Image.new("RGB", (IMAGE_W, IMAGE_H), color=(120, 120, 120))
+
+
+@pytest.fixture
+def configured(monkeypatch: pytest.MonkeyPatch):
+    monkeypatch.setattr(settings, "meta_api_key", "test-key")
+    monkeypatch.setattr(settings, "meta_api_base_url", "https://meta.test")
+    monkeypatch.setattr(settings, "judge_model_id", "judge-test-id")
+    yield
+
+
+@pytest.fixture
+def empty_settings(monkeypatch: pytest.MonkeyPatch):
+    for field in ("meta_api_key", "meta_api_base_url", "judge_model_id"):
+        monkeypatch.setattr(settings, field, "")
+    yield
+
+
+@pytest.fixture
+def no_http(monkeypatch: pytest.MonkeyPatch) -> list:
+    calls: list = []
+
+    def _forbidden(*args, **kwargs):
+        calls.append((args, kwargs))
+        raise AssertionError("HTTP must not be called")
+
+    monkeypatch.setattr(httpx, "post", _forbidden)
+    return calls
+
+
+class StubSopJudge:
+    """Fixed draft so the endpoint test never touches the network."""
+
+    def __init__(self, draft: dict | None = None) -> None:
+        self._draft = draft if draft is not None else DRAFT
+        self.calls = 0
+
+    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
+        self.calls += 1
+        return ProductProfile.model_validate(self._draft)
+
+
+class AlwaysInvalidJudge:
+    """Every attempt fails validation: the endpoint must answer 422."""
+
+    def __init__(self) -> None:
+        self.calls = 0
+
+    def sop_to_profile(self, sop_text: str, category_name: str):
+        self.calls += 1
+        raise JudgeValidationError("sop_to_profile output failed validation twice")
+
+
+def _use_stub(stub, monkeypatch: pytest.MonkeyPatch):
+    monkeypatch.setattr(main_module, "_get_sop_judge", lambda: stub)
+
+
+def test_from_sop_returns_valid_draft_and_saves_nothing(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    stub = StubSopJudge()
+    _use_stub(stub, monkeypatch)
+    resp = client.post(
+        "/api/profiles/from-sop", json={"sop_text": SOP, "category_name": CATEGORY}
+    )
+    assert resp.status_code == 200
+    profile = ProductProfile.model_validate(resp.json())
+    assert profile.id == "bottle"
+    assert profile.defect_prompts == ["scratch", "contamination stain"]
+    assert stub.calls == 1
+
+
+def test_from_sop_saves_nothing_to_profiles_dir(monkeypatch: pytest.MonkeyPatch) -> None:
+    from pathlib import Path
+
+    profiles_dir = Path("profiles")
+    if profiles_dir.is_dir():
+        before = {p.name for p in profiles_dir.iterdir()}
+    else:
+        before = set()
+    _use_stub(StubSopJudge(), monkeypatch)
+    resp = client.post(
+        "/api/profiles/from-sop", json={"sop_text": SOP, "category_name": CATEGORY}
+    )
+    assert resp.status_code == 200
+    if profiles_dir.is_dir():
+        assert {p.name for p in profiles_dir.iterdir()} == before
+
+
+def test_from_sop_garbage_twice_gives_422(monkeypatch: pytest.MonkeyPatch) -> None:
+    stub = AlwaysInvalidJudge()
+    _use_stub(stub, monkeypatch)
+    resp = client.post(
+        "/api/profiles/from-sop",
+        json={"sop_text": "!!! not a spec !!!", "category_name": "bottle"},
+    )
+    assert resp.status_code == 422
+    assert stub.calls == 1
+
+
+def test_from_sop_rejects_empty_body() -> None:
+    resp = client.post(
+        "/api/profiles/from-sop", json={"sop_text": "", "category_name": ""}
+    )
+    assert resp.status_code == 422
+
+
+def test_sop_retry_once_then_succeeds(
+    configured, no_http, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    calls: list[str] = []
+    valid = dict(DRAFT)
+
+    def _scripted(self, prompt: str):
+        calls.append(prompt)
+        if len(calls) == 1:
+            return {"id": 42}  # fails ProductProfile validation
+        return valid
+
+    monkeypatch.setattr(MuseSparkJudge, "_sop_via_meta_api", _scripted)
+    profile = MuseSparkJudge().sop_to_profile(SOP, CATEGORY)
+    assert profile.id == "bottle"
+    assert len(calls) == 2
+    assert "failed validation" in calls[1]
+    assert no_http == []
+
+
+def test_sop_double_failure_raises_judge_error(
+    configured, no_http, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    calls: list[str] = []
+
+    def _always_invalid(self, prompt: str):
+        calls.append(prompt)
+        return {"id": 42}
+
+    monkeypatch.setattr(MuseSparkJudge, "_sop_via_meta_api", _always_invalid)
+    with pytest.raises(JudgeValidationError):
+        MuseSparkJudge().sop_to_profile("!!! not a spec !!!", CATEGORY)
+    assert len(calls) == 2
+    assert no_http == []
+
+
+def test_sop_unconfigured_adapter_errors_without_network(
+    empty_settings, no_http
+) -> None:
+    with pytest.raises(AdapterNotConfiguredError):
+        MuseSparkJudge().sop_to_profile(SOP, CATEGORY)
+    assert no_http == []
diff --git a/backend/tests/test_synth.py b/backend/tests/test_synth.py
new file mode 100644
index 0000000..b0300da
--- /dev/null
+++ b/backend/tests/test_synth.py
@@ -0,0 +1,116 @@
+"""Synth generator tests (M5): determinism, verbatim masks, diff fallback.
+
+Run: cd backend && .venv/bin/python -m pytest -q
+"""
+
+from pathlib import Path
+
+import numpy as np
+from PIL import Image
+
+from app.adapters.fakes import FakeImageGenerator
+from app.synth.generate import diff_mask, generate_pairs
+
+
+def _written_bytes(pairs: list[tuple[Path, Path | None]]) -> list[tuple[bytes, bytes | None]]:
+    return [
+        (
+            image_path.read_bytes(),
+            mask_path.read_bytes() if mask_path is not None else None,
+        )
+        for image_path, mask_path in pairs
+    ]
+
+
+def test_fake_generate_is_deterministic(tmp_path: Path) -> None:
+    first = generate_pairs(
+        "bottle", "scratch", 3, generator=FakeImageGenerator(), out_root=tmp_path
+    )
+    assert len(first) == 3
+    for image_path, mask_path in first:
+        assert image_path.is_file()
+        assert mask_path is not None and mask_path.is_file()
+    before = _written_bytes(first)
+    second = generate_pairs(
+        "bottle", "scratch", 3, generator=FakeImageGenerator(), out_root=tmp_path
+    )
+    assert _written_bytes(second) == before
+
+
+def test_layout_paths_exact(tmp_path: Path) -> None:
+    pairs = generate_pairs(
+        "bottle", "scratch", 2, generator=FakeImageGenerator(), out_root=tmp_path
+    )
+    assert [str(image_path.relative_to(tmp_path)) for image_path, _ in pairs] == [
+        "bottle/scratch/000.png",
+        "bottle/scratch/001.png",
+    ]
+    assert [str(mask_path.relative_to(tmp_path)) for _, mask_path in pairs] == [
+        "bottle/scratch/000_mask.png",
+        "bottle/scratch/001_mask.png",
+    ]
+    assert (tmp_path / "bottle" / "_reference.png").is_file()
+
+
+def test_returned_masks_used_verbatim(tmp_path: Path) -> None:
+    generator = FakeImageGenerator()
+    pairs = generate_pairs(
+        "bottle", "scratch", 2, generator=generator, out_root=tmp_path
+    )
+    for image_path, mask_path in pairs:
+        assert mask_path is not None
+        stored = np.asarray(Image.open(mask_path).convert("L"))
+        assert stored.size > 0 and (stored > 128).any()
+
+
+def test_missing_mask_triggers_diff_fallback(tmp_path: Path, capsys) -> None:
+    class PaintOnly:
+        """add_defect without add_defect_with_mask: forces the diff path."""
+
+        def add_defect(self, good_image, defect_description, mask):
+            painted = good_image.convert("RGB").copy()
+            pixels = painted.load()
+            for y in range(6, 14):
+                for x in range(6, 14):
+                    pixels[x, y] = (255, 0, 0)
+            return painted
+
+    pairs = generate_pairs(
+        "bottle", "scratch", 1, generator=PaintOnly(), out_root=tmp_path
+    )
+    _, mask_path = pairs[0]
+    assert mask_path is not None and mask_path.is_file()
+    stored = np.asarray(Image.open(mask_path).convert("L"))
+    assert (stored > 128).any()
+    out = capsys.readouterr().out
+    assert "mask=diff(threshold=" in out
+
+
+def test_empty_diff_keeps_image_omits_mask_and_logs(tmp_path: Path, capsys) -> None:
+    class Identity:
+        def add_defect(self, good_image, defect_description, mask):
+            return good_image.convert("RGB").copy()
+
+    pairs = generate_pairs(
+        "bottle", "scratch", 1, generator=Identity(), out_root=tmp_path
+    )
+    image_path, mask_path = pairs[0]
+    assert image_path.is_file()
+    assert mask_path is None
+    assert list(tmp_path.rglob("*_mask.png")) == []
+    out = capsys.readouterr().out
+    assert "empty diff, omitting mask" in out
+
+
+def test_diff_mask_finds_painted_shapes() -> None:
+    good = Image.new("RGB", (48, 48), (128, 128, 128))
+    bad = good.copy()
+    bad_pixels = bad.load()
+    for y in range(10, 20):
+        for x in range(10, 20):
+            bad_pixels[x, y] = (255, 0, 0)
+    mask = diff_mask(good, bad)
+    expected = np.zeros((48, 48), bool)
+    expected[10:20, 10:20] = True
+    assert (mask == expected).all()
+    assert not bool(diff_mask(good, good.copy()).any())
diff --git a/docs/EVAL_NOTES.md b/docs/EVAL_NOTES.md
index bbc5f2b..4c75a4b 100644
--- a/docs/EVAL_NOTES.md
+++ b/docs/EVAL_NOTES.md
@@ -53,6 +53,24 @@ Per category: 2 train-good, 10 test-good, 20 test `scratch` defects
   A layout mismatch surfaces as the guidance error; fix the loader
   when real data lands.
 
+## Synthetic images (M5, `data/synth/`)
+
+`python -m app.synth.generate --profile bottle --defect scratch --n 10`
+writes `data/synth/{profile}/_reference.png` plus
+`data/synth/{profile}/{defect}/{i:03d}.png` and `{i:03d}_mask.png`
+pairs (gitignored, never commit). `--fake` (the default) paints seeded
+shapes offline with exact masks; `--no-fake` calls the real Muse Image
+adapter. Generators without exact masks fall back to a grayscale
+image-diff threshold (logged per image); an empty diff keeps the image
+and omits the mask.
+
+`python -m app.eval.run --data synth` reads that layout through the
+same sampler, metrics, and ablations (`--mode`, `--adapter`,
+`--seed` unchanged; `--synth-dir` selects the root). Every synth item
+is defective, so expect recall near 1.0 and precision set by the
+false-positive rate — AUROC is uninformative single-class (0.5 by
+construction) and IoU measures mask overlap against the stored masks.
+
 ## Manual rerun (real MVTec — human steps)
 
 1. Download MVTec AD (CC BY-NC-SA 4.0, non-commercial) into `data/`
```
