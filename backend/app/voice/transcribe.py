"""Optional local speech recognition with faster-whisper (open source, runs on CPU).

Browsers with the Web Speech API transcribe on the client; this endpoint is the fallback for
browsers without it (e.g. Firefox). Enable with WHISPER_ENABLED=true and `pip install faster-whisper`.
"""
import logging
import tempfile
import threading

from app.core.config import get_settings

log = logging.getLogger(__name__)
_model = None
_lock = threading.Lock()


class WhisperUnavailable(RuntimeError):
    pass


def _get_model():
    global _model
    s = get_settings()
    if not s.whisper_enabled:
        raise WhisperUnavailable("Server speech recognition is disabled (set WHISPER_ENABLED=true).")
    with _lock:
        if _model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise WhisperUnavailable("faster-whisper is not installed on the server.") from exc
            _model = WhisperModel(s.whisper_model, device="cpu", compute_type="int8")
    return _model


def transcribe(audio: bytes, language: str | None) -> dict:
    model = _get_model()
    with tempfile.NamedTemporaryFile(suffix=".webm") as f:
        f.write(audio)
        f.flush()
        segments, info = model.transcribe(f.name, language=(language or "").split("-")[0] or None, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    return {"text": text, "language": info.language, "duration": info.duration}
