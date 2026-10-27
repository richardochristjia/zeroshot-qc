# Tier

TIER: L
LOOP: phased
MODE: estimate
BASE: (file list)
FILES: 11
SOURCE: 11
LINES: (not measured)

## Signals
- why: 11 source files
- sensitive: none
- user-visible: backend/app/routers/inspect.py, backend/app/routers/profiles.py, backend/app/routers/eval.py, backend/app/routers/synth.py, backend/app/main.py, frontend/src/pages/Inspect.tsx, frontend/src/pages/Profiles.tsx, frontend/src/pages/Eval.tsx, frontend/src/pages/Synthetic.tsx
- tests: none
- changed source files without a test: backend/app/routers/inspect.py, backend/app/routers/profiles.py, backend/app/routers/eval.py, backend/app/routers/synth.py, backend/app/main.py, frontend/src/api.ts, frontend/src/pages/Inspect.tsx, frontend/src/pages/Profiles.tsx, frontend/src/pages/Eval.tsx, frontend/src/pages/Synthetic.tsx, backend/tests/test_routers.py
- substantial source files (10+ changed lines): none

## Steps
1. Build — sonnet
2. Context pack — sonnet
3. Review (four angles, blast radius) — sonnet
4. Falsify — sonnet
5. Fix, once — opus
6. Simplify and deslop — sonnet
7. Spec check — sonnet
8. Verify — sonnet
9. Push and merge-request link — sonnet
10. Browser walkthrough — sonnet
11. CI status — sonnet

## Skipped
- none
