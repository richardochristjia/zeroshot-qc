# Structure review — feat/zeroshot-qc-m6

Source: [context-pack.md](.plans/zeroshot-qc-m6/context-pack.md) (BASE main/M5; 33 files, +5477/-21; four routers + `/files` serving + Vite frontend behind `frontend/src/api.ts` choke point; admitted divergence: new read-only `GET /api/synth/gallery`).

Scope: structure only — router/CLI sharing, gallery placement, component boundaries, duplication, dead code. No behavior verdicts.

## Must-fix

1. **Dead exports `generateSynthetic` + `toProfileBody` in the choke-point client.**
   Proof: `frontend/src/api.ts:715` defines `generateSynthetic`; `frontend/src/api.ts:744` defines `toProfileBody`; repo-wide grep shows zero call sites (`Synthetic.tsx` calls only `listSyntheticGallery`).
   Why it costs: the "sole backend choke point" now ships an untested POST path nobody exercises (no page UI, no jsdom suite per context-pack §Test entry points) and a serializer (`toProfileBody`) duplicating `putProfile`'s inline body (`api.ts:655-663`) — two PUT-body shapes to keep in sync. Delete both, or wire the generate UI they imply.
2. **`errorDetail` triplicated across pages, plus two inline copies.**
   Proof: identical 4-line helper at `frontend/src/pages/Eval.tsx:13`, `frontend/src/pages/Synthetic.tsx:6`, `frontend/src/pages/Profiles.tsx:15`; same ternary inlined twice more at `frontend/src/pages/Inspect.tsx:73,112`.
   Why it costs: the ApiError→string mapping is the one policy every page shares; a taxonomy change (e.g. new 422 subtype) needs 4–5 coordinated edits today. Move it into `api.ts` (or a `pages/_shared.tsx`) and import it.
3. **Router imports the app entry: inverted layering in `profiles.py`.**
   Proof: `backend/app/routers/profiles.py:27-36` — `_get_sop_judge()` does `from app.main import _get_sop_judge` lazily at request time to dodge the cycle that the layering itself creates; sibling routers instead own local factories over `pipeline/wiring.py` (`routers/inspect.py:34-47`, `routers/synth.py:27-29`).
   Why it costs: routers must depend on wiring/adapters, never on `main` (the composition root). Any second consumer of the SOP judge repeats the lazy-import hack, and moving/renaming `main` silently breaks a router. Hoist the factory into `pipeline/wiring.py` next to `build_judge`/`build_segmenter` and call it from both places.
4. **New gallery endpoint (and eval router) return untyped `dict`s — no contract at the boundary.**
   Proof: `backend/app/routers/synth.py:40` (`-> list[dict]`), `synth.py:84` (`-> dict`), `backend/app/routers/eval.py:38,69` — vs `response_model=` on inspect/profiles routes. The frontend parsers (`api.ts:474-506`) become the only validation.
   Why it costs: the one endpoint M6 invented (gallery, the documented divergence) is the one with no server-side shape; a typo in a key ships 200 + client `fail()` instead of a 500 at the source. Add Pydantic models for gallery items/generate response (and eval detail when touched).

## Consider

5. **Three divergent traversal/sanitization policies for one threat.**
   Proof: `backend/app/main.py:53-58` rejects `.`/`..`/absolute/backslash + resolve-containment; `backend/app/routers/eval.py:56-65` `_image_url` only checks `..` parts + absolute (backslash passes: `Path("a\\b").parts` is one segment on POSIX) after `lstrip("/")` normalization main.py never does; `backend/app/routers/inspect.py:137-142` does a third thing (char-substitution on filenames); `routers/synth.py:68-70` interpolates on-disk dir names into URLs with no check at all.
   Why it costs: four policies drift independently; the next path-handling edit will match the nearest example, not the strongest. One shared `safe_rel_path` helper used by all four sites.
6. **`_TimedSegmenter`/`_TimedJudge` manually duplicate the adapter interfaces.**
   Proof: `backend/app/routers/inspect.py:50-91` — full wrapper classes plus a `sop_to_profile` passthrough (`inspect.py:88-91`) that exists only because the wrapper must mirror `Judge`.
   Why it costs: every future `Judge`/`Segmenter` method needs a matching passthrough or the router breaks at runtime (`type: ignore[arg-type]` at `inspect.py:127-128` already hides the seam). Time at the call site (or a generic timing decorator) instead of interface-mirroring classes.
7. **Impure React updater + double-set refresh in Profiles.**
   Proof: `frontend/src/pages/Profiles.tsx:88-92` (`refreshList` sets list, returns nothing) then `handleRefresh` (`Profiles.tsx:197-210`) calls `setDraft` *inside* the `setProfiles` updater (`Profiles.tsx:201-205`) — updaters must be pure (StrictMode double-invokes them).
   Why it costs: today benign (idempotent set), but the pattern invites a non-idempotent side effect into a function React may run twice. Compute `stillThere` from the awaited `loaded` list instead.
8. **Gallery is an unbounded directory walk per request; grouping lives client-side.**
   Proof: server returns flat list (`routers/synth.py:48-80`), `frontend/src/pages/Synthetic.tsx:66-94` builds category→defect groups in-memory; no limit/pagination on either side.
   Why it costs: fine at current scale, but `data/synth/` grows monotonically with every generate call — first page load to degrade. Acceptable to defer; note the ceiling.

## Noted (checked, no action)

- **Choke point honored.** `fetch(` appears only in `api.ts:563,576,612,650`; all four pages import exclusively from `../api.ts`. Boundary parsers (`api.ts:279-498`) + typed errors (`api.ts:536-559`) cover every route. No bypass found.
- **Router↔CLI sharing is real reuse, not duplication.** Inspect reuses `run_inspection` + `build_*` wiring (`routers/inspect.py:124-130,40-47`); synth reuses M5 `generate_pairs` (`routers/synth.py:97-103`); PUT uses the shared atomic `save_profile` (`pipeline/inspect.py:51-81`). No logic forked between CLI and HTTP found (eval router parses `summary.json` inline, but there is no shared summary-loader to reuse — symmetric with the untyped-`dict` item above, not a new fork).
- **Gallery placement is correct.** `GET /api/synth/gallery` lives in the synth router next to `POST /api/synth/generate`, same `/files/synth/…` URL family — the divergence is a missing-list-endpoint gap (per context-pack), not a misplaced one.
- Minor: stale line-ref comment `frontend/src/api.ts:145` cites `routers/synth.py:63-77`; generate now sits at `synth.py:83-122`. Fix with item 4.
