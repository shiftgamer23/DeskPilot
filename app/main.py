"""FastAPI app entry point. Route definitions live in app/api/, pydantic models in app/models/,
infrastructure (run tracking, Redis cache, Langfuse tracing) in app/infra/.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tickets import router as tickets_router
from app.infra import tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    tracing.flush()  # send any buffered Langfuse traces before the process exits


app = FastAPI(title="Ticket Triage Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],  # demo project, no auth
)

app.include_router(tickets_router)
