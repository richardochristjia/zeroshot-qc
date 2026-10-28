# Tier

TIER: M
LOOP: micro
MODE: estimate
BASE: (file list)
FILES: 5
SOURCE: 4
LINES: (not measured)

## Signals
- why: 4 source files, no sensitive path
- sensitive: none
- user-visible: frontend/src/pages/Eval.tsx, frontend/src/components/ConfusionMatrix.tsx, frontend/src/components/FailureGrid.tsx
- tests: frontend/src/eval-view.test.ts
- changed source files without a test: frontend/src/pages/Eval.tsx, frontend/src/components/ConfusionMatrix.tsx, frontend/src/components/FailureGrid.tsx, frontend/src/eval-view.ts
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
