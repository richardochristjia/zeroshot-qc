"""Muse Voice Transcribe adapter: WAV bytes in, transcript text out."""

import json

from app.adapters.base import post_with_retry, require_configured
from app.config import settings


class MuseVoiceTranscriber:
    def transcribe(self, wav: bytes) -> str:
        require_configured(
            model_id=settings.voice_model_id, model_field="VOICE_MODEL_ID", adapter="Muse Voice"
        )
        request = json.dumps(
            {"model": settings.voice_model_id, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
        )
        response = post_with_retry(
            settings.meta_api_base_url.rstrip("/") + "/asr/transcribe",
            headers={"Authorization": f"Bearer {settings.meta_api_key}", "Accept": "application/json"},
            files={"request": (None, request, "application/json"), "audio": ("a.wav", wav, "audio/wav")},
            timeout=60.0,
        )
        transcript = response.json().get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise RuntimeError("Muse Voice returned no transcript")
        return transcript.strip()
