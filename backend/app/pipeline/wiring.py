"""Shared adapter wiring: one segmenter and one judge builder per entry point.

Every entry point (repo-root ``cli.py``, ``scripts/smoke.py``) builds
its adapters here so the cache root, the fake/real selection, and the
``"fake-sam"`` / ``"fake-judge"`` cache ids cannot drift apart and
split or poison the disk cache.
"""

from pathlib import Path

from app.adapters.fakes import FakeJudge, FakeSegmenter
from app.adapters.muse_spark import MuseSparkJudge
from app.adapters.sam import SamSegmenter
from app.config import settings
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache


def build_segmenter(fake: bool, cache: DiskCache | None = None) -> CachedSegmenter:
    """Cached segmenter: deterministic fake (``"fake-sam"`` id) or real SAM.

    A caller-owned ``DiskCache`` may be passed in so sibling adapters
    (e.g. the judge) share one store instance.
    """
    if cache is None:
        cache = DiskCache(Path(settings.data_dir) / "cache")
    if fake:
        return CachedSegmenter(FakeSegmenter(), "fake-sam", cache)
    return CachedSegmenter(SamSegmenter(), settings.sam_model_id, cache)


def build_judge(fake: bool, cache: DiskCache | None = None) -> CachedJudge:
    """Cached judge: deterministic fake (``"fake-judge"`` id) or Muse Spark.

    Shares the caller's ``DiskCache`` when given so one inspection
    reuses a single store for both segment and judge entries.
    """
    if cache is None:
        cache = DiskCache(Path(settings.data_dir) / "cache")
    if fake:
        return CachedJudge(FakeJudge(), "fake-judge", cache)
    return CachedJudge(MuseSparkJudge(), settings.judge_model_id, cache)
