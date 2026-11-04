"""POST /api/voice/transcribe: fake, keyless and non-WAV paths, plus the adapter request."""

import json

import pytest
from fastapi.testclient import TestClient

import app.adapters.muse_voice as muse_voice
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
