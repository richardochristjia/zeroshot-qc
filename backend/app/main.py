"""FastAPI application entry point. Health endpoint lives here in M1."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.adapters.muse_spark import MuseSparkJudge
from app.config import settings
from app.routers.eval import router as eval_router
from app.routers.inspect import router as inspect_router
from app.routers.profiles import router as profiles_router
from app.routers.synth import router as synth_router

app = FastAPI()

app.include_router(profiles_router)
app.include_router(inspect_router)
app.include_router(eval_router)
app.include_router(synth_router)


def _get_sop_judge() -> MuseSparkJudge:
    """Indirection so tests can substitute a fake without touching HTTP.

    The profiles router calls this factory lazily at request time, so
    patching ``app.main._get_sop_judge`` still substitutes the judge.
    """
    return MuseSparkJudge()

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/files/{rel_path:path}")
def serve_data_file(rel_path: str) -> FileResponse:
    """Serve a file from ``data/``; traversal attempts are 404.

    The data dir resolves per request (tests monkeypatch
    ``settings.data_dir``), so a ``StaticFiles`` mount fixed at import
    time would serve a stale directory. Explicit guard first: any
    ``.``/``..`` segment, absolute path, or backslash is rejected
    before touching the filesystem. A ``resolve()`` + containment
    backstop then covers encoded variants and symlinks.
    """
    if (
        not rel_path
        or rel_path.startswith("/")
        or "\\" in rel_path
        or any(seg in (".", "..") for seg in rel_path.split("/"))
    ):
        raise HTTPException(status_code=404, detail="not found")
    data_dir = Path(settings.data_dir).resolve()
    candidate = (data_dir / rel_path).resolve()
    if candidate != data_dir and data_dir not in candidate.parents:
        raise HTTPException(status_code=404, detail="not found")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(candidate)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "models": {
            "sam": settings.sam_model_id,
            "judge": settings.judge_model_id,
            "image": settings.image_model_id,
        },
    }
