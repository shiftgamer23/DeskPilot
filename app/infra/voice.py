"""Speech-to-text and text-to-speech via Sarvam AI's REST API (English, en-IN).

Unlike the Redis cache and Postgres layers, this does NOT fail open: voice is the feature itself, not an
optimization, so a missing key or a provider error raises and the API layer turns it into a clear HTTP error
rather than silently doing nothing.

Kept behind two plain functions (transcribe / speak) so the provider can be swapped without touching callers,
the same way the LLM provider is swappable in app/llm/provider.py.
"""
import base64

import httpx

from app import config

_BASE = "https://api.sarvam.ai"
_TIMEOUT = 30.0
_TTS_MAX_CHARS = 2500  # bulbul:v3 limit per request


class VoiceUnavailable(Exception):
    """SARVAM_API_KEY is not configured."""


class VoiceProviderError(Exception):
    """Sarvam rejected or failed the request."""


def _headers() -> dict:
    if not config.SARVAM_API_KEY:
        raise VoiceUnavailable("SARVAM_API_KEY is not set")
    return {"api-subscription-key": config.SARVAM_API_KEY}


def _check(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    if resp.status_code in (401, 403):
        raise VoiceProviderError("Sarvam rejected the API key")
    if resp.status_code == 429:
        raise VoiceProviderError("Sarvam rate limit or credits exhausted")
    raise VoiceProviderError(f"Sarvam returned HTTP {resp.status_code}: {resp.text[:200]}")


def transcribe(audio: bytes, content_type: str) -> str:
    """Browser-recorded audio (webm/ogg/mp4/wav) -> English text. Sarvam's REST endpoint suits clips under ~30s."""
    mime = content_type.split(";")[0].strip() or "audio/webm"
    ext = mime.split("/")[-1]
    try:
        resp = httpx.post(
            f"{_BASE}/speech-to-text",
            headers=_headers(),
            files={"file": (f"speech.{ext}", audio, mime)},
            data={"model": config.SARVAM_STT_MODEL, "mode": "transcribe", "language_code": config.VOICE_LANGUAGE},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise VoiceProviderError(f"Could not reach Sarvam: {type(e).__name__}") from e
    _check(resp)
    return (resp.json().get("transcript") or "").strip()


def speak(text: str, codec: str = "mp3") -> tuple[bytes, str]:
    """English text -> (audio bytes, media type)."""
    try:
        resp = httpx.post(
            f"{_BASE}/text-to-speech",
            headers=_headers(),
            json={
                "text": text[:_TTS_MAX_CHARS],
                "language_code": config.VOICE_LANGUAGE,
                "model": config.SARVAM_TTS_MODEL,
                "speaker": config.SARVAM_TTS_SPEAKER,
                "output_audio_codec": codec,
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise VoiceProviderError(f"Could not reach Sarvam: {type(e).__name__}") from e
    _check(resp)
    audios = resp.json().get("audios") or []
    if not audios:
        raise VoiceProviderError("Sarvam returned no audio")
    media_type = {"mp3": "audio/mpeg", "wav": "audio/wav"}.get(codec, f"audio/{codec}")
    return base64.b64decode(audios[0]), media_type
