# Tier

TIER: L
LOOP: phased
MODE: estimate
BASE: (file list)
FILES: 16
SOURCE: 13
LINES: (not measured)

## Signals
- why: 13 source files
- sensitive: none
- user-visible: frontend/src/App.tsx, frontend/src/index.css, frontend/src/main.tsx, frontend/index.html, frontend/src/pages/Inspect.tsx, frontend/src/pages/Profiles.tsx, frontend/src/pages/Eval.tsx, frontend/src/pages/Synthetic.tsx, frontend/src/components/Button.tsx, frontend/src/components/Icon.tsx
- tests: frontend/src/theme.test.ts, frontend/src/geometry.test.ts, frontend/src/health.test.ts
- changed source files without a test: frontend/src/App.tsx, frontend/src/index.css, frontend/src/main.tsx, frontend/src/api.ts, frontend/index.html, frontend/src/pages/Inspect.tsx, frontend/src/pages/Profiles.tsx, frontend/src/pages/Eval.tsx, frontend/src/pages/Synthetic.tsx, frontend/src/components/Button.tsx, frontend/src/components/Icon.tsx, frontend/src/theme.ts, frontend/src/geometry.ts
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
