"""Langfuse client setup. Actual instrumentation (wrapping the graph's invoke/stream calls, tagging spans
with the gate's decision) lives in app/agent/graph.py, since that's where the LangGraph calls happen.

Fails open like app/infra/cache.py: if the Langfuse keys are missing or the client can't be built, every
getter here returns None and callers skip tracing entirely rather than raising - observability must never
be able to break ticket triage.
"""
from functools import lru_cache
from typing import Optional

from app import config


@lru_cache(maxsize=1)
def get_langfuse() -> Optional["Langfuse"]:  # noqa: F821 - Langfuse imported lazily below
    if not (config.LANGFUSE_SECRET_KEY and config.LANGFUSE_PUBLIC_KEY):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            base_url=config.LANGFUSE_BASE_URL,
        )
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_callback_handler():
    """The LangChain/LangGraph callback handler - pass this in `config={"callbacks": [...]}` on a graph
    invoke/stream call to get every LLM call and tool call traced automatically. None if tracing is off."""
    if get_langfuse() is None:
        return None
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def flush() -> None:
    """Call on process exit (script end, server shutdown) - the SDK batches and sends traces on its own
    schedule otherwise, so a short-lived process (eval/run_eval.py) can exit before its traces are sent."""
    lf = get_langfuse()
    if lf is not None:
        lf.flush()
