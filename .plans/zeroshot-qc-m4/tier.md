# Tier

TIER: M
LOOP: micro
MODE: estimate
BASE: (file list)
FILES: 7
SOURCE: 6
LINES: (not measured)

## Signals
- why: 6 source files, no sensitive path
- sensitive: none
- user-visible: backend/app/eval/dataset.py, backend/app/eval/run.py, backend/app/eval/metrics.py
- tests: none
- changed source files without a test: backend/app/eval/dataset.py, backend/app/eval/run.py, backend/app/eval/metrics.py, backend/tests/test_eval_metrics.py, backend/tests/test_eval_run.py, backend/tests/fixtures/mvtec/fixture.py
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
