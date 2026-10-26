# Tier

TIER: L
LOOP: phased
MODE: estimate
BASE: (file list)
FILES: 14
SOURCE: 14
LINES: (not measured)

## Signals
- why: 14 source files
- sensitive: none
- user-visible: backend/app/main.py, backend/app/config.py, backend/app/schemas.py, backend/app/adapters/base.py, backend/app/adapters/sam.py, backend/app/adapters/muse_spark.py, backend/app/adapters/muse_image.py, backend/app/adapters/fakes.py, backend/app/pipeline/cache.py, backend/app/routers/inspect.py
- tests: none
- changed source files without a test: backend/app/main.py, backend/app/config.py, backend/app/schemas.py, backend/app/adapters/base.py, backend/app/adapters/sam.py, backend/app/adapters/muse_spark.py, backend/app/adapters/muse_image.py, backend/app/adapters/fakes.py, backend/app/pipeline/cache.py, backend/app/routers/inspect.py, backend/scripts/smoke.py, backend/tests/test_adapters.py, backend/tests/test_cache.py, backend/tests/test_health.py
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
