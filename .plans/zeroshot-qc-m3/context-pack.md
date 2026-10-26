# Context pack

BASE: main
CHANGED: 9 files, +737/-40

## What this change does

Wires the M3 judge into inspection: `run_inspection` optionally renders the overlay, judges detections against effective rules via the HANDOFF §7 prompt, and forces FAIL in code per the consistency rule. CLI gains `--rules`/`--reference` plus verdict printing; `FakeJudge` gets a deterministic strict/lenient scripted mode.

## Files

- `backend/app/prompts/judge.md` — new; HANDOFF §7 prompt verbatim with `{schema}`, `{rules}`, `{detections_table}` slots
- `backend/app/prompts/__init__.py` — new; `render_judge_prompt` (`:40`), `build_detections_table` (`:23`); plain `.replace` so schema braces can't break rendering
- `backend/app/adapters/muse_spark.py` — `MuseSparkJudge.judge` (`:32`) renders prompt, validates `Verdict`, retries once with error appended, raises `JudgeValidationError` (`:25`); Meta mapping stays isolated in `_judge_via_meta_api` (`:69`), now returns raw `object`
- `backend/app/pipeline/inspect.py` — `run_inspection` (`:117`) gains `judge`/`rules`/`reference` params and returns `(detections, verdict)` when judged; `enforce_consistency` (`:101`) forces FAIL in code; `_load_reference_image` (`:92`)
- `backend/app/pipeline/wiring.py` — new `build_judge` (`:31`); `"fake-judge"` cache id lives here (supporting change, see plan Divergence notes)
- `backend/app/adapters/fakes.py` — `FakeJudge.judge` (`:69`) scripted: rules containing `lenient` pass all, else fail first candidate
- `cli.py` — `--rules`/`--reference` flags, `_print_verdict_block`, catches `JudgeValidationError`/`ValueError` → exit 1; `--no-judge` path unchanged
- `backend/scripts/smoke.py` — also catches `JudgeValidationError` for a clean real-mode `error:` line (supporting change)
- `backend/tests/test_judge.py` — new, 437 lines; diff NOT inlined below (see Test entry points for the case list)

## API contracts

- `Judge.judge(image, overlay, reference|None, detections, profile) -> Verdict` declared in `backend/app/adapters/base.py:42`
- `Verdict` shape (`verdict`, `confidence`, `rulings`, `missed_defects`, `summary`) declared in `backend/app/schemas.py:43`; `DefectRuling` at `backend/app/schemas.py:36`
- Judge cache key covers image+overlay+reference+detections+full profile JSON+model id, `backend/app/pipeline/cache.py:72` — any rules edit is a miss
- Meta API request/response shape is still placeholder behind `TODO(meta-docs)`, `backend/app/adapters/muse_spark.py:69`; payload gained a `"prompt"` field
- CLI output contract: `verdict: <PASS|FAIL> confidence=<0.00>` + `ruling <id>:` lines + `missed:` lines + `summary:` line, `cli.py:44`

## Test entry points

- `backend/tests/test_judge.py` — `cd backend && .venv/bin/python -m pytest -q` (project venv only). Cases: strict-fails-first (`:112`), lenient-passes (`:126`), pipeline flip without profile mutation (`:138`), empty-detections pass (`:152`), retry-then-valid (`:197`), double-malformed raises (`:218`), violation+PASS→FAIL (`:239`), missed+PASS→FAIL (`:259`), real-defect-without-rule keeps PASS (`:270`), pipeline forcing (`:288`), ref present/absent (`:315`), profile ref from disk (`:333`), override wins (`:344`), missing ref raises (`:358`), cache hit/miss on rules (`:386`), prompt slots (`:407`), table empty/mm-dash (`:420`)
- `backend/tests/test_inspect.py` — guards the unchanged `--no-judge` path; same pytest command
- `cd backend && .venv/bin/python scripts/smoke.py --fake` — keeps count/verdict line shape

## Acceptance criteria

1. `python cli.py inspect <image> --profile bottle` prints a valid `Verdict` (verdict, confidence, per-detection rulings, summary). Check: CLI run in Verification.
2. A `--rules` edit flips the verdict on a borderline image with no other change. Check: `test_judge.py` flip case plus CLI run.
3. `pytest` is green and `scripts/smoke.py --fake` keeps its count/verdict line shape. Check: full suite plus smoke run.
4. No model ID, endpoint, or key in new source; prompt file carries no secrets. Check: grep guard in Verification.
5. manual: the same flip against the real Muse Spark model with keys plus official docs. Human steps: paste docs, set `.env`, download MVTec, run the CLI twice with strict then lenient rules.

## Do not re-derive

- Consistency rule is enforced in CODE (`enforce_consistency`, `inspect.py:101`), never trusted from the model: `is_real_defect AND rule_violated` on any ruling, or non-empty `missed_defects`, forces FAIL. Real-defect-without-cited-rule does NOT force FAIL (`test_judge.py:270`).
- `rules` override is call-only: `run_inspection` uses `profile.model_copy`, never mutates (`inspect.py:182`); `reference` param wins, else `profile.reference_image` loads from disk, else None.
- Fake flip signal is the literal substring `lenient` (case-insensitive) in rules text (`fakes.py:77`); everything else fails the first candidate. Empty detections always PASS.
- Retry resends the FULL prompt plus the validation error appended, exactly once (`muse_spark.py:49`); second failure raises `JudgeValidationError(ValueError)`, which CLI and smoke catch for exit-1 `error:` lines.
- Known-broken/out-of-scope, not this change: real-model prompt behavior unproven (manual criterion); `_judge_via_meta_api` mapping is placeholder until official docs; M6 router mapping to HTTP 422 is future work; `sop_to_profile` is an M5 stub.
- Previous behavior: `cli.py inspect` without `--no-judge` printed a "judging arrives in M3" note and stopped after segmentation; `run_inspection` returned only `list[Detection]`.

## Diff (source only; `backend/tests/test_judge.py` is new — read the file, cases listed above)

```diff
diff --git a/backend/app/adapters/fakes.py b/backend/app/adapters/fakes.py
index ff17c31..aeafe8a 100644
--- a/backend/app/adapters/fakes.py
+++ b/backend/app/adapters/fakes.py
@@ -57,7 +57,14 @@ class FakeSegmenter:
 
 
 class FakeJudge:
-    """Verdict that validates first-try: one ruling per input detection."""
+    """Scripted verdict keyed off the rules text (M3).
+
+    Rules containing ``lenient`` (case-insensitive) pass every
+    candidate; any other rules fail the first candidate and pass the
+    rest. Deterministic, no network — proves the pipeline reacts to
+    rule edits, not the model's judgment. No detections always
+    passes.
+    """
 
     def judge(
         self,
@@ -67,21 +74,47 @@ class FakeJudge:
         detections: list[Detection],
         profile: ProductProfile,
     ) -> Verdict:
+        if "lenient" in profile.rules.lower() or not detections:
+            rulings = [
+                DefectRuling(
+                    detection_id=detection.id,
+                    is_real_defect=False,
+                    rule_violated=None,
+                    reason="Fake judge: no rule violation found for this candidate.",
+                )
+                for detection in detections
+            ]
+            return Verdict(
+                verdict="PASS",
+                confidence=0.9,
+                rulings=rulings,
+                missed_defects=[],
+                summary="Fake judge: all candidates dismissed, part passes.",
+            )
+        first, rest = detections[0], detections[1:]
         rulings = [
+            DefectRuling(
+                detection_id=first.id,
+                is_real_defect=True,
+                rule_violated=profile.rules,
+                reason="Fake judge: scripted strict-mode failure of the first candidate.",
+            )
+        ]
+        rulings.extend(
             DefectRuling(
                 detection_id=detection.id,
                 is_real_defect=False,
                 rule_violated=None,
                 reason="Fake judge: no rule violation found for this candidate.",
             )
-            for detection in detections
-        ]
+            for detection in rest
+        )
         return Verdict(
-            verdict="PASS",
+            verdict="FAIL",
             confidence=0.9,
             rulings=rulings,
             missed_defects=[],
-            summary="Fake judge: all candidates dismissed, part passes.",
+            summary="Fake judge: first candidate violates the rules, part fails.",
         )
 
     def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
diff --git a/backend/app/adapters/muse_spark.py b/backend/app/adapters/muse_spark.py
index 27f7b7d..e3b9e7c 100644
--- a/backend/app/adapters/muse_spark.py
+++ b/backend/app/adapters/muse_spark.py
@@ -6,16 +6,26 @@ can be corrected in one place when the official Meta Model API docs
 arrive (HANDOFF §2); every uncertain detail there is marked
 TODO(meta-docs) and built only from the shared settings values.
 ``sop_to_profile`` is an explicit M5 stub (plan: SOP parsing lands M5).
+
+M3: ``judge`` renders the HANDOFF §7 prompt, validates the response
+against ``Verdict``, retries once with the validation error appended,
+and raises ``JudgeValidationError`` on the second failure.
 """
 
 import httpx
 from PIL import Image
+from pydantic import ValidationError
 
 from app.adapters.base import encode_image_b64, require_configured
 from app.config import settings
+from app.prompts import render_judge_prompt
 from app.schemas import Detection, ProductProfile, Verdict
 
 
+class JudgeValidationError(ValueError):
+    """Both judge attempts returned output that failed Verdict validation."""
+
+
 class MuseSparkJudge:
     """Judge backed by Muse Spark over the Meta Model API."""
 
@@ -30,7 +40,27 @@ class MuseSparkJudge:
         require_configured(
             model_id=settings.judge_model_id, model_field="JUDGE_MODEL_ID", adapter="Judge"
         )
-        return self._judge_via_meta_api(image, overlay, reference, detections, profile)
+        prompt = render_judge_prompt(profile.rules, detections)
+        try:
+            data = self._judge_via_meta_api(
+                image, overlay, reference, detections, profile, prompt
+            )
+            return Verdict.model_validate(data)
+        except ValidationError as first_error:
+            retry_prompt = (
+                f"{prompt}\n\nYour previous response failed validation:\n"
+                f"{first_error}\nReturn only JSON matching the schema."
+            )
+            try:
+                data = self._judge_via_meta_api(
+                    image, overlay, reference, detections, profile, retry_prompt
+                )
+                return Verdict.model_validate(data)
+            except ValidationError as second_error:
+                raise JudgeValidationError(
+                    "judge output failed Verdict validation twice: "
+                    f"{second_error}"
+                ) from second_error
 
     def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
         # M5: SOP-to-profile parsing lands in M5; no behaviour in M1.
@@ -43,7 +73,8 @@ class MuseSparkJudge:
         reference: Image.Image | None,
         detections: list[Detection],
         profile: ProductProfile,
-    ) -> Verdict:
+        prompt: str,
+    ) -> object:
         # TODO(meta-docs): everything in this function is a placeholder
         # mapping to be corrected against the official Meta Model API
         # docs. Do not treat the endpoint, payload shape, auth scheme,
@@ -54,10 +85,11 @@ class MuseSparkJudge:
         url = settings.meta_api_base_url
 
         # TODO(meta-docs): request payload shape and field names,
-        # including how images, detections, and rules are passed and
-        # whether a structured-output / JSON mode exists.
+        # including how images, prompt, detections, and rules are
+        # passed and whether a structured-output / JSON mode exists.
         payload = {
             "model": settings.judge_model_id,
+            "prompt": prompt,
             "image": encode_image_b64(image),
             "overlay": encode_image_b64(overlay),
             "reference": encode_image_b64(reference) if reference is not None else None,
@@ -73,4 +105,4 @@ class MuseSparkJudge:
         data = response.json()
         if isinstance(data, dict) and isinstance(data.get("verdict"), dict):
             data = data["verdict"]
-        return Verdict.model_validate(data)
+        return data
diff --git a/backend/app/pipeline/inspect.py b/backend/app/pipeline/inspect.py
index 9df4027..8e388ff 100644
--- a/backend/app/pipeline/inspect.py
+++ b/backend/app/pipeline/inspect.py
@@ -1,9 +1,11 @@
-"""Segmentation orchestrator (M2 Inspect phase).
+"""Segmentation orchestrator (M2 Inspect phase) plus the M3 judge step.
 
 Single flow: load image (RGB) + named profile, segment, drop masks
 below ``profile.min_score``, greedily merge duplicates with IoU above
 0.5, assign stable ``d1, d2, ...`` ids in score order, measure each.
-No judge call in M2.
+With a judge supplied, render the overlay and judge the detections
+against the effective rules, then force FAIL in code per the
+consistency rule (HANDOFF §7 step 8).
 """
 
 import json
@@ -15,9 +17,10 @@ import numpy as np
 from PIL import Image
 from pycocotools import mask as mask_api
 
-from app.adapters.base import Segmenter
+from app.adapters.base import Judge, Segmenter
 from app.pipeline.measure import decode_rle_for_image, measure_mask
-from app.schemas import Detection, ProductProfile, RawMask
+from app.pipeline.overlay import make_overlay
+from app.schemas import Detection, ProductProfile, RawMask, Verdict
 
 MERGE_IOU_THRESHOLD = 0.5
 
@@ -86,10 +89,51 @@ def _decode_valid_masks(
     return valid
 
 
+def _load_reference_image(path: str) -> Image.Image:
+    """Load a known-good reference image; missing files are a caller error."""
+    try:
+        with Image.open(path) as raw:
+            return raw.convert("RGB").copy()
+    except Exception as exc:
+        raise ValueError(f"could not open reference image {path}: {exc}") from exc
+
+
+def enforce_consistency(verdict: Verdict) -> Verdict:
+    """Force FAIL in code when the rulings demand it (HANDOFF §7 step 8).
+
+    The model's own verdict word is not trusted: any ruling with
+    ``is_real_defect`` and a cited rule, or any missed defect, means
+    FAIL. Returns the input unchanged when it already agrees.
+    """
+    must_fail = any(
+        ruling.is_real_defect and ruling.rule_violated
+        for ruling in verdict.rulings
+    ) or bool(verdict.missed_defects)
+    if must_fail and verdict.verdict != "FAIL":
+        return verdict.model_copy(update={"verdict": "FAIL"})
+    return verdict
+
+
 def run_inspection(
-    image: Image.Image, profile: ProductProfile, segmenter: Segmenter
-) -> list[Detection]:
-    """Segment, filter, merge, and measure. Returns score-ordered detections."""
+    image: Image.Image,
+    profile: ProductProfile,
+    segmenter: Segmenter,
+    judge: Judge | None = None,
+    rules: str | None = None,
+    reference: Image.Image | None = None,
+) -> list[Detection] | tuple[list[Detection], Verdict]:
+    """Segment, filter, merge, measure, and optionally judge.
+
+    Without a judge this is the M2 path and returns score-ordered
+    detections. With a judge it also renders the overlay, judges the
+    detections, enforces the consistency rule, and returns
+    ``(detections, verdict)``.
+
+    ``rules`` replaces ``profile.rules`` for this call only (the
+    profile object is never mutated); ``reference`` overrides
+    ``profile.reference_image`` for this call, which is otherwise
+    loaded from disk when set.
+    """
     if image.mode != "RGB":
         image = image.convert("RGB")
     width, height = image.size
@@ -131,7 +175,19 @@ def run_inspection(
                 length_mm=sizes["length_mm"],
             )
         )
-    return detections
+    if judge is None:
+        return detections
+    effective_profile = profile
+    if rules is not None:
+        effective_profile = profile.model_copy(update={"rules": rules})
+    effective_reference = reference
+    if effective_reference is None and profile.reference_image:
+        effective_reference = _load_reference_image(profile.reference_image)
+    overlay = make_overlay(image, detections)
+    verdict = judge.judge(
+        image, overlay, effective_reference, detections, effective_profile
+    )
+    return detections, enforce_consistency(verdict)
 
 
 def inspect_image(
diff --git a/backend/app/pipeline/wiring.py b/backend/app/pipeline/wiring.py
index 091c3e7..8197f3c 100644
--- a/backend/app/pipeline/wiring.py
+++ b/backend/app/pipeline/wiring.py
@@ -1,27 +1,41 @@
-"""Shared adapter wiring: one segmenter builder for every entry point.
+"""Shared adapter wiring: one segmenter and one judge builder per entry point.
 
-Both entry points (repo-root ``cli.py`` and ``scripts/smoke.py``) build
-their segmenter here so the cache root, the fake/real selection, and
-the ``"fake-sam"`` cache id cannot drift apart and split or poison the
-disk cache.
+Every entry point (repo-root ``cli.py``, ``scripts/smoke.py``) builds
+its adapters here so the cache root, the fake/real selection, and the
+``"fake-sam"`` / ``"fake-judge"`` cache ids cannot drift apart and
+split or poison the disk cache.
 """
 
 from pathlib import Path
 
-from app.adapters.fakes import FakeSegmenter
+from app.adapters.fakes import FakeJudge, FakeSegmenter
+from app.adapters.muse_spark import MuseSparkJudge
 from app.adapters.sam import SamSegmenter
 from app.config import settings
-from app.pipeline.cache import CachedSegmenter, DiskCache
+from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache
 
 
 def build_segmenter(fake: bool, cache: DiskCache | None = None) -> CachedSegmenter:
     """Cached segmenter: deterministic fake (``"fake-sam"`` id) or real SAM.
 
     A caller-owned ``DiskCache`` may be passed in so sibling adapters
-    (e.g. smoke's judge) share one store instance.
+    (e.g. the judge) share one store instance.
     """
     if cache is None:
         cache = DiskCache(Path(settings.data_dir) / "cache")
     if fake:
         return CachedSegmenter(FakeSegmenter(), "fake-sam", cache)
     return CachedSegmenter(SamSegmenter(), settings.sam_model_id, cache)
+
+
+def build_judge(fake: bool, cache: DiskCache | None = None) -> CachedJudge:
+    """Cached judge: deterministic fake (``"fake-judge"`` id) or Muse Spark.
+
+    Shares the caller's ``DiskCache`` when given so one inspection
+    reuses a single store for both segment and judge entries.
+    """
+    if cache is None:
+        cache = DiskCache(Path(settings.data_dir) / "cache")
+    if fake:
+        return CachedJudge(FakeJudge(), "fake-judge", cache)
+    return CachedJudge(MuseSparkJudge(), settings.judge_model_id, cache)
diff --git a/backend/app/prompts/__init__.py b/backend/app/prompts/__init__.py
new file mode 100644
index 0000000..9d7348f
--- /dev/null
+++ b/backend/app/prompts/__init__.py
@@ -0,0 +1,49 @@
+"""Judge prompt rendering (M3).
+
+``judge.md`` is the HANDOFF §7 prompt verbatim with ``{schema}``,
+``{rules}``, and ``{detections_table}`` slots. ``render_judge_prompt``
+fills them; ``build_detections_table`` formats the candidates the
+judge sees (same ids as the overlay labels). Slots are replaced with
+plain string substitution so JSON braces in the schema value can
+never disturb rendering.
+"""
+
+import json
+from pathlib import Path
+
+from app.schemas import Detection, Verdict
+
+_JUDGE_TEMPLATE = Path(__file__).resolve().parent / "judge.md"
+
+
+def _format_mm(value: float | None) -> str:
+    return f"{value:.2f}" if value is not None else "-"
+
+
+def build_detections_table(detections: list[Detection]) -> str:
+    """One line per candidate: id, label, score, size in px and mm."""
+    if not detections:
+        return "(no candidates)"
+    lines = [
+        "id | label | score | area_px | length_px | area_mm2 | length_mm"
+    ]
+    for detection in detections:
+        lines.append(
+            f"{detection.id} | {detection.label} | {detection.score:.2f} | "
+            f"{detection.area_px} | {detection.length_px:.1f} | "
+            f"{_format_mm(detection.area_mm2)} | "
+            f"{_format_mm(detection.length_mm)}"
+        )
+    return "\n".join(lines)
+
+
+def render_judge_prompt(rules: str, detections: list[Detection]) -> str:
+    """Render ``judge.md`` with the Verdict schema, rules, and table."""
+    template = _JUDGE_TEMPLATE.read_text(encoding="utf-8")
+    schema = json.dumps(Verdict.model_json_schema(), sort_keys=True)
+    rendered = template.replace("{schema}", schema)
+    rendered = rendered.replace("{rules}", rules)
+    rendered = rendered.replace(
+        "{detections_table}", build_detections_table(detections)
+    )
+    return rendered
diff --git a/backend/app/prompts/judge.md b/backend/app/prompts/judge.md
new file mode 100644
index 0000000..97aa6f4
--- /dev/null
+++ b/backend/app/prompts/judge.md
@@ -0,0 +1,26 @@
+You are a quality inspector on a factory line. Decide whether this part passes inspection.
+
+You receive:
+1. The part image.
+2. The same image with candidate defects outlined and labeled d1, d2, ...
+3. A known-good reference image of the same product (may be absent).
+4. A table of candidates: id, label, score, size in px and mm.
+5. The quality rules, written by the factory.
+
+For each candidate:
+- Decide if it is a real defect or a false alarm (glare, shadow, normal texture,
+  normal variation also visible in the reference image).
+- If real, quote the exact rule it violates, or null if no rule covers it.
+
+Then list any clear defects you see that have no candidate outline.
+
+Verdict is FAIL if any real defect violates a rule or any missed defect exists.
+Otherwise PASS. Apply the rules exactly as written; do not invent stricter rules.
+
+Return only JSON matching this schema: {schema}
+
+QUALITY RULES:
+{rules}
+
+CANDIDATES:
+{detections_table}
diff --git a/backend/scripts/smoke.py b/backend/scripts/smoke.py
index 6cadc7b..e0c74a3 100644
--- a/backend/scripts/smoke.py
+++ b/backend/scripts/smoke.py
@@ -25,7 +25,7 @@ from pydantic import ValidationError  # noqa: E402
 
 from app.adapters.base import AdapterNotConfiguredError  # noqa: E402
 from app.adapters.fakes import FakeJudge  # noqa: E402
-from app.adapters.muse_spark import MuseSparkJudge  # noqa: E402
+from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge  # noqa: E402
 from app.config import settings  # noqa: E402
 from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache  # noqa: E402
 from app.pipeline.measure import measure_mask  # noqa: E402
@@ -223,7 +223,7 @@ def main(argv: list[str] | None = None) -> int:
     except AdapterNotConfiguredError as exc:
         print(f"error: {exc}", file=sys.stderr)
         return 1
-    except ValidationError as exc:
+    except (ValidationError, JudgeValidationError) as exc:
         print(f"error: judge verdict failed validation: {exc}", file=sys.stderr)
         return 1
 
diff --git a/cli.py b/cli.py
index bc95df9..d7bd30b 100644
--- a/cli.py
+++ b/cli.py
@@ -1,8 +1,9 @@
-"""ZeroShot QC command line (M2: segmentation only, judging arrives in M3).
+"""ZeroShot QC command line (M3: segment plus judge).
 
-Canonical run: python cli.py inspect <image> --profile NAME [--no-judge] [--fake]
-Fake mode uses the deterministic fake segmenter (cache id "fake-sam",
-same as smoke); real mode is the default.
+Canonical run: python cli.py inspect <image> --profile NAME [--fake]
+Fake mode uses the deterministic fake adapters (cache ids
+"fake-sam" / "fake-judge", same as smoke); real mode is the default.
+`--no-judge` keeps the M2 segmentation-only output.
 """
 
 from __future__ import annotations
@@ -20,10 +21,11 @@ if str(_BACKEND_ROOT) not in sys.path:
 from PIL import Image  # noqa: E402
 
 from app.adapters.base import AdapterNotConfiguredError  # noqa: E402
+from app.adapters.muse_spark import JudgeValidationError  # noqa: E402
 from app.config import settings  # noqa: E402
 from app.pipeline.inspect import load_profile, run_inspection  # noqa: E402
 from app.pipeline.overlay import make_overlay  # noqa: E402
-from app.pipeline.wiring import build_segmenter  # noqa: E402
+from app.pipeline.wiring import build_judge, build_segmenter  # noqa: E402
 
 
 def _format_mm(value: float | None) -> str:
@@ -39,12 +41,21 @@ def _print_detection_line(detection) -> None:
     )
 
 
-def cmd_inspect(args: argparse.Namespace) -> int:
-    if not args.no_judge:
+def _print_verdict_block(verdict) -> None:
+    print(f"verdict: {verdict.verdict} confidence={verdict.confidence:.2f}")
+    for ruling in verdict.rulings:
+        violated = ruling.rule_violated if ruling.rule_violated else "-"
         print(
-            "note: M2 stops after segmentation; judging arrives in M3.",
-            file=sys.stderr,
+            f"ruling {ruling.detection_id}: "
+            f"real_defect={ruling.is_real_defect} "
+            f"rule_violated={violated} reason={ruling.reason}"
         )
+    for missed in verdict.missed_defects:
+        print(f"missed: {missed}")
+    print(f"summary: {verdict.summary}")
+
+
+def cmd_inspect(args: argparse.Namespace) -> int:
     try:
         profile = load_profile(args.profile)
     except ValueError as exc:
@@ -57,12 +68,39 @@ def cmd_inspect(args: argparse.Namespace) -> int:
     except Exception as exc:
         print(f"error: could not open image {image_path}: {exc}", file=sys.stderr)
         return 1
+    reference = None
+    if args.reference is not None:
+        reference_path = Path(args.reference)
+        try:
+            with Image.open(reference_path) as raw:
+                reference = raw.convert("RGB").copy()
+        except Exception as exc:
+            print(
+                f"error: could not open reference image {reference_path}: {exc}",
+                file=sys.stderr,
+            )
+            return 1
     segmenter = build_segmenter(args.fake)
     try:
-        detections = run_inspection(image, profile, segmenter)
+        if args.no_judge:
+            detections = run_inspection(image, profile, segmenter)
+            verdict = None
+        else:
+            judge = build_judge(args.fake)
+            detections, verdict = run_inspection(
+                image,
+                profile,
+                segmenter,
+                judge=judge,
+                rules=args.rules,
+                reference=reference,
+            )
     except AdapterNotConfiguredError as exc:
         print(f"error: {exc}", file=sys.stderr)
         return 1
+    except (JudgeValidationError, ValueError) as exc:
+        print(f"error: {exc}", file=sys.stderr)
+        return 1
     overlay_dir = Path(settings.data_dir) / "runs" / "cli"
     overlay_dir.mkdir(parents=True, exist_ok=True)
     overlay = make_overlay(image, detections)
@@ -73,6 +111,8 @@ def cmd_inspect(args: argparse.Namespace) -> int:
     for detection in detections:
         _print_detection_line(detection)
     print(f"overlay: {overlay_path}")
+    if verdict is not None:
+        _print_verdict_block(verdict)
     return 0
 
 
@@ -85,12 +125,22 @@ def main(argv: list[str] | None = None) -> int:
     inspect.add_argument(
         "--no-judge",
         action="store_true",
-        help="Stop after segmentation (M2 always stops here; judging arrives in M3).",
+        help="Stop after segmentation with the M2 output (no verdict).",
+    )
+    inspect.add_argument(
+        "--rules",
+        default=None,
+        help="Inline rules text replacing the profile rules for this run only.",
+    )
+    inspect.add_argument(
+        "--reference",
+        default=None,
+        help="Path to a known-good reference image (else profile reference).",
     )
     inspect.add_argument(
         "--fake",
         action="store_true",
-        help="Use the deterministic fake segmenter instead of the real Meta API.",
+        help="Use the deterministic fake adapters instead of the real Meta API.",
     )
     inspect.set_defaults(func=cmd_inspect)
     args = parser.parse_args(argv)
```
