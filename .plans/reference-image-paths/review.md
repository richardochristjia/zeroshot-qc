# Review: fix/reference-image-paths (correctness)

Basis: context-pack.md (cited), plan.md, risks.md. Run: backend `python -m pytest` 192 passed; frontend `npm test` 25 passed.

## Checks requested
- Import cycle `app.synth.generate` -> `app.pipeline.inspect`: none. `python -c "import app.synth.generate"` and `import app.pipeline.inspect` both succeed; `app/pipeline/*.py` does not import synth. Not a finding.
- Absolute / missing file: matches plan. Absolute passes through (inspect.py:116-120); missing relative raises `ValueError: could not open reference image mvtec/nope.png: ...` naming the original path (probe run). Synth falls back to the fixture when the resolved file is missing (generate.py:62-66), as planned. Pre-existing PUT 422 guard unchanged.
- Inspect empty-state split: correct. `refUrl` null (empty/null path) -> "No reference set"; otherwise `refFailedUrl === refUrl` (set by onError, Inspect.tsx:339) -> "Reference image not found: <path>". Verified by reading code only (criterion 5 is code review; no component test).
- `referenceImageUrl` + API_BASE: joins correctly (`${API_BASE}/files/<path>`); vitest passes.

## Findings

1. minor, frontend/src/api.ts:503 - path is not URL-encoded. A reference path containing `#`, `?` or `%` yields a wrong URL (`node`: `new URL("http://x/files/mvtec/a b/#c.png")` gives pathname `/files/mvtec/a%20b/`, hash `#c.png`). Proof: that command. Not hit by the 16 committed profiles (all `mvtec/<cat>/train/good/000.png`); user-entered paths in Profiles editor could hit it. Fix: `path.split('/').map(encodeURIComponent).join('/')`. Must-fix: no.
2. minor, frontend/src/pages/Inspect.tsx:211 - whitespace-only `referenceImage` is truthy, giving URL `/files/ ` and "not found" instead of "not set". Unproven (no run; reasoning from code). Must-fix: no.
3. minor (behavior change, already in risks.md), backend/profiles/*.json - profiles went null -> set, so any environment without the dataset under `data_dir` now raises `could not open reference image` in inspect (inspect.py:214-215) instead of running without a reference. Proof: probe above shows the ValueError for a missing file. Fix: deployment note, or make inspect tolerant. Must-fix: no (plan accepted it).

No critical or major findings. Must-fix: none.
