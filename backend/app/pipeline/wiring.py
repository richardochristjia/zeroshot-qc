"""Shared adapter wiring: one segmenter builder for every entry point.

Both entry points (repo-root ``cli.py`` and ``scripts/smoke.py``) build
their segmenter here so the cache root, the fake/real selection, and
the ``"fake-sam"`` cache id cannot drift apart and split or poison the
disk cache.
"""

from pathlib import Path

from app.adapters.fakes import FakeSegmenter
from app.adapters.sam import SamSegmenter
from app.config import settings
from app.pipeline.cache import CachedSegmenter, DiskCache


def build_segmenter(fake: bool, cache: DiskCache | None = None) -> CachedSegmenter:
    """Cached segmenter: deterministic fake (``"fake-sam"`` id) or real SAM.

    A caller-owned ``DiskCache`` may be passed in so sibling adapters
    (e.g. smoke's judge) share one store instance.
    """
    if cache is None:
        cache = DiskCache(Path(settings.data_dir) / "cache")
    if fake:
        return CachedSegmenter(FakeSegmenter(), "fake-sam", cache)
    return CachedSegmenter(SamSegmenter(), settings.sam_model_id, cache)
