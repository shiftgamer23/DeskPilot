"""Voice endpoints: turn a spoken ticket into text, and speak the agent's routing decision back.

Deliberately thin - the ticket itself still goes through the ordinary POST /tickets pipeline, so voice adds
no second code path into the agent. The spoken reply is templated from the agent's existing structured
Decision (no extra LLM call, so no extra Groq quota).
"""
import asyncio
import re

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra import voice
from app.infra.run_store import store
from app.models.requests import TranscriptResponse

router = APIRouter(tags=["voice"])

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # ~30s of browser-recorded audio is well under 1MB; this is just a sanity cap
_MAX_REASON_CHARS = 240


def _reason(justification: str | None) -> str:
    """First sentence of the agent's justification, minus parenthetical asides (scores, "e.g. T04488") and
    bare ticket IDs, none of which read well aloud."""
    if not justification:
        return ""
    text = re.sub(r"\s*\([^)]*\)", "", justification)
    text = re.sub(r"(?:\bT\d{4,6}\b(?:\s*,\s*and\s+|\s*,\s*|\s+and\s+)?)+", "", text)
    text = re.sub(r"\s+([.,;])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    if len(first) > _MAX_REASON_CHARS:
        first = first[:_MAX_REASON_CHARS].rsplit(" ", 1)[0] + "..."
    return first


def spoken_summary(result: dict) -> str:
    action, queue = result.get("action"), result.get("queue") or "the general queue"
    reason = _reason(result.get("justification"))
    if action == "escalate":
        lead = f"I wasn't confident enough to route this automatically, so I've escalated it to a human reviewer. It looks like a {queue} issue."
    elif action == "auto_resolve":
        lead = f"I found a close match to a previously resolved ticket, so this is being handled automatically under {queue}."
    else:
        lead = f"Your ticket has been routed to {queue}."
    return f"{lead} {reason}".strip()


@router.post("/voice/transcribe", response_model=TranscriptResponse)
async def transcribe_audio(request: Request) -> TranscriptResponse:
    """Body is the raw recorded audio (Content-Type e.g. audio/webm); no multipart, so no extra dependency."""
    audio = await request.body()
    if not audio:
        raise HTTPException(400, "empty audio")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "audio too large")
    content_type = request.headers.get("content-type", "audio/webm")
    try:
        text = await asyncio.to_thread(voice.transcribe, audio, content_type)
    except voice.VoiceUnavailable as e:
        raise HTTPException(503, f"Voice mode is not configured: {e}")
    except voice.VoiceProviderError as e:
        raise HTTPException(502, str(e))
    if not text:
        raise HTTPException(422, "Couldn't hear any speech in that recording")
    return TranscriptResponse(text=text)


@router.get("/tickets/{run_id}/voice")
async def ticket_voice_reply(run_id: str) -> Response:
    """Audio of the agent telling the customer where their ticket went. Only available once the run is done."""
    run = store.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run_id")
    if run.status != "done" or not run.result:
        raise HTTPException(409, "ticket has no decision yet")
    try:
        audio, media_type = await asyncio.to_thread(voice.speak, spoken_summary(run.result))
    except voice.VoiceUnavailable as e:
        raise HTTPException(503, f"Voice mode is not configured: {e}")
    except voice.VoiceProviderError as e:
        raise HTTPException(502, str(e))
    return Response(content=audio, media_type=media_type)
