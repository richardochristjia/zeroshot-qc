# Tier

TIER: L
LOOP: phased
MODE: estimate
BASE: (file list)
FILES: 8
SOURCE: 7
LINES: (not measured)

## Signals
- why: touches Dockerfile
- sensitive: Dockerfile
- user-visible: backend/app/main.py
- tests: none
- changed source files without a test: Dockerfile, .dockerignore, modal_app.py, vercel.json, frontend/src/api.ts, frontend/vite.config.ts, backend/app/main.py
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
