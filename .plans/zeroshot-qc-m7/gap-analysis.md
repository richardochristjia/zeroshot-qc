# Gap analysis — M7 (Deploy-ready + polish) vs `feat/zeroshot-qc-m7`

Branch: `feat/zeroshot-qc-m7` (HEAD `670083c`) vs `main`. Date: 2026-10-27.
Method: read `plan.md` + `tasks.md` + `check-*.md` + `falsify.md`, read the full
diff, and re-ran every automated proof live (container probes, prod bundle,
`pytest`, `tsc` + `vite build`, `vitest`).

## Acceptance-criteria table

| ID | Criterion | Met? | Evidence |
|---|---|---|---|
| AC1 | `docker build` succeeds; container passes health, fake inspect with fetchable overlay, `/files` fetch | Yes | Image `zeroshot-qc` 570MB exists; live re-probe this run: `/api/health` → `{"status":"ok","models":{...}}`; fake inspect (profile `screw`) → detections + `mask_rle.size [8,8]`; overlay fetch → 200; `/files/../outside.txt` → 404; unknown profile → 404; CORS `Origin` echoed (`access-control-allow-origin: http://localhost:5173`) |
| AC2 | Production frontend build succeeds with no secret patterns in bundle | Yes | `VITE_API_URL=http://localhost:8000 npm run build` clean (28 modules, `tsc` exit 0); bundle contains the baked API URL; grep for `sk-`/`Bearer`/key patterns over fresh `frontend/dist/` → zero hits; `Dockerfile` has no `COPY .env` |
| AC3 | `pytest` green; no app-code behavior changes (config/wiring only) | Yes | `cd backend && .venv/bin/python -m pytest -q` → 171 passed; the one app-code touch (`USE_FAKE_ADAPTERS`, default `False`) keeps the real path byte-identical — declared divergence in `plan.md`, tested by `test_fake_flag.py` + `test_modal_app.py` |
| AC4 | README takes a stranger from clone to local run to public-URL push | Yes | `README.md` covers prerequisites, setup, local run, Docker run, push commands, checklist state; the exact `docker build`/`run` + probe commands from the README were re-run verbatim in this check and pass; `probe.png` creation one-liner present |
| AC5 | `manual:` user runs Modal/Vercel push, confirms public URL privately | Can't tell | Human step by plan design; correctly left unchecked in `tasks.md`; `modal`/`vercel` CLIs not installed here. Settles when the user runs the documented commands |
| F1 | Modal wrapper deployable without credentials in-run | Yes | `modal_app.py`: module-scope `modal.App`, image pins `backend/requirements.txt`, guarded import; proven by 4 stub-`modal` tests in `backend/tests/test_modal_app.py` (3 fail on pre-fix code) |
| F2 | `VITE_API_URL` wiring with dev-proxy fallback + slash normalization | Yes | `frontend/src/api.ts` (`normalizeApiBase`, `resolveFileUrl`, applied at all fetch + img-src sites); 7 `vitest` tests pass |
| F3 | Polish sweep: carry triage, gallery decision, README, checklist | Yes | 13 carry items with owners in `docs/HANDOFF.md`; synth `n_defective` note in `docs/EVAL_NOTES.md`; gallery entry APPROVED + written; submission checklist recorded in README |

## Record reconciliation (`.agents/RECORD.md`)

- Both promised `(deploy)` entries are present verbatim and match the build
  (slim 3.11/uvicorn container; static frontend via build-time API URL).
- Gallery decision from polish is reflected: `(synth)` gallery entry present
  (line 64), verified live (200, 11 grouped entries per Phase 3).
- No other existing entry was changed, broken, or made stale by this work.
- No new high-level fact needs an entry.

## Gaps

None. All 8 fix + 1 narrow rulings from `falsify.md` were already implemented
in `612dc24` and verified green; no new automated gap was found, so no fix
commit was needed.

## Next

- User runs the AC5 manual push (`modal deploy`, `vercel --prod`) and confirms
  the public URL in a private window.
- Carry list owners in `docs/HANDOFF.md` as future work.
