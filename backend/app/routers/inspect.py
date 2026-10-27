"""Inspect router: POST /api/inspect (multipart image + profile_id + rules).

Adapters come from ``_get_segmenter()`` / ``_get_judge()`` (real by
default, sharing one ``DiskCache``); tests monkeypatch the factories.
"""

import io
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app.adapters.base import Judge, Segmenter
from app.adapters.muse_spark import JudgeValidationError
from app.config import settings
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache
from app.pipeline.inspect import load_profile, run_inspection
from app.pipeline.overlay import make_overlay
from app.pipeline.wiring import build_judge, build_segmenter
from app.schemas import Detection, InspectionResult, ProductProfile, Verdict

router = APIRouter()


def _get_segmenter(
    cache: DiskCache | None = None,
) -> CachedSegmenter:
    """Real cached segmenter; tests monkeypatch this to ``build_*(True)``."""
    if cache is None:
        cache = DiskCache(Path(settings.data_dir) / "cache")
    return build_segmenter(False, cache)


def _get_judge(cache: DiskCache | None = None) -> CachedJudge:
    """Real cached judge; tests monkeypatch this to ``build_*(True)``."""
    if cache is None:
        cache = DiskCache(Path(settings.data_dir) / "cache")
    return build_judge(False, cache)


class _TimedSegmenter:
    """``Segmenter`` wrapper recording wall-ms of the last ``segment`` call."""

    def __init__(self, inner: Segmenter) -> None:
        self._inner = inner
        self.elapsed_ms = 0

    def segment(self, image: Image.Image, prompts: list[str]) -> list:
        start = time.perf_counter()
        try:
            return self._inner.segment(image, prompts)
        finally:
            self.elapsed_ms = int((time.perf_counter() - start) * 1000)


class _TimedJudge:
    """``Judge`` wrapper recording wall-ms of the last ``judge`` call."""

    def __init__(self, inner: Judge) -> None:
        self._inner = inner
        self.elapsed_ms = 0

    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        start = time.perf_counter()
        try:
            return self._inner.judge(
                image, overlay, reference, detections, profile
            )
        finally:
            self.elapsed_ms = int((time.perf_counter() - start) * 1000)

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        return self._inner.sop_to_profile(sop_text, category_name)


@router.post("/api/inspect", response_model=InspectionResult)
def inspect_image(
    image: UploadFile = File(...),
    profile_id: str = Form(...),
    rules: str | None = Form(None),
) -> InspectionResult:
    """Inspect an uploaded image against a profile.

    Multipart ``image`` bytes + ``profile_id`` + optional ``rules``
    (per-call override, profile untouched) → ``InspectionResult``
    with the overlay served under ``/files/...`` and ``timings_ms``.
    Unknown profile → 404; double judge failure → 422.
    """
    try:
        profile = load_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raw = image.file.read()
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            pil_image = opened.convert("RGB").copy()
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"could not decode image: {exc}"
        ) from exc
    cache = DiskCache(Path(settings.data_dir) / "cache")
    segmenter = _TimedSegmenter(_get_segmenter(cache))
    judge = _TimedJudge(_get_judge(cache))
    total_start = time.perf_counter()
    try:
        detections, verdict = run_inspection(
            pil_image,
            profile,
            segmenter,  # type: ignore[arg-type]
            judge=judge,  # type: ignore[arg-type]
            rules=(rules or None),
        )
    except JudgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    total_ms = int((time.perf_counter() - total_start) * 1000)
    inspection_id = uuid.uuid4().hex
    uploads_dir = Path(settings.data_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        c if (c.isalnum() or c in ("-", "_", ".")) else "_"
        for c in (image.filename or "upload")
    ).strip(".") or "upload"
    while ".." in safe_name:
        safe_name = safe_name.replace("..", "_")
    (uploads_dir / f"{inspection_id}_{safe_name}").write_bytes(raw)
    overlay = make_overlay(pil_image, detections)
    overlay_dir = Path(settings.data_dir) / "runs" / "inspect"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    overlay_name = f"{inspection_id}_overlay.png"
    overlay.save(overlay_dir / overlay_name, format="PNG")
    return InspectionResult(
        id=inspection_id,
        profile_id=profile.id,
        detections=detections,
        verdict=verdict,
        overlay_url=f"/files/runs/inspect/{overlay_name}",
        timings_ms={
            "segment": segmenter.elapsed_ms,
            "judge": judge.elapsed_ms,
            "total": total_ms,
        },
    )
