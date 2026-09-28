"""Wire-level request/response models for the FastAPI layer (app/api/). Kept separate from
app/models/decision.py, which models the agent's own domain output rather than the HTTP contract."""
from pydantic import BaseModel


class TicketRequest(BaseModel):
    subject: str | None = None
    body: str
    customer_id: str | None = None
    provider: str | None = None  # "groq" | "gemini" | None (uses config default)


class TicketAck(BaseModel):
    run_id: str
    status: str


class TranscriptResponse(BaseModel):
    text: str
