"""Synth router: POST /api/synth/generate reusing M5 ``generate_pairs``.

Pinned contract (M6 check-1 appendix): sync JSON endpoint, body
``{profile_id, defect, n, seed=0}`` (names mirror ``generate_pairs`` in
``app/synth/generate.py``); generator via ``_get_image_generator()``
factory defaulting to ``FakeImageGenerator`` (mirrors the synth CLI
``--fake`` default-True), real adapter via monkeypatch only — never a
request param. Response ``{profile_id, defect, count, pairs:
[{image_url, mask_url|null}]}`` with ``/files/synth/{profile}/{defect}/``
URLs served from ``data/synth/`` (mask null when the diff/exact mask is
empty). Unknown profile → 404, ``n < 1`` → 422. Implemented in M6 Routers.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.adapters.base import ImageGenerator
from app.adapters.fakes import FakeImageGenerator
from app.config import settings
from app.synth.generate import generate_pairs

router = APIRouter()


def _get_image_generator() -> ImageGenerator:
    """Fake image generator; tests monkeypatch this for the real adapter."""
    return FakeImageGenerator()


class _GenerateBody(BaseModel):
    profile_id: str
    defect: str
    n: int
    seed: int = 0


@router.post("/api/synth/generate")
def generate_synth(body: _GenerateBody) -> dict:
    """Generate ``n`` synthetic pairs; files land under ``data/synth/``.

    Names mirror ``generate_pairs``; the generator comes from
    ``_get_image_generator`` (fake by default, real via monkeypatch
    only — never a request param). ``n < 1`` → 422, unknown
    profile → 404.
    """
    if body.n < 1:
        raise HTTPException(
            status_code=422, detail=f"--n must be >= 1, got {body.n}"
        )
    try:
        pairs = generate_pairs(
            body.profile_id,
            body.defect,
            body.n,
            generator=_get_image_generator(),
            seed=body.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    data_dir = Path(settings.data_dir)
    return {
        "profile_id": body.profile_id,
        "defect": body.defect,
        "count": len(pairs),
        "pairs": [
            {
                "image_url": f"/files/{image_path.relative_to(data_dir).as_posix()}",
                "mask_url": (
                    f"/files/{mask_path.relative_to(data_dir).as_posix()}"
                    if mask_path is not None
                    else None
                ),
            }
            for image_path, mask_path in pairs
        ],
    }
