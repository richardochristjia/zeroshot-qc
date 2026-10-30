"""Disk cache for model calls, keyed by sha256 of the inputs.

Every model call is cached by a hash of its inputs (HANDOFF §2). Keys
are sha256 over length-prefixed components in a fixed order so
component boundaries can never collide: call kind, PNG image bytes,
then the call inputs, then the explicit model id. Callers pass the
model id in explicitly (from shared settings at wiring); nothing here
reads settings and no key or entry ever contains the API key.

Entries are one ``<key>.json`` file per call under the store root
(wiring passes ``Path(settings.data_dir) / "cache"``). They hold only
the result JSON (``model_dump`` output) and are rebuilt with
``model_validate`` on a hit. Adapter exceptions are never cached,
writes are atomic, and an unreadable or corrupt entry counts as a
miss.

``ImageGenerator`` result caching is deferred to M5: it returns a PIL
Image, which would need a binary entry format this phase does not
specify, and it is first exercised in M5.
"""

import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from app.adapters.base import Judge, Segmenter
from app.prompts import JUDGE_TEMPLATE
from app.schemas import Detection, ProductProfile, RawMask, Verdict

_NONE_MARKER = b"__none__"


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _frame(digest: Any, component: bytes) -> None:
    digest.update(len(component).to_bytes(8, "big"))
    digest.update(component)


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def segment_cache_key(
    image: Image.Image, prompts: list[str], model_id: str
) -> str:
    """Cache key for one segment call.

    Components in order: call kind, image PNG bytes, each prompt in
    list order, then the model id.
    """
    digest = hashlib.sha256()
    _frame(digest, b"segment")
    _frame(digest, _png_bytes(image))
    for prompt in prompts:
        _frame(digest, prompt.encode("utf-8"))
    _frame(digest, model_id.encode("utf-8"))
    return digest.hexdigest()


def judge_cache_key(
    image: Image.Image,
    overlay: Image.Image,
    reference: Image.Image | None,
    detections: list[Detection],
    profile: ProductProfile,
    model_id: str,
) -> str:
    """Cache key for one judge call.

    Components in order: call kind, judge prompt template bytes, image
    PNG bytes, overlay PNG bytes, reference PNG bytes (or a None
    marker), detections JSON, profile JSON, then the model id. Any
    profile/rules edit changes the profile JSON and so is a miss.
    """
    digest = hashlib.sha256()
    _frame(digest, b"judge")
    _frame(digest, JUDGE_TEMPLATE.read_bytes())
    _frame(digest, _png_bytes(image))
    _frame(digest, _png_bytes(overlay))
    if reference is None:
        _frame(digest, _NONE_MARKER)
    else:
        _frame(digest, _png_bytes(reference))
    _frame(digest, _canonical_json([d.model_dump() for d in detections]))
    _frame(digest, _canonical_json(profile.model_dump()))
    _frame(digest, model_id.encode("utf-8"))
    return digest.hexdigest()


class DiskCache:
    """One ``<sha256>.json`` file per entry under ``root``.

    The root directory is created on demand. ``get`` returns the
    parsed JSON payload, or ``None`` on a miss; an unreadable or
    corrupt entry also counts as a miss. ``put`` writes atomically
    (temp file in the same directory, then replace) and stores only
    the JSON payload it is given.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> Any | None:
        try:
            text = self._path_for(key).read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def put(self, key: str, payload: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self._path_for(key)
        fd, tmp_name = tempfile.mkstemp(
            dir=self.root, prefix=".tmp-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            os.replace(tmp_name, destination)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


class CachedSegmenter:
    """``Segmenter`` wrapper that serves repeat calls from a DiskCache.

    Takes the inner adapter, an explicit model id (from shared
    settings at wiring, never hardcoded here), and the cache store.
    On a hit the stored JSON is rebuilt with ``model_validate``
    without calling the inner adapter; on a miss the inner adapter is
    called once and its ``model_dump`` JSON is stored. Exceptions
    from the inner adapter propagate and are never cached.
    """

    def __init__(self, inner: Segmenter, model_id: str, cache: DiskCache) -> None:
        self._inner = inner
        self._model_id = model_id
        self._cache = cache

    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]:
        key = segment_cache_key(image, prompts, self._model_id)
        cached = self._cache.get(key)
        if cached is not None:
            try:
                return [RawMask.model_validate(entry) for entry in cached]
            except Exception:
                pass  # corrupt entry counts as a miss
        result = self._inner.segment(image, prompts)
        self._cache.put(key, [mask.model_dump() for mask in result])
        return result


class CachedJudge:
    """``Judge`` wrapper that serves repeat calls from a DiskCache.

    Same contract as ``CachedSegmenter``: explicit model id plus the
    cache store injected, hit rebuilds a ``Verdict`` without calling
    the inner adapter, miss calls it once and stores ``model_dump``
    JSON, and exceptions propagate uncached. ``sop_to_profile`` is
    delegated to the inner adapter uncached (SOP parsing lands M5).
    """

    def __init__(self, inner: Judge, model_id: str, cache: DiskCache) -> None:
        self._inner = inner
        self._model_id = model_id
        self._cache = cache

    def judge(
        self,
        image: Image.Image,
        overlay: Image.Image,
        reference: Image.Image | None,
        detections: list[Detection],
        profile: ProductProfile,
    ) -> Verdict:
        key = judge_cache_key(
            image, overlay, reference, detections, profile, self._model_id
        )
        cached = self._cache.get(key)
        if cached is not None:
            try:
                return Verdict.model_validate(cached)
            except Exception:
                pass  # corrupt entry counts as a miss
        result = self._inner.judge(image, overlay, reference, detections, profile)
        self._cache.put(key, result.model_dump())
        return result

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        return self._inner.sop_to_profile(sop_text, category_name)
