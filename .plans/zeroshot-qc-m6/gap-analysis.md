# ZeroShot QC M6 — gap analysis (Plan mode)

Date: 2026-10-27. Branch `feat/zeroshot-qc-m6`. Diff base: `main`.
Method: read `plan.md` + `tasks.md`, read the routers/pages/tests the diff touches,
reproduced guards by execution (`pytest`, `tsc`, `vite build`, secret grep).

## Acceptance-criteria table

| ID | Criterion | Met? | Evidence |
|---|---|---|---|
| AC1 | Browser inspect e2e: upload → hoverable overlay → verdict card with reasons | Yes | `frontend/src/pages/Inspect.tsx`; `walkthrough.md` §1: fixture upload → 200 FAIL/3 detections, overlay GET 200 `image/png`; all four Vite routes HTTP 200 |
| AC2 | Rule edit flips verdict without re-upload (judge-only, visibly fast) | Yes | `walkthrough.md` §1 step B: same bytes + new rules → PASS, segment 1ms→0ms (cache hit), total 21ms→8ms; `test_inspect_same_image_new_rules_is_judge_only_cache_hit` (`backend/tests/test_routers.py:94`); debounce + `AbortSignal` in `Inspect.tsx` (review-correctness confirmed) |
| AC3 | Profiles round-trip; Eval table+chart+failures; Synthetic gallery groups | Yes | `walkthrough.md` §§2–4: 15 profiles, draft→PUT→re-GET round-trip, id-mismatch 422; 6 eval runs, summary keys + 10 rows, failure image 200; gallery 11 entries `{(bottle,scratch):10,(bottle,dent):1}`, `_reference.png` excluded |
| AC4 | `pytest` green; `tsc` + `vite build` clean; no secrets in frontend | Yes | Re-ran this session: `164 passed` (`cd backend && .venv/bin/python -m pytest -q`); `tsc --noEmit` exit 0; `vite build` ✓ 112ms; `grep` for keys/secrets in `frontend/src` → no hits |
| AC5 | `manual:` second-device walkthrough | Can't tell | Human step, `tasks.md` box unchecked. Nothing in the branch can satisfy it; needs a person with two devices on the LAN. |
| F1 | Synth generation endpoint reusing M5 `generate_pairs` | Yes | `backend/app/routers/synth.py:85`; `test_synth_generate_happy_n_and_unknown_profile`, `test_synth_generate_traversal_rejected_without_writes` |
| F2 | `/files/...` static serving from `data/` with traversal blocked | Yes | `backend/app/main.py` `serve_data_file`; `test_files_traversal_blocked`, `test_files_missing_backslash_absolute_are_404`; live `..`/`%2F` probes → 404 |
| F3 | Eval read-only; no webcam; routers share CLI-grade functions | Yes | `Eval.tsx` calls only list/get (no launch); no `getUserMedia`/webcam in `frontend/src`; `test_cli_parity_identical_verdicts` |

## Divergence note — `GET /api/synth/gallery`

`plan.md` "Divergence notes" declares it: HANDOFF §8 assumed a listing that didn't
exist, so `routers/synth.py:list_synth_gallery` enumerates `data/synth/` as grouped
`{category, defect, image_url, mask_url|null}` pairs, skipping `_reference.png` and
tolerating missing masks. **Judgment: legitimate minimal-means addition.**
It is read-only, serves only `/files/...` URLs under the same traversal-safe
mount, was explicitly authorized in `tasks.md` ("Synthetic.tsx blocked on this"),
and is covered by `test_synth_gallery_grouping_reference_skip_and_missing_mask`
plus `test_synth_gallery_empty_dir` and the live walkthrough (§4).

## Record reconciliation (`.agents/RECORD.md`)

All 5 entries `plan.md` Record Updates promised are present verbatim (lines 59–63)
and each holds against the build: FastAPI routers + `/files/` serving; four pages;
judge-only rule re-runs (AC2 evidence); Eval read-only (F3); file upload, no webcam.
No existing entry was broken or made stale by this work. No cosmetic edits needed.

Proposed new entry (gallery endpoint establishes a high-level API fact; needs
human approval per Record rules — **not written**):

```markdown
- (synth) The synthetic gallery is currently served by GET /api/synth/gallery enumerating data/synth/ pairs with /files/ URLs.
```

## Gaps

- G0 (AC5): second-device manual walkthrough still pending — human step, not fixable here.
- All falsify must-fix findings (synth traversal, absolute `reference_image`,
  missing route tests) were already fixed pre-check (`62c13af`) and verified
  present + green in this session. No automated gaps found; no code changes made.

## Next

1. Human: run the AC5 second-device walkthrough, then check the `manual:` box.
2. Human: approve/reject the proposed `(synth)` gallery Record entry.
3. Merge `feat/zeroshot-qc-m6` (M5 already merged per plan).
