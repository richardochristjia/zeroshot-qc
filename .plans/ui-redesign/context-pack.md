# Context pack

BASE: origin/main (branch feat/ui-redesign)
CHANGED: 28 files, +1576/-743 (excl. lockfile noise: package-lock.json +87)

## What this change does
Frontend-only UI redesign: design-token CSS + light/dark/system theme switch, shared components, rebuilt Inspect/Profiles/Eval/Synthetic pages, Motion animations, self-hosted Fira fonts. Backend untouched. Spec: `.plans/ui-redesign/plan.md`.

## Files
- `frontend/src/index.css` — tokens, dark theme, fonts
- `frontend/src/theme.ts` (+`theme.test.ts`) — theme state/persistence
- `frontend/src/geometry.ts` (+`geometry.test.ts`) — box/overlay math for Inspect
- `frontend/src/main.tsx` — MotionConfig, `MotionGlobalConfig.skipAnimations` on prefers-reduced-motion
- `frontend/src/App.tsx` — shell, tabs, route fade, HealthDot, ThemeSwitch
- `frontend/src/api.ts:716` — new `getHealth()`; only API change
- `frontend/src/health.test.ts` — covers getHealth
- `frontend/src/components/*` — Alert, Button, EmptyState, Field, HealthDot, Icon, PageHeader, Panel, ThemeSwitch, VerdictBadge
- `frontend/src/pages/{Inspect,Profiles,Eval,Synthetic}.tsx` — rebuilt pages
- `frontend/index.html`, `public/favicon.svg`, `package.json`(+motion, fontsource), `docs/design-system.md`

## API contracts (frontend/src/api.ts -> backend)
- `listProfiles` GET /api/profiles, `getProfile` GET /api/profiles/{id}, `putProfile` PUT /api/profiles/{id}, `draftProfileFromSop` POST /api/profiles/from-sop (backend/app/routers/profiles.py). `ProductProfile` api.ts:54 (`referenceImage` api.ts:61, mapped from `reference_image` at :342, sent at :655).
- `inspectImage` POST /api/inspect (routers/inspect.py; overlay_url = `/files/runs/inspect/<name>`, :145). `InspectionResult` api.ts:70.
- `listEvalRuns` GET /api/eval/runs, `getEvalRun` GET /api/eval/runs/{id} (routers/eval.py; image urls `/files/<source>/<rel>`, :56).
- `listSyntheticGallery` GET /api/synth/... (routers/synth.py; `/files/synth/<cat>/<defect>/NNN.png`).
- `getHealth` GET /api/health -> `{status:"ok"}` (backend/app/main.py:~58).
- Files: `GET /files/{rel_path}` (main.py:38) serves `settings.data_dir` (= `data/`), 404 on traversal/non-file. `resolveFileUrl` (api.ts:489) passes blob:/data:/http(s) through, else `apiUrl(url)`.

### Reference image URL (known issue)
- Every `backend/profiles/*.json` (15 incl. untracked bottle-sop-test) has `"reference_image": null`, so no real value exists today.
- Schema: `reference_image: str|None` "path to a known-good image" (schemas.py:33); PUT rejects absolute/`..` paths (profiles.py:85). Backend loads it via `_load_reference_image` (pipeline/inspect.py:115,207) relative to backend cwd; synth/generate.py:62 also resolves it.
- Frontend: Inspect.tsx:211 and Profiles.tsx:375 call `resolveFileUrl(profile.referenceImage)` with no `/files/` prefix. A value like `data/mvtec/bottle/train/good/000.png` becomes `<api>/data/mvtec/...` -> 404 (backend only serves `/files/...`, relative to data/). A value `mvtec/...` that works for `/files/` would not load in the backend (cwd-relative). No single value satisfies both. Pre-existing contract.

## Test entry points
- `cd frontend && npm run build && npm run lint && npm test` (tsc -b && vite build; oxlint; vitest run)
- Tests: `src/{geometry,health,theme,url-join}.test.ts`. Pages/components have no tests (browser-verified via taste gate only).

## Acceptance criteria (plan.md:288-308)
1. build, lint, test pass in frontend/.
2. Taste inspector --app 0 FAIL on /, /profiles, /eval, /synthetic at 1440/768/390, light+dark; WARNs in taste/allow.md.
3. No raw tailwind palette classes (bg|text|border-(neutral|gray|red|green|amber|slate)-N) in pages, App.tsx, components.
4. One h1 per route.
5. All flows work vs fake backend (inspect, re-judge rules, clear rules, save, draft SOP, eval run + failure, synthetic masks); no h-scroll at 390.
6. Theme persists across reload, overrides OS, System follows OS, no flash.
7. Reduced motion: nothing animates; MotionConfig reducedMotion="user" present.
8. dist has Fira .woff2; no googleapis/gstatic requests.
9. Inspect Reference/Under-test side by side, 12px gap at >=1001px; no-reference frame; hover/focus box<->ruling.
- manual: real SAM/Muse keys, inspect real MVTec image, boxes on defects (outside automated verification).
- manual: `docker compose up --build`, fonts from same origin, theme switch behind nginx.

## Do not re-derive
- Backend not changed; `/files/` contract and null reference images pre-exist.
- Only api.ts change is `getHealth` (never throws except AbortError).
- Reduced motion needs `MotionGlobalConfig.skipAnimations` (main.tsx) because reducedMotion="user" leaves opacity fades.
- Most page behaviour was verified by build only; see risks.md.

## Diff
Not inlined (1.5k lines exceeds budget). Get it with:
`git diff origin/main...HEAD -- . ':!frontend/package-lock.json'`
Groups: components/ (new, ~220 lines), pages/ (bulk), index.css/main.tsx/App.tsx/api.ts/theme*/geometry* (small).
