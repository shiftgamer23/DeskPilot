"""The agent's final decision, as a Pydantic schema. Used two ways:
  1. As the args schema for the `submit_decision` tool - the LLM can only "finish" by filling this out,
     which is what guarantees structured output (native tool-calling), not prompt-and-hope JSON parsing.
  2. As the shape returned by the API/eval (after the deterministic gate has had a chance to override it).
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app import config


class Decision(BaseModel):
    action: Literal["auto_resolve", "route", "escalate"] = Field(
        description="What should happen to this ticket next."
    )
    queue: Literal[tuple(config.QUEUES)] = Field(
        description="Best-matching queue, even when escalating - a human reviewer still needs a starting point."
    )
    type: Literal[tuple(config.TICKET_TYPES)] = Field(description="ITSM ticket type.")
    priority: Literal[tuple(config.PRIORITIES)] = Field(description="Urgency.")
    confidence: float = Field(ge=0.0, le=1.0, description="Your own confidence in this decision, 0-1.")
    justification: str = Field(
        min_length=15, description="2-4 sentences explaining the decision, referencing what you found, if anything."
    )
    cited_ticket_id: Optional[str] = Field(
        default=None,
        description="Required when action=auto_resolve: the ticket_id (from search_past_tickets results) whose "
        "resolution you are reusing. Must be one of the ticket_ids actually returned by that tool.",
    )


class GatedDecision(Decision):
    """Decision after the deterministic confidence gate. Adds a transparency trail: what the LLM
    originally said, and whether/why the gate overrode it."""

    llm_action: str  # the agent's own action, before any override
    llm_confidence: float
    gate_overridden: bool = False
    gate_reason: Optional[str] = None
    tools_called: list[str] = Field(default_factory=list)
    retrieval_top_score: Optional[float] = None
