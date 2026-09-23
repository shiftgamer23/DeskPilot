"""Hand-authored flagship demo scenarios. Deliberately NOT random - these are the demo/regression cases.

Each scenario is a synthetic customer (with a history built from *real* tickets) plus a hand-written incoming ticket.
The point of each is that the correct decision depends on evidence the agent must gather, not on the text alone.
"""

# --- Customers (profile fields are hand-set; prior tickets are real dataset rows referenced by ID) ---
FLAGSHIP_CUSTOMERS = {
    # 1. VIP with a repeat billing problem on record.
    "CUST-9001": {
        "name": "Dana Whitfield",
        "email": "dana.whitfield@example.com",
        "vip_tier": "premium",
        "account_age_days": 1460,
        "churn_risk": "high",
        "prior_ticket_ids": ["T00113", "T00117", "T00119", "T00157"],  # 4 real Billing discrepancy tickets
    },
    # 2. Brand-new customer, no history.
    "CUST-9002": {
        "name": "Marcus Lindqvist",
        "email": "marcus.lindqvist@example.com",
        "vip_tier": "standard",
        "account_age_days": 12,
        "churn_risk": "low",
        "prior_ticket_ids": [],
    },
    # 3. Ordinary customer whose two prior tickets are in unrelated queues (history does not disambiguate).
    "CUST-9003": {
        "name": "Priya Raman",
        "email": "priya.raman@example.com",
        "vip_tier": "standard",
        "account_age_days": 310,
        "churn_risk": "medium",
        "prior_ticket_ids": ["T00035", "T00231"],  # Technical Support/Bug + Product Support/Feature
    },
}

# --- Incoming tickets ---
FLAGSHIP_SCENARIOS = [
    {
        "id": "vip_repeat",
        "customer_id": "CUST-9001",
        "subject": "Question About My Latest Invoice",
        "body": (
            "Dear Customer Support Team,\n\n"
            "I hope you are well. I noticed that the total on my most recent invoice looks slightly different "
            "from previous months, and I would like to understand what is included in the charges. "
            "Could you please confirm the breakdown?\n\n"
            "Thank you for your help."
        ),
        "expected_action": "escalate",
        "expected_queue": "Billing and Payments",
        "why": "Text alone reads as a routine invoice question, but the customer is premium, high churn risk, "
        "and has 4 prior billing-discrepancy tickets. Context should drive escalation.",
    },
    {
        "id": "first_time_match",
        "customer_id": "CUST-9002",
        "subject": "Question About How Billing Works",
        "body": (
            "Hello,\n\n"
            "I'm new to your service and would like to understand how billing works. When are invoices issued, "
            "how soon do they need to be paid, which payment methods do you accept, and are there any fees "
            "for paying late?\n\n"
            "Thanks in advance."
        ),
        "expected_action": "auto_resolve",
        "expected_queue": "Billing and Payments",
        "expected_type": "Request",
        "expected_source_ticket_id": "T00034",  # paraphrase of this real, resolved ticket
        "why": "First-time standard customer; a near-identical past ticket exists with a clear resolution. "
        "Should auto-resolve and cite that resolution.",
    },
    {
        "id": "ambiguous",
        "customer_id": "CUST-9003",
        "subject": "Still Not Working",
        "body": (
            "Hi,\n\n"
            "It's still not working. I already tried what you suggested last time and nothing has changed. "
            "Please sort this out as soon as possible.\n\n"
            "Thanks."
        ),
        "expected_action": "escalate",
        "expected_queue": None,
        "why": "No product, symptom or error is named; retrieval has nothing specific to match and the "
        "customer's two prior tickets are in unrelated queues. Should escalate on low confidence, not guess.",
    },
]

# Real tickets these scenarios depend on. They are kept out of dev/eval and out of random history assignment,
# so they are guaranteed to sit in the retrieval corpus.
RESERVED_TICKET_IDS = sorted(
    {tid for c in FLAGSHIP_CUSTOMERS.values() for tid in c["prior_ticket_ids"]}
    | {s["expected_source_ticket_id"] for s in FLAGSHIP_SCENARIOS if "expected_source_ticket_id" in s}
)
