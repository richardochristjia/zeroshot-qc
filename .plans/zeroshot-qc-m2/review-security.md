# Security review — feat/zeroshot-qc-m2

Scope per [context-pack.md](.plans/zeroshot-qc-m2/context-pack.md): M2 turns
`RawMask` lists into measured `Detection`s (`measure.py`, `inspect.py`,
`overlay.py`, repo-root `cli.py`, 5 profile JSONs, smoke rewrite). Reviewed
ONLY path handling, RLE decode of untrusted masks, CLI input handling, and
secret leakage. Every finding below has a proof run; base is `main`.

## Must-fix (2)

### M1 — `load_profile` path traversal: arbitrary file read outside `backend/profiles/`
- Where: `backend/app/pipeline/inspect.py:32`, `path = PROFILES_DIR / f"{name}.json"`
  with no sanitization; `name` comes straight from CLI `--profile`.
- Two escapes: (a) absolute name discards the base (`Path('/a') / '/b' ==
  Path('/b')`); (b) `..` segments walk out of the profiles dir.
- Proof (backend venv, real run):
  - `load_profile('/tmp/evil333')` → `ABSOLUTE-PATH LOAD OK: evil pwned`
  - `load_profile('../evil_trav')` → `TRAVERSAL LOAD OK: evil pwned`
  (both loaded attacker JSON from outside `PROFILES_DIR`).
- Impact: any local caller/script passing an untrusted `--profile` value reads
  and schema-validates an arbitrary local JSON file; combined with the
  error-path leak (C1) it also oracles file existence. Low privilege bar,
  trivial fix.
- Fix: strict allowlist, e.g. `if not re.fullmatch(r"[A-Za-z0-9_]+", name):
  raise ValueError(...)`, or `path.resolve()` + `is_relative_to(PROFILES_DIR)`
  guard. Add a test asserting `load_profile('../x')` and absolute paths raise.

### M2 — unbounded RLE decode: memory-exhaustion DoS before any size check
- Where: `decode_rle` (`measure.py:12`) calls `mask_api.decode(rle)` with
  attacker-influenced `size` (real-mode SAM API response, cache file on disk,
  or crafted `Detection.mask_rle`). `_decode_valid_masks` (`inspect.py:58`)
  and `make_overlay` (`overlay.py:24`) check shape only AFTER decoding.
- Proof (real run): `decode_rle({'size': [30000,30000], 'counts':
  'zzzzzzzzzzzz'})` → `DECODED shape (30000, 30000) secs 0.8` — a ~900 MB
  allocation with no complaint. Larger dims scale linearly to OOM-kill.
- Impact: one malicious mask kills the process (CLI, smoke, and any future
  server reusing this path).
- Fix: pre-validate `size` against the already-known image dims before
  decoding (both call sites know `(height, width)`), and/or cap total pixels
  in `decode_rle`. Add a test with mismatched-giant `size` asserting skip
  without a large allocation.

## Consider (2)

### C1 — error paths leak absolute repo path; directory profile breaks no-traceback contract
- The context pack's CLI contract is "exit 1 with `error:` on stderr (no
  traceback)". Two violations, both proven:
  - `python cli.py inspect ... --profile nope` → `error: unknown profile
    'nope': /Users/167560.KEVIN/orca/projects/Zeroshot QC/backend/profiles/nope.json
    does not exist` (absolute path disclosed; `inspect.py:36` interpolates `{path}`).
  - A directory at `backend/profiles/d.json` + `--profile d` → uncaught
    `IsADirectoryError` traceback (cli.py catches only `ValueError`;
    `read_text` raises `OSError`, proven via real CLI run).
- Fix: catch `OSError` in `load_profile` (map to `ValueError`) and drop `{path}`
  from the message (name only).

### C2 — profile numerics unvalidated: NaN / negative values accepted
- Proof: `ProductProfile.model_validate({... 'mm_per_px': nan, 'min_score':
  -1e308})` accepted → `nan -1e+308`. NaN poisons every derived size;
  negative `min_score` silently disables filtering. Local-file trust boundary,
  so integrity-only.
- Fix: `mm_per_px: float | None = Field(default=None, gt=0,
  allow_inf_nan=False)`, `min_score: float = Field(default=0.3, ge=0, le=1)`.

## Noted — verified safe (5, each with proof)

1. Malformed RLE never crashes: 8-case battery (`garbage!!!` counts, empty,
   zero/negative/short/non-list/missing `size`, `{}`) raised only catchable
   `ValueError`/`OverflowError`/`IndexError`/`TypeError`/`KeyError`
   ("SURVIVED"); all three call sites wrap decode in `try/except` +
   warn-and-skip.
2. No secrets in M2 diff: grep over the Group 1+2+3 diff for
   `api.?key|secret|token|password|model.?id|endpoint|http|sk-|AKIA` hit only
   `settings.sam_model_id` (env-backed config reference, `cli.py:36`), no
   hardcoded IDs/keys/endpoints.
3. Corrupt image input fails clean: garbage `/tmp/bad.png` → `error: could not
   open image ...` exit 1, no traceback; PIL bomb guard active
   (`MAX_IMAGE_PIXELS = 89478485`), and `DecompressionBombError` falls under
   cli.py's `except Exception`.
4. Overlay output path cannot traverse: filename is built from
   `image_path.stem` (`cli.py:79`); proven `Path('/tmp/../../etc/passwd').stem
   == 'passwd'`. Overwrite of an existing overlay is silent but local-only.
5. Bad profile JSON fails clean: `JSONDecodeError` and pydantic
   `ValidationError` both subclass `ValueError` (proven via `issubclass`),
   so both hit cli.py's `except ValueError` → clean `error:` exit 1.
