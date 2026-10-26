# Correctness review — M2 (`feat/zeroshot-qc-m2`)

Sources: [.plans/zeroshot-qc-m2/context-pack.md](.plans/zeroshot-qc-m2/context-pack.md)
("Do not re-derive" bullets) and [plan.md](.plans/zeroshot-qc-m2/plan.md)
Acceptance Criteria 1–4 (AC5 is manual, not reviewed here). Scope: correctness only.

Baseline, all passing: `81 passed` full suite (`cd backend && .venv/bin/python -m pytest -q`);
`backend/scripts/smoke.py --fake` prints 3 `stem: scratch=…` count lines + 1 `verdict:` line
and writes 3 overlays (AC3 shape holds).

Verified correct (each by real run, see Proof appendix): rect measurement
`area=5000 len=99.0 bbox=(10,5,100,50)`; mm scaling `area*mm² / len*mm`, `None` when
unset; empty-mask `measure_mask` zeroes without raising; `score>=min_score` keeps with
equality kept (0.29 drop / 0.30 keep); strict `IoU>0.5` (exactly 0.5 does NOT merge);
merge keeps higher score, joins distinct labels once, score-desc `d1…` ids with label
tiebreak; size-mismatched and undecodable (`bad counts`, `{}`) RLE warn-and-skip;
CLI bottle mm values vs screw `-`, overlay saved, exit 0; unknown profile / bad image /
missing keys / schema-bad profile / malformed JSON all `error:` on stderr, exit 1, no
traceback; empty detections print `no detections`, save unmarked overlay (pixel-identical),
exit 0; CWD-independent (`backend/` launch identical); merged RLE `counts` stays `str`.

## Must-fix

### MF1 — Zero-area masks are emitted as `(0,0,0,0)` detections instead of skipped
- Where: `backend/app/pipeline/inspect.py` `_decode_valid_masks` (no area check);
  same gap in `backend/scripts/smoke.py` `_masks_to_detections`.
- Proof (real runs, `/tmp/m2_probe1.py`): one all-zero mask →
  `ndets=1 bbox=(0, 0, 0, 0) area=0` (P6); two all-zero masks → 2 detections (P7).
  Failing-now test `/tmp/test_m2_zero_area.py::test_zero_area_mask_is_skipped`
  fails with `Left contains one more item: Detection(id='d1', … bbox=(0, 0, 0, 0),
  area_px=0 …)` and would pass with the fix.
- Why wrong: reintroduces the placeholder `bbox=(0,0,0,0)` the plan's Problem
  statement says M2 eliminates; contradicts the context-pack's
  "empty masks → zero detections"; the overlay stamps a misleading `d1 label` at the
  origin; M3's judge would rule on vacuous candidates. Reachable: the real SAM
  adapter validates RLE shape/counts, not area, so an all-zero mask passes through.
- Fix: skip `binary.sum() == 0` with `warnings.warn` in `_decode_valid_masks`
  (existing warn-and-skip precedent), same hardening in `_masks_to_detections`.

## Consider

### C1 — Merge compares each candidate to the union, so `pairwise IoU > 0.5` chains can split
- Where: `backend/app/pipeline/inspect.py` `run_inspection` merge loop
  (`_mask_iou(binary, group["mask"])`).
- Proof (`/tmp/m2_probe1.py` P11): A=[10,70), B=[25,85), C=[40,100) (h=50):
  `IoU(A,B)=0.600`, `IoU(B,C)=0.600`, but `IoU(C, union(A,B))=0.500` → strict `>`
  fails → output is 2 detections (`scratch+crack`, `dent`) although both pairs
  exceed 0.5. A member-vs-member (transitive) reading of the plan's "greedily merge
  pairs above 0.5" would yield 1 detection.
- Fix options: compare against each group member (transitive merge), or keep
  union-compare and document it as intended (C overlaps A only 0.33, so splitting is
  defensible). No AC pins chain behavior; either way, add a test locking it in.

## Noted

- N1 — CLI same-stem images from different dirs overwrite one overlay across runs
  (`a/part.png` then `b/part.png` both → `data/runs/cli/part_overlay.png`; sha
  changed `6a9501…` → `2c8427…`). Within-run one-per-image holds (single-image CLI);
  standard CLI behavior; no AC violated.
- N2 — Single-pixel `length_px=0.0`, 100×50 rect `length_px=99.0`: spec-defined
  `minAreaRect` point-span (context-pack), not a bug.
- N3 — `area_mm2` float artifact (`5000*0.1**2 = 50.00000000000001`): absorbed by
  `pytest.approx` and CLI `%.2f`. Not a bug.
- N4 — `overlay.py` `ndim == 3` squeeze branch is unreachable (single-RLE decode is
  always 2D, probe P1); `inspect.py` lacks it, but the input never triggers either
  path. Harmless.
- N5 — Real-SAM network/runtime errors propagate with traceback: carries diagnostics;
  the contract requires clean `error:` only for profile/image/keys (all verified).
- N6 — Smoke ids follow mask order, orchestrator ids score order: throwaway path,
  output shape preserved, `FakeJudge` order-insensitive.

## Dismissed (checked, not findings)

- D1 — Suspected `ValidationError` traceback on schema-bad profile: wrong.
  Pydantic `ValidationError` subclasses `ValueError`, so the CLI's
  `except ValueError` prints clean `error: 2 validation errors…`, exit 1, no
  traceback (proven; same for malformed JSON text via `JSONDecodeError`).
- D2 — Suspected missing-keys traceback (`build_segmenter` outside `try`): wrong.
  `require_configured` raises at segment time inside the `try` → clean
  `error: SAM adapter is not configured…`, exit 1 (proven).
- D3 — Merged `a+b` labels hitting the fallback tint: per spec (context-pack:
  lookup on the full label string). Not a bug.
- D4 — `IoU == 0.5` boundary: verified no-merge (probe P5, A=4px/B=2px-inside);
  strict `>` matches the plan. Correct.

## Proof appendix (commands, workspace root unless noted)

- `cd backend && .venv/bin/python -m pytest -q` → `81 passed, 2 warnings`
- `backend/.venv/bin/python backend/scripts/smoke.py --fake` → 3 count lines +
  1 `verdict:` line; 3 `*_overlay.png` under `data/runs/smoke/`
- `backend/.venv/bin/python /tmp/m2_probe1.py` → P1–P11 lines quoted above
- `backend/.venv/bin/python -m pytest /tmp/test_m2_zero_area.py -q` → 1 failed (MF1)
- `backend/.venv/bin/python cli.py inspect /tmp/m2cli/solo.jpg --profile bottle --no-judge --fake`
  → 3 detection lines with mm values + `overlay: …/data/runs/cli/solo_overlay.png`, exit 0
  (`screw` → `area_mm2=- length_mm=-`; tie `0.67/0.67` → label tiebreak `d2/d3`)
- Unknown profile / missing image / real-mode-without-keys / schema-bad profile /
  malformed JSON → `error:` on stderr, stdout empty, exit 1, `grep -c Traceback` = 0
- `cmd_inspect` with empty segmenter → `no detections` + overlay line, exit 0;
  saved overlay pixel-identical to `make_overlay(image, [])`; `{}` RLE →
  `skipping undecodable RLE … 'size'`, 0 detections
- From `backend/`: `.venv/bin/python ../cli.py inspect …` → identical detections and
  overlay path (CWD-independent)
