"""The Triage Agent's LangGraph flow: agent <-> tools loop, ending in a deterministic confidence gate.

    START -> agent -[no tool call]-> nudge -> agent (retry)
                  -[search/context]-> tools -> agent (loop, reason over results)
                  -[submit_decision]-> tools -> gate -> END
                  -[turn limit hit]-> fallback -> END

Two things are deliberately NOT trusted at face value from the LLM:
  1. `action=auto_resolve` - the `gate` node re-checks that the cited past ticket was actually retrieved
     and that its similarity score clears AUTO_RESOLVE_MIN_SCORE. An LLM saying "confidence: 0.95" is not
     enough evidence on its own; this makes confidence-gating a real, checkable rule, not a self-report.
  2. A premium customer with a repeat issue on record (from get_customer_context) forces escalation even
     if the LLM chose route/auto_resolve - this is the `vip_repeat` flagship pattern, enforced as a safety
     net rather than left purely to prompting.
Both overrides are recorded on the output (gate_overridden, gate_reason) rather than applied silently.
"""
import json
import time
from functools import lru_cache
from typing import Annotated, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app import config
from app.agent.agent_tools import AGENT_TOOLS
from app.agent.prompts import SYSTEM_PROMPT, ticket_message
from app.infra import tracing
from app.models.decision import Decision, GatedDecision
from app.llm.provider import get_llm

NUDGE = (
    "You must call a tool to continue: search_past_tickets, get_customer_context, or - if you are ready to "
    "finish - submit_decision. Do not respond with plain text."
)
FALLBACK_REASON = "Agent did not reach a structured decision within the turn limit; defaulting to escalation."


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tools_called: list[str]
    retrieval_hits: list[dict]
    customer_context: Optional[dict]
    decision: Optional[dict]
    turns: int
    final: Optional[dict]
    _provider: Optional[str]  # which LLM provider to use for this run; read once by agent_node


_TOOL_MAP = {t.name: t for t in AGENT_TOOLS}


def agent_node(state: AgentState) -> dict:
    llm = _bound_llm(state.get("_provider"))
    error = None
    for attempt in range(3):
        try:
            response = llm.invoke(state["messages"])
            return {"messages": [response], "turns": state["turns"] + 1}
        except Exception as e:  # e.g. Groq's gpt-oss models occasionally emit a malformed tool call
            error = e
            time.sleep(0.5 * (attempt + 1))
    # All retries failed. Don't crash the run - fall through as if the model said nothing, so the
    # existing route_after_agent -> nudge/fallback path handles it the same as any other stuck turn.
    note = f"[LLM call failed after retries: {type(error).__name__}: {error}]"
    return {"messages": [AIMessage(content=note)], "turns": state["turns"] + 1}


def route_after_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "fallback" if state["turns"] >= config.MAX_AGENT_TURNS else "nudge"


def nudge_node(state: AgentState) -> dict:
    return {"messages": [HumanMessage(NUDGE)]}


def tools_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    tool_msgs, tools_called = [], list(state["tools_called"])
    retrieval_hits, customer_context, decision = (
        list(state["retrieval_hits"]),
        state["customer_context"],
        state["decision"],
    )
    for tc in last.tool_calls:
        name = tc["name"]
        try:
            result = _TOOL_MAP[name].invoke(tc["args"])
        except Exception as e:  # a malformed call (e.g. bad enum value) becomes visible tool feedback, not a crash
            result = {"error": f"{type(e).__name__}: {e}"}
        tool_msgs.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=tc["id"], name=name))
        tools_called.append(name)
        if name == "search_past_tickets" and isinstance(result, list):
            retrieval_hits.extend(result)
        elif name == "get_customer_context" and isinstance(result, dict):
            customer_context = result
        elif name == "submit_decision" and "error" not in result:
            decision = result
    return {
        "messages": tool_msgs,
        "tools_called": tools_called,
        "retrieval_hits": retrieval_hits,
        "customer_context": customer_context,
        "decision": decision,
    }


def route_after_tools(state: AgentState) -> str:
    if state["decision"] is not None:
        return "gate"
    return "fallback" if state["turns"] >= config.MAX_AGENT_TURNS else "agent"


def gate_node(state: AgentState) -> dict:
    decision = dict(state["decision"])
    llm_action, llm_confidence = decision["action"], decision["confidence"]
    reasons = []

    if decision["action"] == "auto_resolve":
        cited = decision.get("cited_ticket_id")
        hit = next((h for h in state["retrieval_hits"] if h["ticket_id"] == cited), None) if cited else None
        if hit is None:
            decision["action"] = "escalate"
            reasons.append("cited_ticket_id missing or not among retrieved results")
        elif hit["score"] < config.AUTO_RESOLVE_MIN_SCORE:
            decision["action"] = "escalate"
            reasons.append(f"retrieval score {hit['score']:.4f} below auto-resolve threshold "
                            f"{config.AUTO_RESOLVE_MIN_SCORE}")

    ctx = state["customer_context"]
    if ctx and ctx["vip_tier"] == "premium" and ctx["prior_ticket_count"] >= config.VIP_REPEAT_MIN_PRIOR:
        if decision["action"] != "escalate":
            decision["action"] = "escalate"
            reasons.append(f"premium customer with {ctx['prior_ticket_count']} prior tickets on record")

    top_score = max((h["score"] for h in state["retrieval_hits"]), default=None)
    gated = GatedDecision(
        **decision,
        llm_action=llm_action,
        llm_confidence=llm_confidence,
        gate_overridden=bool(reasons),
        gate_reason="; ".join(reasons) or None,
        tools_called=state["tools_called"],
        retrieval_top_score=top_score,
    )
    return {"final": gated.model_dump()}


def fallback_node(state: AgentState) -> dict:
    decision = Decision(
        action="escalate", queue="General Inquiry", type="Request", priority="medium",
        confidence=0.0, justification=FALLBACK_REASON, cited_ticket_id=None,
    )
    top_score = max((h["score"] for h in state["retrieval_hits"]), default=None)
    gated = GatedDecision(
        **decision.model_dump(), llm_action="none", llm_confidence=0.0,
        gate_overridden=True, gate_reason="turn_limit_exceeded",
        tools_called=state["tools_called"], retrieval_top_score=top_score,
    )
    return {"final": gated.model_dump()}


@lru_cache(maxsize=4)
def _bound_llm(provider: Optional[str]):
    return get_llm(provider).bind_tools(AGENT_TOOLS)


@lru_cache(maxsize=1)
def _compiled_graph():
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("nudge", nudge_node)
    g.add_node("tools", tools_node)
    g.add_node("gate", gate_node)
    g.add_node("fallback", fallback_node)

    g.set_entry_point("agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "nudge": "nudge", "fallback": "fallback"})
    g.add_edge("nudge", "agent")
    g.add_conditional_edges("tools", route_after_tools, {"gate": "gate", "agent": "agent", "fallback": "fallback"})
    g.add_edge("gate", END)
    g.add_edge("fallback", END)
    return g.compile()


def _initial_state(subject: str | None, body: str, customer_id: str | None, provider: str | None) -> AgentState:
    return {
        "messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(ticket_message(subject, body, customer_id))],
        "tools_called": [],
        "retrieval_hits": [],
        "customer_context": None,
        "decision": None,
        "turns": 0,
        "final": None,
        "_provider": provider,
    }


def _trace_metadata(final: Optional[dict], provider: Optional[str]) -> dict:
    return {
        "action": final["action"] if final else None,
        "gate_overridden": final["gate_overridden"] if final else None,
        "gate_reason": final["gate_reason"] if final else None,
        "tools_called": final["tools_called"] if final else None,
        "provider": provider or config.LLM_PROVIDER,
    }


def run_triage(subject: str | None, body: str, customer_id: str | None = None, provider: str | None = None) -> dict:
    """Runs one ticket through the full agent loop. Returns a GatedDecision dict (see app/agent/schemas.py)."""
    state = _initial_state(subject, body, customer_id, provider)
    run_config = {"recursion_limit": 50}
    handler = tracing.get_callback_handler()
    langfuse = tracing.get_langfuse()
    if handler is None or langfuse is None:
        return _compiled_graph().invoke(state, config=run_config)["final"]

    run_config["callbacks"] = [handler]
    with langfuse.start_as_current_observation(
        name="triage_agent", as_type="span",
        input={"subject": subject, "body": body, "customer_id": customer_id},
    ) as span:
        final = _compiled_graph().invoke(state, config=run_config)["final"]
        span.update(output=final, metadata=_trace_metadata(final, provider))
    return final


def _event_from_update(node_name: str, update: dict) -> Optional[dict]:
    """Turns one LangGraph node's raw state update into a small, JSON-serializable event for the API/frontend."""
    if node_name == "agent":
        msgs = update.get("messages") or []
        last = msgs[-1] if msgs else None
        tool_calls = getattr(last, "tool_calls", None) if last else None
        if tool_calls:
            return {"type": "tool_call", "tools": [{"name": tc["name"], "args": tc["args"]} for tc in tool_calls]}
        return {"type": "agent_note", "content": getattr(last, "content", "")} if last else None
    if node_name == "nudge":
        return {"type": "nudge"}
    if node_name == "tools":
        results = []
        for m in update.get("messages") or []:
            try:
                content = json.loads(m.content)
            except (TypeError, ValueError):
                content = m.content
            results.append({"tool": getattr(m, "name", None), "content": content})
        return {"type": "tool_result", "results": results}
    if node_name in ("gate", "fallback"):
        final = update.get("final")
        return {"type": "decision", "decision": final} if final else None
    return None


def stream_triage(subject: str | None, body: str, customer_id: str | None = None, provider: str | None = None):
    """Generator yielding one event dict per agent step (tool calls, tool results, final decision) - the same
    run as run_triage(), just observable step-by-step instead of returning only the end result. Synchronous/
    blocking (like the rest of the agent stack); callers that need this alongside an async server (see
    app/main.py) run it in a background thread and relay events onto the event loop."""
    state = _initial_state(subject, body, customer_id, provider)
    run_config = {"recursion_limit": 50}
    handler = tracing.get_callback_handler()
    langfuse = tracing.get_langfuse()
    if handler is not None:
        run_config["callbacks"] = [handler]

    def _events():
        for update in _compiled_graph().stream(state, config=run_config, stream_mode="updates"):
            for node_name, node_update in update.items():
                event = _event_from_update(node_name, node_update)
                if event:
                    yield event

    if handler is None or langfuse is None:
        yield from _events()
        return

    with langfuse.start_as_current_observation(
        name="triage_agent", as_type="span",
        input={"subject": subject, "body": body, "customer_id": customer_id},
    ) as span:
        final = None
        for event in _events():
            if event["type"] == "decision":
                final = event["decision"]
            yield event
        span.update(output=final, metadata=_trace_metadata(final, provider))
