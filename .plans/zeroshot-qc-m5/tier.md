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
- user-visible: backend/app/synth/generate.py, backend/app/adapters/muse_image.py, backend/app/adapters/muse_spark.py, backend/app/prompts/sop_to_profile.md, backend/app/main.py, backend/app/eval/dataset.py
- tests: none
- changed source files without a test: backend/app/synth/generate.py, backend/app/adapters/muse_image.py, backend/app/adapters/muse_spark.py, backend/app/main.py, backend/app/eval/dataset.py, backend/tests/test_synth.py, backend/tests/test_sop.py
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
