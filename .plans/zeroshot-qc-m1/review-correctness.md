# Correctness review — M1 (`feat/zeroshot-qc-m1` @ a1a569c)

Scope: correctness only (health shape, fake determinism, cache hit/miss semantics,
not-configured guards, smoke exits). Spec sources read first:
[context-pack.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/context-pack.md:55)
(acceptance criteria verbatim at lines 55–64, API contracts at 37–44,
do-not-re-derive at 66–74) and
[plan.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/plan.md:23)
(acceptance criteria 1–6 at lines 25–30, detailed contract in
[tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:35)
lines 35–39). Baseline verified: `cd backend && .venv/bin/python -m pytest -q`
→ 23 passed. All findings below were reproduced with real runs in
`backend/.venv` (Python 3.11.13); no code was changed by this review.

## Must-fix

### MF-1. Smoke verdict-validation failures escape as a traceback, not clean exit 1

Spec: verdict-validation failures print a clear stderr message and exit 1 with
no traceback ([tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:39));
context pack restates the smoke exit contract
([context-pack.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/context-pack.md:73)).

Code: the real judge validates inside itself at
[muse_spark.py:87](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/app/adapters/muse_spark.py:87)
(`Verdict.model_validate(data)`), but smoke only catches
`AdapterNotConfiguredError` around the judge call at
[smoke.py:250](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/scripts/smoke.py:250);
its `ValidationError` handler at
[smoke.py:256](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/scripts/smoke.py:256)
wraps only the redundant round-trip of an already-validated `Verdict`, which
cannot fail. So the one real validation failure path is uncovered.

Proof (real run, stubbed `httpx.post`: SAM returns one valid mask, judge
returns `confidence: 99`): `smoke.main([])` raised
`pydantic_core.ValidationError: confidence Input should be less than or equal to 1`
out of `smoke.py:251` → `cache.py:207` → `muse_spark.py:87`, with a full
traceback, instead of returning 1. A test asserting
`smoke.main([]) == 1` and no raised exception fails now and passes once the
judge call is covered.

Fix: catch `ValidationError` around the `judge.judge(...)` call itself
(e.g. extend the existing `except AdapterNotConfiguredError` block at
smoke.py:250–254, or move both judge call and round-trip into one try).

### MF-2. Smoke overwrites overlays when two images share a file stem

Spec: save one PNG overlay per image
([tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:39));
the verification check expects 3 overlay files after a 3-image run
([tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:48)),
and acceptance 2 covers "any 3 images"
([plan.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/plan.md:26)).

Code: smoke keeps only `path.stem` as the image identity at
[smoke.py:181](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/scripts/smoke.py:181)
and names each overlay `<stem>_overlay.png` at
[smoke.py:222](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/scripts/smoke.py:222).

Proof (real `--fake` run): three images `cat1/000.png`, `cat2/000.png`,
`cat3/000.png` printed three `000: scratch=1, crack=1, dent=1` lines and exited
0, but `data/runs/smoke/` contained exactly one file, `000_overlay.png` —
the second and third overlays overwrote the first. A test creating three
same-stem images in different folders and asserting three distinct overlay
files fails now and passes with the fix.

Fix: disambiguate the overlay filename on stem collision (e.g. include the
parent folder name or an index) while keeping `<stem>_overlay.png` for the
unique-stem case.

## Consider

### C-1. Configured-but-failing real adapters also traceback out of smoke

Proof: real smoke against `META_API_BASE_URL=http://127.0.0.1:9` with keys and
model IDs set and 3 images present exited 1 only via an uncaught
`httpx.ConnectError` traceback. The spec enumerates only data-missing,
not-configured, and verdict-validation as clean-exit cases
([tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:39)),
so this is not MF-1, but the manual real-keys readout (acceptance 6) would be
easier to read with a clean `error: …` line. Suggested fix: also catch
`httpx.HTTPError` (and mapping `KeyError`/`ValueError`) around the segment and
judge calls in smoke and return 1.

### C-2. FakeImageGenerator silently returns an unchanged copy for non-RGB inputs

Proof (real run): `FakeImageGenerator().add_defect(img, desc, None)` changed
the image for `RGB`/`RGBA` 20×20 inputs, but returned a byte-identical copy
for `L`, `LA`, `P`, `CMYK`, and `I;16` inputs and for a 1×1 RGB image — two
different defect descriptions then produce identical output, contrary to the
"hash-seeded mark" contract in the class docstring at
[fakes.py:92](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/app/adapters/fakes.py:92).
The M1 task text only requires a deterministic same-size image
([tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:25)),
so this is not must-fix for M1, but M5 synth work will hit it. Suggested fix:
draw in a mode-appropriate way (convert, paint a gray value, or handle the
1×1 case) instead of skipping.

### C-3. Smoke image discovery counts directories named `*.png` as images

Proof (real `--fake` run): with a directory `mvtec/fake.png` plus two real
images `a.png`/`b.png`, smoke exited 1 with
`error: could not open image …/fake.png: [Errno 21] Is a directory` instead of
processing the real images or using placeholders. Root cause: the first glob
loop in `_collect_images` at
[smoke.py:66](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/scripts/smoke.py:66)
appends matches without an `is_file()` check (the second loop at smoke.py:73
does check). Suggested fix: filter the first loop with `path.is_file()` too.

### C-4. Whitespace-only config values count as "configured"

Proof (real run): with `meta_api_key=" "` (or base URL `" "`), each real
adapter passed its guard and attempted HTTP, because the guards at
[sam.py:26](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/app/adapters/sam.py:26),
[muse_spark.py:33](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/app/adapters/muse_spark.py:33),
and [muse_image.py:27](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/app/adapters/muse_image.py:27)
test `if not settings.…`. The spec defines unset as the empty string
([plan.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/plan.md:72)),
and a copied `.env.example` parses to `''` correctly (verified), so this only
bites on a quoted-whitespace `.env` value. Suggested fix: treat
`value.strip() == ""` as unset in the three guards.

## Noted (verified correct, or investigated and dismissed)

- Health shape is exact and leak-free: empty and configured runs return only
  `{"status":"ok","models":{"sam","judge","image"}}` read from `settings` at
  request time ([main.py:20](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/app/main.py:20));
  sentinel key/base-URL never appear (probe + `test_health.py`).
- Fake determinism holds across processes (two separate interpreter runs gave
  identical scores and RLE counts), and all 120 probed fake masks across
  8 image sizes decode through pycocotools with non-zero area and survive a
  JSON/cache round-trip unchanged; overlay tint matched the decoded mask area
  pixel-for-pixel in [smoke.py](/Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/scripts/smoke.py:142).
- Cache semantics are sound: key framing separates prompt boundaries
  (`["ab"]` vs `["a","b"]`, `[]` vs `[""]`), prompt order, model ID, image,
  overlay, reference `None` vs a real reference, detections, and profile all
  miss correctly; empty-prompt results cache as hits; corrupt entries fall
  back to a miss. Verified beyond `test_cache.py` with additional key probes.
- Not-configured guards fire per-field before any HTTP for all three real
  adapters (each of key/base-URL/model-ID emptied individually, HTTP stubbed,
  zero calls recorded). Health stays 200 with empty config.
- Smoke exits are otherwise clean: fake run exits 0 with 3 count lines, a
  `verdict:` line, and 3 overlays; a second fake run leaves the cache file
  count unchanged (4 files); real mode with missing data and real mode with
  data but no keys both exit 1 on stderr with no traceback; uppercase
  `.JPG`/`.PNG` discovery and `cache/`+`runs/smoke/` exclusion work.
- Dismissed: fake-segmenter masks differing when the prompt *list* changes
  (seed is specified as image bytes plus the whole prompt list,
  [tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:25));
  `add_defect` having no default for `mask` (HANDOFF §5 pins no default,
  [tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:21));
  unbounded `RawMask.score` (verbatim schemas bound only `Verdict.confidence`,
  [tasks.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/tasks.md:16));
  `MuseSparkJudge.sop_to_profile` raising `NotImplementedError` and
  `ImageGenerator` being uncached (both explicit M5 deferrals,
  [context-pack.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/context-pack.md:70));
  the `TODO(meta-docs)` Meta request/response mappings (explicitly not a
  settled contract,
  [context-pack.md](/Users/167560.KEVIN/orca/projects/Zeroshot QC/.plans/zeroshot-qc-m1/context-pack.md:43)).
