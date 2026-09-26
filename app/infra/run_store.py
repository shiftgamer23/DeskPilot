"""In-memory store for ticket-triage runs (submitted ticket -> status -> events -> final decision).

Deliberately in-memory, not Redis, for now: this tracks *in-flight API runs* for streaming/listing, a
different concern from Phase 6's Redis cache (which avoids redundant LLM calls on repeated ticket text -
see app/infra/cache.py once that lands). Swapping this store's backing to Redis later only touches this
file - the RunStore interface stays the same.

Threading note: `push_event`/`finish`/`fail` mutate shared state and touch asyncio.Queue objects, so they
must only be called from the event loop thread. app/api/tickets.py enforces this via
loop.call_soon_threadsafe() when reporting progress from the background thread that actually runs the agent.
"""
import time
import uuid
from asyncio import Queue
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Run:
    run_id: str
    subject: Optional[str]
    body: str
    customer_id: Optional[str]
    provider: Optional[str]
    status: str = "pending"  # pending -> running -> done | error
    created_at: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None
    subscribers: list[Queue] = field(default_factory=list)


class RunStore:
    def __init__(self):
        self._runs: dict[str, Run] = {}

    def create(self, subject: str | None, body: str, customer_id: str | None, provider: str | None) -> Run:
        run = Run(run_id=uuid.uuid4().hex[:12], subject=subject, body=body, customer_id=customer_id,
                   provider=provider)
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[Run]:
        return self._runs.get(run_id)

    def list(self, limit: int = 50) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)[:limit]

    def subscribe(self, run_id: str) -> Optional[Queue]:
        run = self._runs.get(run_id)
        if run is None:
            return None
        q: Queue = Queue()
        run.subscribers.append(q)
        return q

    def unsubscribe(self, run_id: str, q: Queue) -> None:
        run = self._runs.get(run_id)
        if run:
            run.subscribers = [s for s in run.subscribers if s is not q]

    def push_event(self, run_id: str, event: dict) -> None:
        run = self._runs.get(run_id)
        if run is None:
            return
        run.status = "running"
        run.events.append(event)
        for q in run.subscribers:
            q.put_nowait(event)

    def finish(self, run_id: str, result: dict) -> None:
        run = self._runs.get(run_id)
        if run is None:
            return
        run.status, run.result = "done", result
        for q in run.subscribers:
            q.put_nowait({"type": "end", "status": "done"})

    def fail(self, run_id: str, error: str) -> None:
        run = self._runs.get(run_id)
        if run is None:
            return
        run.status, run.error = "error", error
        for q in run.subscribers:
            q.put_nowait({"type": "end", "status": "error", "error": error})


store = RunStore()  # single process-wide instance
