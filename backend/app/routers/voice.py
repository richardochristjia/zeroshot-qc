"""POST /api/voice/transcribe: spoken rule edits (WAV in, text out)."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.adapters.base import AdapterNotConfiguredError, Transcriber
from app.adapters.fakes import FakeTranscriber
from app.adapters.muse_voice import MuseVoiceTranscriber
from app.config import settings

router = APIRouter()

MAX_WAV_BYTES = 10 * 1024 * 1024


def _get_transcriber() -> Transcriber:
    """Indirection so tests can substitute a transcriber without HTTP."""
    return FakeTranscriber() if settings.use_fake_adapters else MuseVoiceTranscriber()


@router.post("/api/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    wav = await audio.read(MAX_WAV_BYTES + 1)
    if len(wav) > MAX_WAV_BYTES:
        raise HTTPException(status_code=422, detail="audio is over 10 MB")
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise HTTPException(status_code=422, detail="audio must be a WAV file")
    try:
        return {"text": _get_transcriber().transcribe(wav)}
    except AdapterNotConfiguredError as exc:
        raise HTTPException(
            status_code=503, detail="voice needs META_API_KEY and VOICE_MODEL_ID"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="voice transcription failed") from exc
