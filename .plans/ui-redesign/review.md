# Review: feat/ui-redesign vs origin/main

Basis: .plans/ui-redesign/context-pack.md (read first), spec .plans/ui-redesign/plan.md.
Mode: interrogate run by a single reviewer reading the pack plus targeted files (four-agent fan-out not spawned: unattended subagent, cost). Angles covered inline: correctness, security, structure, tests.

## Proof runs
- frontend: `npm run build` ok (Fira woff2 emitted to dist/assets), `npm run lint` clean, `npm test` 4 files / 16 tests pass.
- grep for raw palette classes (bg|text|border|ring|from|to)-(neutral|gray|red|green|amber|slate|zinc|blue|emerald|yellow|rose)-N in src: 0 hits.
- fake backend (USE_FAKE_ADAPTERS=true uvicorn :8000) GET /api/eval/runs: 9 runs, all with n_good 10 / n_defective 20; stopped afterwards.

## Act on
(none)

## Consider
1. Eval ablation `groupKey` (Eval.tsx:29) keys on source+seed+sorted categories only, but the panel is titled "same N images" (Eval.tsx ~ PanelHeader). nGood/nDefective are not in the key, and the loop keeps the first run per mode. Two runs with identical source/seed/categories but different N would be mixed into one ablation. Proof: reading groupKey vs EvalRunSummary (api.ts:116-127, has nGood/nDefective); today's 9 runs from the fake backend all have 10/20, so it is latent. Fix is one extra array element in groupKey.
2. Inspect pickFile (Inspect.tsx ~L113) does not abort an in-flight inspect or clear a pending rules debounce; a slow response for the old file can set `result` over the new file's preview, and a pending 500ms timer re-judges the new file with old rules. Same as origin/main (its pickFile also did not abort), so not a regression. Proof: code reading; the abort/debounce effect depends only on [rulesText].

## Noted
- Debounce/abort re-judge contract preserved: runInspect aborts previous controller, AbortError returns without touching state, effect cleanup aborts and clears timer, empty rules map to undefined (Inspect.tsx:112-200); structure identical to main.
- Motion keyed on `result.id` (Inspect.tsx:400): id is a fresh uuid per backend response (routers/inspect.py:125) and aborted requests never reach setResult, so aborted requests cannot replay the animation. A successful re-judge does replay the verdict fade by design.
- Theme: pre-paint inline script in index.html head is wrapped in try/catch; theme.ts read/write both try/catch; theme.test.ts covers resolveTheme. System mode uses `:root:not([data-theme="light"])` media guard.
- getHealth (api.ts:717) returns "ok"/"down" and only rethrows AbortError; HealthDot swallows the rejection. Covered by health.test.ts.
- Reduced motion: MotionGlobalConfig.skipAnimations set before render plus a change listener (main.tsx); MotionConfig reducedMotion="user" present.
- Profiles save/SOP/overwrite: overwrite warning and armed confirm retained and only re-wrapped in motion; dirty tracking added. Not exercised in a browser here (no page tests exist).
- Reference image URL: Inspect.tsx:211 / Profiles.tsx:375 call resolveFileUrl on the raw path; all profiles have reference_image null, pre-existing contract per context pack, not introduced here.
- No test coverage for pages/components (pack states browser-verified only).
- Security: no dangerouslySetInnerHTML/innerHTML, no new network calls beyond /api/health, fonts self-hosted (no googleapis/gstatic in src).

## Dismissed
- "reducedMotion=user alone suffices": dismissed, the pack and main.tsx explain it leaves opacity fades; skipAnimations covers it.
- Backend/contract changes: none in diff, nothing to review.

## Blast radius
Act on: (none proven broken)

Proof (real run): `cd frontend && VITE_API_URL=http://example.test npm run build` ok.
- Health URL: dist js has `Rm=Lm("http://example.test")` and `Um("/api/health",e)`, joined by apiUrl as `${base}/api/health` (same path as every other call, so getHealth honors VITE_API_URL like the rest of api.ts).
- Fonts: 33 font files emitted; CSS uses root-absolute `url(/assets/fira-*.woff2)`; served from dist with a static server: `/assets/fira-sans-latin-400-*.woff2` 200 font/woff2, `/favicon.svg` 200 image/svg+xml. No googleapis/gstatic in dist. Matches feat/single-compose nginx.conf (root + try_files, base "/"), so same-origin fonts work. Not run under real nginx (not installed).
- Backend: grep of backend tests, Dockerfile, cli.py, modal_app.py for frontend/dist references: none. vercel.json builds `cd frontend && npm ci && npm run build` (same script, still passes).
- CSP: no CSP header or meta anywhere on this branch, in backend (only CORSMiddleware, main.py:30) or on feat/single-compose nginx.conf. The inline pre-paint script in index.html is therefore not blocked today.

Consider (latent, not broken):
- If a CSP with `script-src 'self'` is ever added to nginx/Vercel, the inline script in index.html:8 is blocked: the theme falls back to the CSS media query (dark OS users with saved "light" would flash/ignore). Needs a hash/nonce then. Likelihood low, no CSP exists.
- Cross-origin deploy: /api/health from another origin relies on backend CORS allow_origins (pre-existing setting); HealthDot would show "down" if the origin is not allowed, same as every other call.
