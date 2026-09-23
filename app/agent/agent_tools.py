"""LangChain @tool wrappers around the Phase 2 tool functions, for LLM tool-calling.

Kept separate from app/tools/*.py so those stay plain, independently testable Python functions (Phase 2),
while this layer only adds the LLM-facing schema/description. `search_past_tickets` is pinned to hybrid
mode here - mode-switching is a retrieval-evaluation knob (see eval/compare_retrieval.py), not a choice
the agent itself needs to make.
"""
from langchain_core.tools import StructuredTool, tool

from app.agent.schemas import Decision
from app.tools.get_customer_context import get_customer_context as _get_customer_context
from app.tools.search_past_tickets import search_past_tickets as _search_past_tickets


@tool
def search_past_tickets(query: str, k: int = 5) -> list[dict]:
    """Search resolved past support tickets for ones similar to the given text. Returns up to k matches,
    each with ticket_id, score (higher = more similar; roughly: >0.02 means a real precedent exists, well
    below that means this situation has little precedent), subject, body, answer (the past resolution),
    queue, type, priority, tag_1. Use the incoming ticket's own subject+body as the query."""
    return _search_past_tickets(query, mode="hybrid", k=k)


@tool
def get_customer_context(customer_id: str) -> dict | None:
    """Look up a customer's account: vip_tier (standard/premium), account_age_days, churn_risk
    (low/medium/high), prior_ticket_count, and prior_tickets (their past ticket queue/type/priority/summary).
    Returns None if the customer_id is unknown. Call this whenever a customer_id is available - a premium
    customer with a repeat issue on record should usually be escalated even if the current ticket text
    alone looks routine."""
    return _get_customer_context(customer_id)


def _submit_decision(**kwargs) -> dict:
    return Decision(**kwargs).model_dump()


# The agent's only way to "finish": filling out this schema, enforced via native tool-calling (not a
# freeform final message we'd have to parse and hope is valid JSON).
submit_decision = StructuredTool.from_function(
    func=_submit_decision,
    name="submit_decision",
    description="Call this exactly once, when and only when you are ready to give your final triage decision "
    "for this ticket. This ends your turn - do not call any other tool afterward.",
    args_schema=Decision,
)

AGENT_TOOLS = [search_past_tickets, get_customer_context, submit_decision]
