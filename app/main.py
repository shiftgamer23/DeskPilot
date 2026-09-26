"""FastAPI app entry point. Route definitions live in app/api/, pydantic models in app/models/,
infrastructure (run tracking, Redis cache, Langfuse tracing) in app/infra/.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tickets import router as tickets_router
from app.infra import db, tracing
from app.infra.run_store import Run, store


@asynccontextmanager
async def lifespan(app: FastAPI):
    for row in db.list_runs():  # no-op if DATABASE_URL is unset/unreachable - see app/infra/db.py
        result = row.get("result")
        # Only the final decision is persisted, not the step-by-step trace - synthesize the one event the
        # trace panel needs to still show the outcome for a ticket reloaded after a restart.
        events = [{"type": "decision", "decision": result}] if result else []
        store.hydrate(Run(
            run_id=row["run_id"], subject=row["subject"], body=row["body"], customer_id=row["customer_id"],
            provider=row["provider"], status=row["status"], created_at=row["created_at"],
            events=events, result=result, error=row.get("error"),
        ))
    yield
    tracing.flush()  # send any buffered Langfuse traces before the process exits


app = FastAPI(title="Ticket Triage Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],  # demo project, no auth
)

app.include_router(tickets_router)
