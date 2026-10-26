# Falsify — M1 must-fix findings (`feat/zeroshot-qc-m1` @ a1a569c)

Read-only rulings. No code was changed. Every finding below was reproduced
with a real run in `backend/.venv` (Python 3.11.13; baseline
`cd backend && .venv/bin/python -m pytest -q` → 23 passed) or, for test-gap
findings, by a mutation in a `/tmp/mut_*` copy that the current suite fails
to catch. Intent: `plan.md` + `tasks.md` + `context-pack.md` in this folder.

Scope: 13 must-fix findings — correctness MF-1/MF-2, security S1/S2,
structure S1/S2/S3, tests M1–M6. `review-impact.md` contains no must-fix
findings (its own verdict is "Nothing blocks M1"), so there is nothing to
rule on in that file. Security "Consider" (C1–C6), correctness "Consider",
structure "Consider", and tests "Consider" items were out of scope.

## Rulings (worst harm first)

fix: Cleartext-HTTP credential/image exposure in all three real adapters (security review). Reproduced: stubbed `httpx.post` recorded `POST http://127.0.0.1:9/meta` with `Authorization: Bearer [REDACTED] and no scheme rejection (`sam.py:40,52`, `muse_spark.py:59,79`, `muse_image.py:44,61` read `settings.meta_api_base_url` verbatim). Who hits it: the operator on the acceptance-6 real-key smoke — one `http://` typo or docs paste sends the key and every base64 inspection image in plaintext to any on-path observer. Harm: credential theft + image disclosure. Fix is a scheme check, no new setting needed.
fix: Unchecked remote RLE crashes smoke `IndexError` and feeds attacker-sized input to the native decoder (security review). Reproduced: donor RLE with `size [200,200]` on a 40×30 image — adapter passed it through verbatim (`sam.py:59-65`, `mask_rle: dict` unvalidated at `schemas.py:11`), then `_make_overlay` raised `IndexError: boolean index did not match … dimension is 30 but corresponding boolean dimension is 200` because indexing at `smoke.py:157` sits outside the `try/except`. No adversary needed: the Meta shape is still a `TODO(meta-docs)` placeholder, so the first unexpected real response hits this, and the bad dict is persisted to the disk cache and replayed.
fix: Smoke overwrites overlays when images share a file stem (correctness review). Reproduced: `--fake` run over `cat1/000.png`, `cat2/000.png`, `cat3/000.png` printed three `000: …` lines and exited 0, but `data/runs/smoke/` held exactly one file, `000_overlay.png` (`path.stem` at `smoke.py:181`, `<stem>_overlay.png` at `smoke.py:222`). Who hits it: anyone pointing smoke at a tree with repeated stems (MVTec-style `…/000.png` layouts); the run reports success while silently losing two of three overlays, violating acceptance 2 / the 3-overlay verification check.
fix: Smoke verdict-validation failure escapes as a traceback instead of clean exit 1 (correctness review). Reproduced: stubbed SAM (valid mask) + judge returning `confidence: 99` made `smoke.main([])` raise `pydantic ValidationError` out of `muse_spark.py:87` via `smoke.py:251`, instead of returning 1. The `ValidationError` handler at `smoke.py:256` only wraps the round-trip of an already-validated `Verdict`, which cannot fail. Who hits it: the acceptance-6 operator the first time the real judge returns an out-of-range verdict. This breaks the written exit contract (`tasks.md`: validation failures print to stderr and exit 1, no traceback), so the repo-rule limit applies.
fix: Judge cache misses for detections/overlay/reference/judge-model are untested (tests review). Reproduced by mutation: rewriting `judge_cache_key` to hash only image+profile still gave `9 passed`. Current code is correct — direct probe confirms all five dimensions change the key today — so this is missing regression protection, not a live bug. Harm if the key regresses: a stale PASS/FAIL verdict is served for different detections/reference with no model call, i.e. a wrong QC decision.
fix: Segment cache miss for a changed image is untested (tests review). Reproduced by mutation: dropping `_png_bytes(image)` from `segment_cache_key` still gave `9 passed`; current key does vary by image (probe). Harm if it regresses: two different product photos with the same prompts/model collide and the first photo's masks are returned for the second.
fix: Not-configured guard proven only for all-empty config (tests review). Reproduced by mutation: narrowing the judge guard to `if not settings.judge_model_id:` still gave `11 passed`. Current guards are correct — probe shows each single empty field (key/base/model) raises `AdapterNotConfiguredError` with zero HTTP calls — so this is a test gap. Who hits the underlying behaviour: an operator who sets two of the three values and forgets one; without the guard the adapter would POST to `""` with an empty Bearer [REDACTED] instead of the specified clear error.
fix: HANDOFF §6 schema bounds/defaults have no direct tests (tests review). Reproduced by mutation: unbounded `confidence` plus `min_score 0.3 → 0.9` still gave `23 passed`. Current schemas are correct — probe: `confidence` −0.1/1.5 rejected, 0.0/1.0 accepted, omitted `rule_violated` rejected, `min_score` defaults to 0.3. Harm if they drift: M2 thresholding and judge-confidence display silently change meaning.
fix: Fake-RLE test never decodes the fake mask (tests review). Reproduced by mutation: `counts → "!!!not-rle!!!"` in `fakes.py:47` still passed all of `test_adapters.py` (11 passed), while the real consumer `mask_api.decode` raises `ValueError: Invalid RLE mask representation` on the same value; the unmutated fake decodes fine (40×30 fixture areas 108/224). The asserts at `test_adapters.py:79-85` are vacuous (bare `json.dumps`, bytes truthiness, unrelated blank array). Harm: M2 measure code is built against a fake whose core contract is unproven.
narrow: Smoke (acceptance 2) and its clean-exit paths have zero pytest coverage (tests review). Confirmed: `grep smoke backend/tests/` finds no import; the suite is green by construction while MF-1/MF-2 above lived undetected in smoke. Narrowed, not taken whole: the plan deliberately makes smoke "Verification, not a unit test", and the fake/real cache-id separation is already covered by the changed-model cache tests. One automated fake-smoke test plus the data-missing exit is worth code; the rest stays manual verification.
leave open: Adapter wiring lives only in the smoke script (structure review). Traced: `build_adapters` (`smoke.py:46`) is called only from smoke `main()`; `main.py` imports no adapter/cache/router, so no M1 caller is harmed today — health never constructs an adapter. `tasks.md` explicitly tasks the wiring into `smoke.py` for M1, so the code follows its contract; extracting it now creates a `deps` module with no consumer. The duplication cost is real but arrives with M2's first router. One PR line below.
leave open: Cache-key model ID vs adapter model ID can diverge (structure review). Mechanism reproduced only by mutating the global `settings` between wiring and call (wrapper keyed `model-A`, HTTP payload sent `model-B`); no M1 code path does this — the CLI wires once and calls immediately. The impact review independently rates this "unlikely in M1, medium later" with an M3 check. Constructor injection across all three adapters is architectural churn for a state that cannot occur in the shipped wiring. One PR line below.
dismiss: RLE decode + overlay rendering is stranded in the smoke script (structure review). Factually true (`_decode_mask`/`_make_overlay` exist only at `smoke.py:125/142`), but as an M1 must-fix it is wrong: `context-pack.md` records the tint as smoke-local with M2 owning `pipeline/overlay.py`, `tasks.md` defers `pipeline/overlay.py` and tasks the overlay as smoke-local, and the structure review's own scope files pack-named deferrals under Noted. No M1 caller besides smoke exists. Re-file as the first M2 extraction step.

## For the fixer

- fix: Require HTTPS before any adapter HTTP (security S1). In each real adapter's guard path, reject a non-`https` `meta_api_base_url` with `AdapterNotConfiguredError` before `httpx.post`. Add no opt-in flag — an `ALLOW_HTTP` setting is exactly the special case this ruling refuses; if a local mock server is ever needed, that is a separate decision. Proving test: with key/model set and `http://` base URL, each adapter raises before HTTP (stub records zero calls); the `https://` stubbed path is unaffected.
- fix: Validate remote RLE before native decode (security S2). In `SamSegmenter` reject/repair masks whose `mask_rle["size"] != [image.height, image.width]` or whose `counts` is not `str`/`bytes` within a sane length cap, and in smoke move the `overlay_arr[sel]` indexing inside the existing `try/except` (or skip masks whose decoded shape ≠ image shape). Proving test: the `[200,200]`-on-40×30 fixture no longer raises out of `_make_overlay`/`main` (fails now with `IndexError`, passes with the fix), and a malformed mask never reaches the disk cache.
- fix: Disambiguate overlay filenames on stem collision (correctness MF-2). Keep `<stem>_overlay.png` when unique; on collision include the parent folder name or an index. Proving test: three same-stem images in different folders produce three distinct overlay files (fails now: one file, passes with the fix).
- fix: Catch `ValidationError` around the judge call in smoke (correctness MF-1). Extend the `except` at `smoke.py:250` (or wrap judge call + round-trip in one `try`) so a verdict that fails validation inside `MuseSparkJudge` prints `error: …` to stderr and returns 1. Proving test: stubbed judge returning `confidence: 99` asserts `smoke.main([]) == 1` with no raised exception (raises now, passes with the fix).
- fix: Add judge cache-miss tests for detections, overlay, reference `None`→image and image→different-image, and judge model ID (tests M2), each asserting the inner call count increments and the repeat then hits. Proving condition: all fail against the image+profile-only key mutation above, pass against the current key.
- fix: Add a segment cache-miss test with a different image (same prompts/model → miss, repeat → hit) and pin prompt-order sensitivity (tests M3). Proving condition: fails against the image-dropped key mutation, passes now.
- fix: Parametrize the not-configured guard per adapter × per single empty field (key/base/model), asserting `AdapterNotConfiguredError` and zero HTTP calls (tests M6). Proving condition: fails against the judge-guard mutation, passes now.
- fix: Add direct schema tests (tests M5): `confidence` −0.1/1.1 rejected and 0.0/1.0 accepted, `verdict` literal enforced, `DefectRuling` without `rule_violated` raises while `None`/string validate, `ProductProfile.min_score` defaults to 0.3, `Detection` mm fields default to `None`. Proving condition: fails against the unbounded-confidence/`min_score=0.9` mutation, passes now.
- fix: Make the fake-RLE test decode (tests M1): pass each fake mask's own `counts` to `mask_api.decode`, assert shape `(H, W)`, `area > 0`, and area equals the decoded sum; delete the vacuous `test_adapters.py:79-85` asserts. Proving condition: fails against the `"!!!not-rle!!!"` mutation, passes now.
- narrow: Add one automated smoke test only (tests M4): tmp `DATA_DIR`/`MVTEC_DIR`, `--fake` exits 0 with 3 count lines, 3 overlay files, and a parseable `Verdict` line; plus empty-dirs real mode exits 1 with "data missing" on stderr and no `Traceback`. Leave real-mode not-configured coverage to the guard tests and acceptance 6 manual.

## For the user

- None. No finding requires a new rule, setting, or flag; the one proposed flag (an HTTP opt-in for security S1) is refused above rather than decided here.

## For the PR's open findings

- leave open: Adapter wiring lives only in `scripts/smoke.py` (`build_adapters`, `smoke.py:46`); extract it to `app/deps.py` when M2 mounts the first router so routers never import from `scripts/`.
- leave open: `Cached*` wrappers snapshot the model ID at wiring while real adapters re-read live `settings` at call time; inject config or rebuild wrappers on settings change when a long-lived (M3) wiring exists — no M1 path mutates settings between wiring and call.

## Dismissed

- dismiss: RLE decode + overlay rendering stranded in smoke (structure S3) — explicit M1 deferral, not a defect: smoke-local overlay is the tasked M1 contract (`context-pack.md`, `tasks.md` defer `pipeline/overlay.py` to M2). Re-file as M2's first extraction step.

## Fix outcome

All 9 `fix` items and the 1 `narrow` item above were implemented; no
leave-open / your-call / dismissed item was touched and no new rule,
setting, or flag was added. Production: HTTPS-only guard in all three
real adapters, SAM remote-RLE validation (`size`/`counts` type + length
cap, malformed masks dropped before caching), smoke overlay shape guard
with indexing inside `try/except`, stem-collision overlay names
(`<stem>_overlay.png`, then `<stem>_2_overlay.png`, …), and
`ValidationError` caught around the smoke judge call. Tests: judge
cache misses (detections/overlay/reference/model), segment
changed-image + prompt-order misses, per-adapter × per-field
not-configured matrix plus HTTP/HTTPS adapter tests, direct schema
bounds/defaults tests, fake-RLE decode asserts, one fake-smoke +
data-missing smoke test, and smoke collision/validation/overlay tests.
Each new test was mutation-checked to fail without its fix.
Verification: `cd backend && .venv/bin/python -m pytest -q` → 62 passed.
