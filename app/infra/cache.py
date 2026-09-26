"""Redis-backed cache for full agent decisions, keyed on a normalized hash of the ticket text (+
customer_id, + provider) so an identical resubmission skips the LLM/tool-calling loop entirely.

Fails open: if Redis is unreachable, get()/set() act as a no-op cache miss (with a one-time warning)
rather than raising. Caching is a pure optimization here, never a correctness requirement - the agent
must keep working even if Redis is down, same "degrade gracefully" discipline as the rest of the app.
"""
import hashlib
import json
import logging
from functools import lru_cache
from typing import Optional

import redis

from app import config

logger = logging.getLogger(__name__)
_warned = False


def _warn_once(msg: str) -> None:
    global _warned
    if not _warned:
        logger.warning(msg)
        _warned = True


@lru_cache(maxsize=1)
def _client() -> Optional["redis.Redis"]:
    try:
        client = redis.from_url(config.REDIS_URL, socket_connect_timeout=2, decode_responses=True)
        client.ping()
        return client
    except redis.RedisError as e:
        _warn_once(f"Redis unavailable ({e}); caching disabled for this process")
        return None


def build_key(subject: str | None, body: str, customer_id: str | None, provider: str | None) -> str:
    """Whitespace/case-normalized so near-identical resubmissions (extra spaces, different casing) still
    hit the cache. Provider is included alongside the plan's "text + customer_id" because different
    providers can legitimately produce different decisions for the same ticket - keying only on
    text+customer_id would let a Gemini run silently serve a cached Groq answer, or vice versa."""
    def norm(s: str | None) -> str:
        # Real historical tickets can have a missing subject, which pandas represents as float('nan') -
        # truthy, so `s or ""` doesn't catch it. Anything that isn't actually a str is treated as absent.
        return " ".join((s if isinstance(s, str) else "").split()).lower()

    resolved_provider = (provider or config.LLM_PROVIDER).lower()
    raw = f"{norm(subject)}\x1f{norm(body)}\x1f{customer_id or ''}\x1f{resolved_provider}"
    return "triage:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> Optional[dict]:
    client = _client()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except redis.RedisError as e:
        _warn_once(f"Redis get failed ({e}); treating as cache miss")
        return None
    return json.loads(raw) if raw else None


def set(key: str, decision: dict, ttl: int = config.CACHE_TTL_SECONDS) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.set(key, json.dumps(decision), ex=ttl)
    except redis.RedisError as e:
        _warn_once(f"Redis set failed ({e}); decision not cached")


if __name__ == "__main__":
    k = build_key("Test Subject", "  Some   ticket BODY text  ", "CUST-0001", "groq")
    print("key:", k)
    print("miss (expected None):", get(k))
    set(k, {"action": "route", "confidence": 0.5}, ttl=30)
    print("hit:", get(k))
    # same text, different whitespace/case -> should hit the same key
    k2 = build_key("test subject", "some ticket body text", "CUST-0001", "groq")
    print("normalized key matches:", k == k2)
