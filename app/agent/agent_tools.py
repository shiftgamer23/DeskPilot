"""LangChain @tool wrappers around the Phase 2 tool functions, for LLM tool-calling.

Kept separate from app/tools/*.py so those stay plain, independently testable Python functions (Phase 2),
while this layer only adds the LLM-facing schema/description. `search_past_tickets` is pinned to hybrid
mode here - mode-switching is a retrieval-evaluation knob (see eval/compare_retrieval.py), not a choice
the agent itself needs to make.
"""
from langchain_core.tools import StructuredTool, tool

from app.models.decision import Decision
from app.tools.get_customer_context import get_customer_context as _get_customer_context
from app.tools.search_past_tickets import search_past_tickets as _search_past_tickets

ANSWER_CHAR_CAP = 500  # dataset median ~386 chars, so this rarely truncates a real resolution


def _trim_hit(hit: dict) -> dict:
    # Drop `body` - the past ticket's own question text. It's redundant for the LLM's purposes: judging
    # similarity is already done by search (score) plus subject/tags, and the thing actually worth reusing
    # is `answer`. Dropping it is the single biggest token saving here (full past-ticket bodies were being
    # sent back for every one of k=5 hits, on every search call, and staying in context for the rest of the
    # trajectory) - this is what let a handful of eval runs burn through Groq's daily token quota.
    answer = hit["answer"]
    if len(answer) > ANSWER_CHAR_CAP:
        answer = answer[:ANSWER_CHAR_CAP] + "... [truncated]"
    return {k: v for k, v in hit.items() if k != "body"} | {"answer": answer}


@tool
def search_past_tickets(query: str, k: int = 5) -> list[dict]:
    """Search resolved past support tickets for ones similar to the given text. Returns up to k matches,
    each with ticket_id, score (higher = more similar; roughly: >0.02 means a real precedent exists, well
    below that means this situation has little precedent), subject, answer (the past resolution), queue,
    type, priority, tag_1. Use the incoming ticket's own subject+body as the query."""
    return [_trim_hit(h) for h in _search_past_tickets(query, mode="hybrid", k=k)]


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
