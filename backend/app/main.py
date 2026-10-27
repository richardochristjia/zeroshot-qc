"""FastAPI application entry point. Health endpoint lives here in M1."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge
from app.config import settings
from app.schemas import ProductProfile

app = FastAPI()


class SopDraftRequest(BaseModel):
    sop_text: str = Field(min_length=1)
    category_name: str = Field(min_length=1)


def _get_sop_judge() -> MuseSparkJudge:
    """Indirection so tests can substitute a fake without touching HTTP."""
    return MuseSparkJudge()

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/profiles/from-sop", response_model=ProductProfile)
def profiles_from_sop(body: SopDraftRequest) -> ProductProfile:
    """Draft a profile from an SOP paragraph (M5). Never saves anything.

    Two consecutive validation failures surface as 422, mirroring the
    judge's error shape.
    """
    try:
        return _get_sop_judge().sop_to_profile(body.sop_text, body.category_name)
    except JudgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
