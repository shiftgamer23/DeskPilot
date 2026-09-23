"""Tool: get_customer_context(customer_id) -> synthetic account profile + prior-ticket history.

Deliberately excludes the LLM-generated account note (data/synthetic/account_notes.json) - that field is
cosmetic flavor text for the frontend/profile card only, and must never influence the agent's decision or eval.
"""
import json
from functools import lru_cache

from app import config


@lru_cache(maxsize=1)
def _profiles() -> dict:
    return json.loads(config.CUSTOMER_PROFILES.read_text(encoding="utf-8"))


def get_customer_context(customer_id: str) -> dict | None:
    """Returns vip_tier, prior_ticket_count, account_age_days, churn_risk and prior-ticket summaries,
    or None if customer_id is unknown (e.g. an anonymous/guest ticket with no customer_id)."""
    profile = _profiles().get(customer_id)
    if profile is None:
        return None
    return {
        "customer_id": customer_id,
        "vip_tier": profile["vip_tier"],
        "account_age_days": profile["account_age_days"],
        "churn_risk": profile["churn_risk"],
        "prior_ticket_count": profile["prior_ticket_count"],
        "prior_tickets": profile["prior_tickets"],  # [{ticket_id, summary, queue, type, priority, tag_1}, ...]
    }


if __name__ == "__main__":
    for cid in ["CUST-9001", "CUST-9002", "CUST-0001", "CUST-9999"]:
        print(cid, "->", get_customer_context(cid))
