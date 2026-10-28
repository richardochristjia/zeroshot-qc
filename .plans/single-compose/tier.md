# Tier

TIER: L
LOOP: phased
MODE: estimate
BASE: (file list)
FILES: 4
SOURCE: 3
LINES: (not measured)

## Signals
- why: touches docker-compose.yml
- sensitive: docker-compose.yml, frontend/Dockerfile
- user-visible: none
- tests: none
- changed source files without a test: docker-compose.yml, frontend/Dockerfile, frontend/nginx.conf
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
