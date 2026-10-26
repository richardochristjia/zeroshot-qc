"""FastAPI application entry point. Health endpoint lives here in M1."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI()

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
