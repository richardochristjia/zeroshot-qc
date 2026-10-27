"""Profiles router: GET list / GET one / PUT + POST from-sop.

``GET /api/profiles`` returns every valid profile sorted by id;
``GET /api/profiles/:id`` 404s on unknown ids (traversal-safe: the id
must match ``[A-Za-z0-9_-]+``); ``PUT /api/profiles/:id`` validates
the body as ``ProductProfile`` (FastAPI answers 422 before the
handler runs, so the file is untouched) and writes atomically via
``save_profile``. ``POST /api/profiles/from-sop`` drafts a profile
from SOP text and never saves anything.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.adapters.muse_spark import JudgeValidationError
from app.pipeline.inspect import PROFILES_DIR, load_profile, save_profile
from app.schemas import ProductProfile

router = APIRouter()


def _is_unsafe_reference(value: str) -> bool:
    """True when a profile ``reference_image`` could escape the repo.

    Absolute paths (posix or drive-letter) would let a PUT point the
    profile at any on-disk file, which ``load_good_image`` and the
    inspect path then read and forward to the external judge. ``..``
    segments and backslashes are rejected with the same guard the
    ``/files`` endpoint uses.
    """
    if value.startswith("/") or "\\" in value:
        return True
    if len(value) >= 2 and value[1] == ":":
        return True
    return any(seg in (".", "..") for seg in value.split("/"))


class SopDraftRequest(BaseModel):
    sop_text: str = Field(min_length=1)
    category_name: str = Field(min_length=1)


def _get_sop_judge():
    """Delegate to ``app.main`` (import kept local to avoid a cycle)."""
    from app.main import _get_sop_judge as factory

    return factory()


@router.get("/api/profiles", response_model=list[ProductProfile])
def list_profiles() -> list[ProductProfile]:
    """Return all valid profiles sorted by id; skip unreadable files."""
    profiles: list[ProductProfile] = []
    if PROFILES_DIR.is_dir():
        for path in sorted(PROFILES_DIR.glob("*.json")):
            try:
                profiles.append(load_profile(path.stem))
            except (ValueError, ValidationError):
                continue
    return profiles


@router.get("/api/profiles/{profile_id}", response_model=ProductProfile)
def get_profile(profile_id: str) -> ProductProfile:
    """Return one profile; 404 on unknown id or traversal attempt."""
    try:
        return load_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/api/profiles/{profile_id}", response_model=ProductProfile)
def put_profile(profile_id: str, body: ProductProfile) -> ProductProfile:
    """Validate ``body`` as ``ProductProfile`` and write it atomically.

    FastAPI rejects an invalid body with 422 before this runs, so the
    file stays untouched. A body id that disagrees with the path is
    422; an invalid path id is 404.
    """
    if body.id != profile_id:
        raise HTTPException(
            status_code=422,
            detail=f"body id {body.id!r} does not match path id {profile_id!r}",
        )
    if body.reference_image and _is_unsafe_reference(body.reference_image):
        raise HTTPException(
            status_code=422,
            detail="reference_image must be a relative path without '..' segments",
        )
    try:
        save_profile(body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return body


@router.post("/api/profiles/from-sop", response_model=ProductProfile)
def profiles_from_sop(body: SopDraftRequest) -> ProductProfile:
    """Draft a profile from an SOP paragraph (M5). Never saves anything.

    Two consecutive validation failures surface as 422, mirroring the
    judge's error shape.
    """
    try:
        return _get_sop_judge().sop_to_profile(body.sop_text, body.category_name)
    except JudgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
