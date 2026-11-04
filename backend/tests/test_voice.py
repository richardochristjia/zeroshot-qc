"""POST /api/voice/transcribe: fake, keyless and non-WAV paths, plus the adapter request."""

import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import app.adapters.muse_voice as muse_voice
import app.routers.voice as voice
from app.config import settings
from app.main import app

client = TestClient(app)
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 20


def _post(data: bytes):
    return client.post("/api/voice/transcribe", files={"audio": ("a.wav", data, "audio/wav")})


def test_fake_transcriber_returns_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_fake_adapters", True)
    resp = _post(WAV)
    assert resp.status_code == 200 and resp.json() == {"text": "also fail any visible dent"}


def test_slow_transcribe_does_not_block_health(monkeypatch) -> None:
    class Slow:
        def transcribe(self, wav: bytes) -> str:
            time.sleep(1.5)
            return "x"

    monkeypatch.setattr(voice, "_get_transcriber", lambda: Slow())

    async def run() -> float:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            start = time.monotonic()
            post = asyncio.create_task(
                c.post("/api/voice/transcribe", files={"audio": ("a.wav", WAV, "audio/wav")})
            )
            await asyncio.sleep(0.05)
            assert (await c.get("/api/health")).status_code == 200
            elapsed = time.monotonic() - start
            assert (await post).json() == {"text": "x"}
            return elapsed

    assert asyncio.run(run()) < 1.0


def test_keyless_is_503(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_fake_adapters", False)
    monkeypatch.setattr(settings, "meta_api_key", "")
    assert _post(WAV).status_code == 503


def test_non_wav_is_422(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_fake_adapters", True)
    assert _post(b"not audio at all, definitely").status_code == 422


def test_adapter_posts_multipart_and_strips(monkeypatch) -> None:
    monkeypatch.setattr(settings, "meta_api_key", "k")
    monkeypatch.setattr(settings, "meta_api_base_url", "https://api.test/v1")
    monkeypatch.setattr(settings, "voice_model_id", "voice-x")
    seen = {}

    class Resp:
        def json(self):
            return {"transcript": " also fail any dent. "}

    def fake_post(url, **kwargs):
        seen["url"], seen["kwargs"] = url, kwargs
        return Resp()

    monkeypatch.setattr(muse_voice, "post_with_retry", fake_post)
    assert muse_voice.MuseVoiceTranscriber().transcribe(WAV) == "also fail any dent."
    assert seen["url"] == "https://api.test/v1/asr/transcribe"
    assert json.loads(seen["kwargs"]["files"]["request"][1])["model"] == "voice-x"


@pytest.mark.parametrize("body", [{}, {"transcript": "  "}])
def test_missing_transcript_raises(monkeypatch, body) -> None:
    monkeypatch.setattr(settings, "meta_api_key", "k")
    monkeypatch.setattr(settings, "meta_api_base_url", "https://api.test/v1")
    monkeypatch.setattr(settings, "voice_model_id", "voice-x")

    class Resp:
        def json(self):
            return body

    monkeypatch.setattr(muse_voice, "post_with_retry", lambda *a, **k: Resp())
    with pytest.raises(RuntimeError):
        muse_voice.MuseVoiceTranscriber().transcribe(WAV)
