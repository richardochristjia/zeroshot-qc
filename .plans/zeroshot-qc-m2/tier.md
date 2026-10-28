# Tier

TIER: L
LOOP: phased
MODE: estimate
BASE: (file list)
FILES: 12
SOURCE: 12
LINES: (not measured)

## Signals
- why: 12 source files
- sensitive: none
- user-visible: backend/app/pipeline/measure.py, backend/app/pipeline/inspect.py, backend/app/pipeline/overlay.py
- tests: none
- changed source files without a test: backend/app/pipeline/measure.py, backend/app/pipeline/inspect.py, backend/app/pipeline/overlay.py, cli.py, backend/profiles/bottle.json, backend/profiles/screw.json, backend/profiles/metal_nut.json, backend/profiles/hazelnut.json, backend/profiles/carpet.json, backend/tests/test_measure.py, backend/tests/test_inspect.py, backend/scripts/smoke.py
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
