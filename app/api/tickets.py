"""Ticket endpoints: submit a ticket, watch the agent work over SSE, fetch its final decision.

Threading model: the agent stack is synchronous (LangChain's Groq/Gemini clients block on network calls),
so each submitted ticket runs in its own background thread, not on the event loop. That thread reports
progress back via loop.call_soon_threadsafe(store.push_event, ...) - the only safe way to touch the
asyncio-based RunStore from a non-event-loop thread. See app/infra/run_store.py for the run-tracking side.
"""
import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.triage_agent import triage_stream
from app.infra import db
from app.infra.run_store import Run, store
from app.models.requests import TicketAck, TicketRequest

router = APIRouter(tags=["tickets"])


def _run_summary(run: Run) -> dict:
    r = run.result or {}
    return {
        "run_id": run.run_id,
        "status": run.status,
        "subject": run.subject,
        "body": run.body,
        "customer_id": run.customer_id,
        "created_at": run.created_at,
        "action": r.get("action"),
        "queue": r.get("queue"),
        "confidence": r.get("confidence"),
        "justification": r.get("justification"),
        "cached": r.get("cached"),
    }


def _run_agent_in_thread(run: Run, loop: asyncio.AbstractEventLoop) -> None:
    """Runs on a plain background thread. Never touches the store directly - only via call_soon_threadsafe,
    which safely hands each update to the event loop thread that actually owns the store's asyncio.Queues."""
    try:
        final = None
        for event in triage_stream(run.subject, run.body, run.customer_id, run.provider):
            loop.call_soon_threadsafe(store.push_event, run.run_id, event)
            if event["type"] == "decision":
                final = event["decision"]
        loop.call_soon_threadsafe(store.finish, run.run_id, final)
        db.update_run(run.run_id, "done", result=final)  # plain blocking I/O, safe from this thread
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        loop.call_soon_threadsafe(store.fail, run.run_id, msg)
        db.update_run(run.run_id, "error", error=msg)


@router.post("/tickets", response_model=TicketAck)
async def submit_ticket(req: TicketRequest) -> TicketAck:
    if not req.body or not req.body.strip():
        raise HTTPException(400, "body is required")
    run = store.create(req.subject, req.body, req.customer_id, req.provider)
    await asyncio.to_thread(db.insert_run, run.run_id, run.subject, run.body, run.customer_id, run.provider,
                             run.status, run.created_at)
    loop = asyncio.get_running_loop()  # must be captured on the event loop thread, before the background thread starts
    threading.Thread(target=_run_agent_in_thread, args=(run, loop), daemon=True).start()
    return TicketAck(run_id=run.run_id, status=run.status)


@router.get("/tickets")
def list_tickets(limit: int = 200) -> list[dict]:
    return [_run_summary(r) for r in store.list(limit)]


@router.get("/tickets/{run_id}")
def get_ticket(run_id: str) -> dict:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run_id")
    return {**_run_summary(run), "result": run.result, "error": run.error}


@router.get("/tickets/{run_id}/stream")
async def stream_ticket(run_id: str) -> StreamingResponse:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run_id")

    async def event_gen():
        # Snapshot + subscribe back-to-back with no `await` between them, so no event pushed by the
        # background thread can land in the gap between "already happened" and "now watching live".
        buffered = list(run.events)
        already_done = run.status in ("done", "error")
        q = None if already_done else store.subscribe(run_id)

        for evt in buffered:
            yield f"data: {json.dumps(evt)}\n\n"
        if already_done:
            yield f"data: {json.dumps({'type': 'end', 'status': run.status, 'error': run.error})}\n\n"
            return
        try:
            while True:
                evt = await q.get()
                yield f"data: {json.dumps(evt)}\n\n"
                if evt.get("type") == "end":
                    break
        finally:
            store.unsubscribe(run_id, q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
