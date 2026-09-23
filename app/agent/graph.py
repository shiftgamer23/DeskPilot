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
from functools import lru_cache
from typing import Annotated, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app import config
from app.agent.agent_tools import AGENT_TOOLS
from app.agent.prompts import SYSTEM_PROMPT, ticket_message
from app.agent.schemas import Decision, GatedDecision
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
    response = llm.invoke(state["messages"])
    return {"messages": [response], "turns": state["turns"] + 1}


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
        tool_msgs.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=tc["id"]))
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


def run_triage(subject: str | None, body: str, customer_id: str | None = None, provider: str | None = None) -> dict:
    """Runs one ticket through the full agent loop. Returns a GatedDecision dict (see app/agent/schemas.py)."""
    initial_state: AgentState = {
        "messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(ticket_message(subject, body, customer_id))],
        "tools_called": [],
        "retrieval_hits": [],
        "customer_context": None,
        "decision": None,
        "turns": 0,
        "final": None,
        "_provider": provider,
    }
    result = _compiled_graph().invoke(initial_state, config={"recursion_limit": 50})
    return result["final"]
