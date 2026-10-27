"""Synth router: POST /api/synth/generate reusing ``generate_pairs``.

Body ``{profile_id, defect, n, seed=0}``; generator via
``_get_image_generator()`` (fake by default, real via monkeypatch).
Response pairs carry ``/files/synth/...`` URLs (mask null when empty).
Unknown profile → 404, ``n < 1`` → 422.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.adapters.base import ImageGenerator
from app.adapters.fakes import FakeImageGenerator
from app.config import settings
from app.synth.generate import generate_pairs

router = APIRouter()

# No separators or dots: `..` traversal and absolute paths cannot spell
# a match, so the joined `root / profile_id / defect` path always stays
# under `data/synth/`.
_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")


def _get_image_generator() -> ImageGenerator:
    """Fake image generator; tests monkeypatch this for the real adapter."""
    return FakeImageGenerator()


class _GenerateBody(BaseModel):
    profile_id: str
    defect: str
    n: int
    seed: int = 0


@router.get("/api/synth/gallery")
def list_synth_gallery() -> list[dict]:
    """Enumerate ``data/synth/`` pairs as grouped gallery entries.

    Read-only: walks ``data/synth/<category>/<defect>/NNN.png`` files,
    skipping category-level ``_reference.png`` files, and pairs each
    image with an optional ``<stem>_mask.png`` sibling (``mask_url``
    null when absent). Missing or empty ``data/synth/`` returns ``[]``.
    """
    gallery: list[dict] = []
    synth_dir = Path(settings.data_dir) / "synth"
    if not synth_dir.is_dir():
        return gallery
    for category_dir in sorted(synth_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        for defect_dir in sorted(category_dir.iterdir()):
            if not defect_dir.is_dir():
                continue
            for image_path in sorted(defect_dir.glob("*.png")):
                if image_path.name.endswith("_mask.png"):
                    continue
                if image_path.name == "_reference.png":
                    continue
                mask_path = image_path.with_name(f"{image_path.stem}_mask.png")
                gallery.append(
                    {
                        "category": category_dir.name,
                        "defect": defect_dir.name,
                        "image_url": (
                            f"/files/synth/{category_dir.name}"
                            f"/{defect_dir.name}/{image_path.name}"
                        ),
                        "mask_url": (
                            f"/files/synth/{category_dir.name}"
                            f"/{defect_dir.name}/{mask_path.name}"
                            if mask_path.is_file()
                            else None
                        ),
                    }
                )
    return gallery


@router.post("/api/synth/generate")
def generate_synth(body: _GenerateBody) -> dict:
    """Generate ``n`` synthetic pairs; files land under ``data/synth/``.

    Names mirror ``generate_pairs``; the generator comes from
    ``_get_image_generator`` (fake by default, real via monkeypatch
    only — never a request param). ``n < 1`` → 422, unknown
    profile → 404. ``profile_id``/``defect`` outside
    ``[A-Za-z0-9_-]+`` → 422 before any file is written.
    """
    for field, value in (("profile_id", body.profile_id), ("defect", body.defect)):
        if not _NAME_RE.fullmatch(value):
            raise HTTPException(
                status_code=422, detail=f"invalid {field} {value!r}"
            )
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
