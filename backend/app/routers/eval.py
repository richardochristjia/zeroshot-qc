"""Eval router: run list + run detail (read-only, never launches runs).

``GET /api/eval/runs`` returns the ``summary.json`` of every run
directory under ``data/runs/``, skipping entries without one (flat
overlay PNGs and helper dirs such as ``runs/inspect/`` hold no
summary). ``GET /api/eval/runs/{run_id}`` returns
``{"summary": ..., "results": [...]}``; unknown ids (including
traversal attempts outside ``[A-Za-z0-9_-]+``) are 404.

Pre-M6 ``summary.json`` files lack the ``source`` key current
``app/eval/run.py`` writes, so detail defaults it to ``"mvtec"``.
``results.jsonl`` rows carry no stored overlays — only a
dataset-relative ``image`` path — so detail builds
``image_url`` (``/files/<source>/<image>``) from each record path;
absolute or escaping paths get ``image_url`` null instead of a URL.
"""

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()

# Same guard as profile names: no separators or dots, so `..`
# traversal cannot spell a match and the join stays under runs/.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def _runs_dir() -> Path:
    return Path(settings.data_dir) / "runs"


@router.get("/api/eval/runs")
def list_runs() -> list[dict]:
    """Return every run summary; skip entries lacking ``summary.json``."""
    runs: list[dict] = []
    runs_dir = _runs_dir()
    if runs_dir.is_dir():
        for child in sorted(runs_dir.iterdir()):
            if not child.is_dir():
                continue
            summary_path = child / "summary.json"
            if not summary_path.is_file():
                continue
            try:
                runs.append(json.loads(summary_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
    return runs


def _image_url(source: str, image: object) -> str | None:
    """Build ``/files/<source>/<image>`` for a dataset-relative record path."""
    if not isinstance(image, str) or not image:
        return None
    rel = image.lstrip("/")
    if rel in ("", ".") or ".." in Path(rel).parts:
        return None
    if Path(image).is_absolute():
        return None
    return f"/files/{source}/{rel}"


@router.get("/api/eval/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    """Return ``{"summary": ..., "results": [...]}`` for one run; 404 if missing."""
    if not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    run_dir = _runs_dir() / run_id
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=404, detail=f"unknown run {run_id!r}: {exc}"
        ) from exc
    if not isinstance(summary, dict):
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    summary.setdefault("source", "mvtec")
    source = summary["source"] if isinstance(summary.get("source"), str) else "mvtec"
    results: list[dict] = []
    results_path = run_dir / "results.jsonl"
    if results_path.is_file():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            record["image_url"] = _image_url(source, record.get("image"))
            results.append(record)
    return {"summary": summary, "results": results}
