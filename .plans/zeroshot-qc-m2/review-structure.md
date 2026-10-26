# Structure review — feat/zeroshot-qc-m2

Scope: structure only (module boundaries, M1 contract preservation,
cli/smoke wiring duplication, dead code, profile-loading placement).
Source of truth for intended contracts:
[.plans/zeroshot-qc-m2/context-pack.md](.plans/zeroshot-qc-m2/context-pack.md)
(API contracts §, "Do not re-derive" §). Branch: `feat/zeroshot-qc-m2`
(14 files, +828/-51 per context pack; `cache.py`, `base.py`,
`schemas.py` unchanged in the diff stat — M1 surface untouched).

## Must-fix (3)

1. `cli.build_segmenter` duplicates smoke's segmenter wiring
   (`cli.py:31-36` vs `backend/scripts/smoke.py:39-52`).
   Proof: the docstring admits it — "Mirror smoke.build_adapters'
   segmenter half (incl. "fake-sam" id)". Cache root
   (`Path(settings.data_dir) / "cache"`), the `"fake-sam"` id, and the
   Fake/SAM selection now live in two places.
   Why it costs: the next adapter or cache-id change (M3 adds judge
   wiring to the CLI) must be edited twice; a one-sided edit silently
   splits or poisons the disk cache. Fix: one shared builder (e.g.
   `app/pipeline/wiring.py`, or CLI imports from a smoke-independent
   home) used by both entry points.

2. `smoke._masks_to_detections` is a second RawMask→Detection pipeline
   bypassing `run_inspection` (`backend/scripts/smoke.py:104-131` vs
   `backend/app/pipeline/inspect.py:79-124`).
   Proof: it measures and assigns `d1...` ids in raw mask order with
   no `min_score` filter, no IoU merge, no score ordering — the three
   behaviors the context pack defines as the orchestrator's contract.
   Smoke is therefore the only producer that never exercises M2's
   orchestrator.
   Why it costs: every future `run_inspection` change (M3 judge
   expects merged, score-ordered detections) needs a mirror edit in
   smoke or smoke output silently diverges from CLI semantics. Fix:
   run smoke images through `run_inspection` with a smoke
   `ProductProfile` (it already builds one at `smoke.py:208-213`,
   currently only for the judge).

3. `inspect_image` is dead in production; the CLI hand-rolls the same
   path (`backend/app/pipeline/inspect.py:127-133` vs `cli.py:58-72`).
   Proof: repo-wide grep shows the only `inspect_image` caller is
   `backend/tests/test_inspect.py:255`; `cmd_inspect` re-implements
   open-image + `load_profile` + `run_inspection` line for line.
   Why it costs: two disk-loading paths for one operation — error
   semantics (exit-1 `error:` vs traceback) and future steps (M3
   reference-image loading) drift apart. Fix: either route the CLI
   through `inspect_image` with its exceptions mapped to `error:`
   exits, or delete `inspect_image` and keep the CLI path canonical.

## Consider (4)

4. Decode-and-validate logic exists in three places:
   `inspect._decode_valid_masks` (`inspect.py:58-76`),
   `make_overlay`'s loop (`overlay.py:36-53`), and
   `_masks_to_detections` (`smoke.py:113-119`) — each with its own
   try/except + `warnings.warn` + shape check. Both pipeline modules
   already import `decode_rle` from `measure.py`, so a shared
   `decode_valid` helper there would add no new edge to the module
   graph. Costs one edit per policy change today; grows if M3 adds a
   third consumer.

5. Profile loading lives inside the orchestrator (`inspect.py:23-37`:
   `PROFILES_DIR` + `load_profile` + `json`/`pathlib` imports).
   Proof of the awkward seam: `test_inspect.py:252-257` monkeypatches
   the module global `PROFILES_DIR` to test `inspect_image`.
   `run_inspection` itself is clean (takes a `ProductProfile` value),
   but any M3 consumer of profiles (judge needs `rules`) must import
   the segmentation orchestrator for config I/O. Consider
   `app/profiles.py` (or config-adjacent) owning `PROFILES_DIR` +
   `load_profile`.

6. RLE text-encoding is tripled: `inspect._encode_mask_text`
   (`inspect.py:48-55`) plus private doubles in
   `test_inspect.py:27-38` and `test_measure.py:23-24`. Tests cannot
   import the underscore-private helper, so the Fortran-order
   requirement the context pack flags ("C-order raises ValueError")
   is asserted in three copies. Consider a public `encode_mask_text`
   in `measure.py` next to `decode_rle`, reused by orchestrator and
   tests.

7. Smoke counts from raw masks but renders/judges from detections
   (`smoke.py:180-192`): the `{stem}: scratch=N, ...` line counts
   pre-skip `masks`, while the overlay and judge input use
   post-skip `detections`. After any warn-and-skip, the count line
   disagrees with what was rendered and judged. Consider deriving
   counts from `detections` so one list is the source of truth
   (keeps the context-pack smoke shape: same lines, consistent
   numbers).

## Noted (no action)

- M1 contracts preserved: `Segmenter`/`Judge` protocols
  (`base.py:36-49`) and `cache.py` are byte-identical to main;
  `run_inspection(image, profile, segmenter)` depends only on the
  `Segmenter` protocol (`inspect.py:80`), so `CachedSegmenter`,
  `FakeSegmenter`, and `SamSegmenter` slot in unchanged. Per the
  context pack, the M1 byte-vs-text RLE risk carries over knowingly.
- Clean boundaries worth keeping: `measure.py` is pure (no config,
  no I/O — only `cv2`/`numpy`/`pycocotools`); overlay's caller-saves
  convention is honored by both callers (`cli.py:80`,
  `smoke.py:200`); smoke's old local tint code was deleted rather
  than forked, so the palette now has a single home
  (`overlay.py:15`).
- `reference_image`, `rules`, and the `--no-judge` flag are unused /
  no-op in M2 (`cli.py:53-57`, `schemas.py:33`) — intentional M3
  scaffolding per the context pack, not dead code. Revisit when the
  judge lands; do not "clean up" the flag before M3 wires it.
- Merged-label fallback tint (`scratch+crack` → `(255, 200, 0)`,
  `overlay.py:56-58`) is a known context-pack behavior, not a
  structure defect; a per-component tint lookup would be a display
  decision, out of scope for this review.
