"""Public entry point for the Triage Agent. app/api/ and eval/run_eval.py should import from here,
not reach into app.agent.graph directly.

Wraps the graph with the Phase 6 Redis cache: an identical resubmission (same ticket text, customer_id,
and provider - see app/infra/cache.py's normalization) returns the previous decision instantly instead of
re-running the LLM/tool-calling loop. Caching fails open, so this wrapper behaves exactly like the
uncached graph whenever Redis is unavailable.
"""
from app.agent.graph import run_triage, stream_triage
from app.infra import cache


def triage(subject: str | None, body: str, customer_id: str | None = None, provider: str | None = None) -> dict:
    """Run one ticket through the agent (or return a cached decision for an identical resubmission).
    Returns a GatedDecision dict, plus `cached`: True if this decision was served from Redis:
    action, queue, type, priority, confidence, justification, cited_ticket_id,
    llm_action, llm_confidence, gate_overridden, gate_reason, tools_called, retrieval_top_score, cached.
    """
    key = cache.build_key(subject, body, customer_id, provider)
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}
    result = run_triage(subject, body, customer_id, provider)
    cache.set(key, result)
    return {**result, "cached": False}


def triage_stream(subject: str | None, body: str, customer_id: str | None = None, provider: str | None = None):
    """Same as triage(), but yields one small event dict per agent step instead of only the final result.
    On a cache hit, yields a single `decision` event immediately (no tool_call/tool_result steps, since
    nothing was re-run) rather than replaying the original run's steps.
    Blocking/synchronous - see app.agent.graph.stream_triage for the threading note."""
    key = cache.build_key(subject, body, customer_id, provider)
    cached = cache.get(key)
    if cached is not None:
        yield {"type": "decision", "decision": {**cached, "cached": True}}
        return

    final = None
    for event in stream_triage(subject, body, customer_id, provider):
        if event.get("type") == "decision":
            final = event["decision"]
            event = {**event, "decision": {**event["decision"], "cached": False}}
        yield event
    if final is not None:
        cache.set(key, final)
