"""GET /api/samples: bundled demo samples for the Inspect page."""

from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.demo import load_samples

router = APIRouter()


@router.get("/api/samples")
def list_samples() -> list[dict]:
    return [
        {
            "id": e["id"],
            "label": e["label"],
            "profile_id": e["profile_id"],
            "image_url": "/files/" + e["file"],
        }
        for e in load_samples(Path(settings.data_dir))
    ]
