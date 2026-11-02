"""Tune router: read-only list and detail of ``<data_dir>/tune/*/tune.json``."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()

# Same guard as routers/eval.py: no separators or dots.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def _tune_dir() -> Path:
    return Path(settings.data_dir) / "tune"


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


@router.get("/api/tune/runs")
def list_runs() -> list[dict]:
    runs: list[dict] = []
    if _tune_dir().is_dir():
        for child in sorted(_tune_dir().iterdir()):
            record = _read(child / "tune.json") if child.is_dir() else None
            if record is None:
                continue
            try:
                heldout = record["heldout"]
                runs.append(
                    {
                        "run_id": record["run_id"],
                        "category": record["category"],
                        "adapter": record["adapter"],
                        "before_f1": heldout["before"]["f1"],
                        "after_f1": heldout["after"]["f1"],
                        "rounds_accepted": sum(
                            1 for r in record["rounds"] if r["accepted"]
                        ),
                    }
                )
            except (KeyError, TypeError):
                continue
    return runs


@router.get("/api/tune/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    record = (
        _read(_tune_dir() / run_id / "tune.json")
        if _RUN_ID_RE.fullmatch(run_id)
        else None
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    return record
