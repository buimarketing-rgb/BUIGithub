from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.deps import rate_limit, require_member
from app.models import User
from app.voice.transcribe import WhisperUnavailable, transcribe

router = APIRouter(prefix="/voice", tags=["voice"])
MAX_AUDIO = 15 * 1024 * 1024


@router.get("/capabilities")
def capabilities(_: User = Depends(require_member)):
    return {"server_transcription": get_settings().whisper_enabled, "max_audio_mb": MAX_AUDIO // (1024 * 1024)}


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), language: str | None = Form(None), user: User = Depends(require_member)):
    rate_limit("voice", 20, 60, str(user.id))
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty audio")
    if len(data) > MAX_AUDIO:
        raise HTTPException(413, "Audio too long")
    if not (file.content_type or "").startswith(("audio/", "video/webm", "application/octet-stream")):
        raise HTTPException(400, "Unsupported audio format")
    try:
        return await run_in_threadpool(transcribe, data, language)
    except WhisperUnavailable as exc:
        raise HTTPException(501, str(exc))
