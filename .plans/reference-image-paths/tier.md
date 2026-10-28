# Tier

TIER: M
LOOP: micro
MODE: estimate
BASE: (file list)
FILES: 8
SOURCE: 7
LINES: (not measured)

## Signals
- why: 7 source files, no sensitive path
- sensitive: none
- user-visible: backend/app/pipeline/inspect.py, backend/app/synth/generate.py, frontend/src/pages/Inspect.tsx, frontend/src/pages/Profiles.tsx
- tests: frontend/src/url-join.test.ts
- changed source files without a test: backend/app/pipeline/inspect.py, backend/app/synth/generate.py, frontend/src/api.ts, frontend/src/pages/Inspect.tsx, frontend/src/pages/Profiles.tsx, backend/profiles/bottle.json, backend/tests/test_judge.py
- substantial source files (10+ changed lines): none

## Steps
1. Build — sonnet
2. Context pack — sonnet
3. Correctness review (one angle) — sonnet
4. Falsify — sonnet
5. Fix, once — opus
6. Verify — sonnet
7. Push and merge-request link — sonnet
8. CI status — sonnet

## Skipped
- four-angle interrogate
- blast radius
- browser walkthrough
- simplify
- spec check
