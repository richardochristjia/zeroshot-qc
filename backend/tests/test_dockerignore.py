"""The root .dockerignore is an allowlist of the backend's runtime paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = [
    line.strip()
    for line in (ROOT / ".dockerignore").read_text().splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
ALLOWED = [r[1:].rstrip("/") for r in RULES if r.startswith("!")]


def test_first_rule_excludes_everything():
    assert RULES[0] == "*"


def test_reincluded_paths_are_exactly_the_runtime_set():
    assert sorted(ALLOWED) == [
        "backend/app",
        "backend/demo",
        "backend/profiles",
        "backend/requirements.txt",
    ]


def test_no_reinclude_leaks_data_or_secrets():
    for bad in ("data", ".env", "tests", ".venv", "scripts"):
        assert not any(bad in r for r in ALLOWED), bad


def test_reincluded_paths_exist():
    for p in ALLOWED:
        assert (ROOT / p).exists(), p
