"""Generate the synthetic customer layer. Deterministic (seeded); the raw dataset is never touched.

Outputs (data/synthetic/):
  customer_profiles.json   - profiles + prior-ticket history (deterministic synthetic)
  ticket_customers.json    - which customer each dev/eval incoming ticket belongs to (deterministic synthetic)
  flagship_scenarios.json  - the 3 hand-authored demo scenarios
  account_notes.json       - LLM flavor text; ONLY with --notes, kept separate so the files above stay
                             byte-reproducible. Never used by the agent's decision logic or eval.

Design: a customer's `prior_tickets` are real resolved tickets from the retrieval corpus, and
`prior_ticket_count == len(prior_tickets)` - derived from the assignment, never invented separately.
Incoming dev/eval tickets are *separate* tickets that arrive under a customer_id. Repeat customers (3-5 prior tickets)
are clustered on one queue + tag_1 so "repeat issue" is a real, findable pattern.

Prereq: python eval/build_eval_slice.py   (creates splits.json)
Run:    python data/generate_customer_profiles.py [--notes]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config
from app.data_loader import load_tickets
from app.flagship import FLAGSHIP_CUSTOMERS, FLAGSHIP_SCENARIOS, RESERVED_TICKET_IDS

N_SINGLE, N_REPEAT = 48, 22  # ordinary customers with 1 / 3-5 prior tickets
P_PREMIUM = 0.15
P_CLUSTER_MATCH = 0.5  # share of dev/eval tickets deliberately given to a repeat customer with the same queue
MIN_TAG_POOL = 5  # a repeat cluster needs >= this many unused tickets sharing queue + tag_1

CHURN = ["low", "medium", "high"]
CHURN_W_SINGLE = [0.65, 0.28, 0.07]
CHURN_W_REPEAT = [0.25, 0.40, 0.35]  # repeat complainers are likelier to be at risk


def history_entry(row) -> dict:
    summary = row["subject"] if isinstance(row["subject"], str) else row["body"][:80].rstrip() + "..."
    return {
        "ticket_id": row["ticket_id"],
        "summary": summary,
        "queue": row["queue"],
        "type": row["type"],
        "priority": row["priority"],
        "tag_1": row["tag_1"],
    }


def draw_cluster(available, rng: random.Random) -> list[str]:
    """3-5 unused corpus tickets sharing one queue and one tag_1."""
    queue_counts = available["queue"].value_counts().sort_index()
    queue = rng.choices(list(queue_counts.index), weights=list(queue_counts.values))[0]
    in_queue = available[available["queue"] == queue]
    tag_counts = in_queue["tag_1"].value_counts().sort_index()
    tag_counts = tag_counts[tag_counts >= MIN_TAG_POOL]
    tag = rng.choices(list(tag_counts.index), weights=list(tag_counts.values))[0]
    ids = sorted(in_queue[in_queue["tag_1"] == tag]["ticket_id"])
    return rng.sample(ids, rng.randint(3, 5))


def build_profiles(tickets, corpus_ids: list[str], rng: random.Random) -> dict:
    by_id = tickets.set_index("ticket_id", drop=False)
    fake = Faker()
    Faker.seed(config.SEED)

    profiles: dict[str, dict] = {}
    used = set(RESERVED_TICKET_IDS)  # flagship anchors are never handed to random customers

    kinds = ["repeat"] * N_REPEAT + ["single"] * N_SINGLE
    rng.shuffle(kinds)  # so repeat customers aren't all the lowest IDs
    for i, kind in enumerate(kinds, start=1):
        available = by_id.loc[[t for t in corpus_ids if t not in used]]
        if kind == "repeat":
            history_ids = draw_cluster(available, rng)
        else:
            history_ids = rng.sample(sorted(available["ticket_id"]), 1)
        used.update(history_ids)
        profiles[f"CUST-{i:04d}"] = {
            "name": fake.name(),
            "email": fake.email(),
            "vip_tier": "premium" if rng.random() < P_PREMIUM else "standard",
            "account_age_days": rng.randint(30, 2200),
            "churn_risk": rng.choices(CHURN, weights=CHURN_W_REPEAT if kind == "repeat" else CHURN_W_SINGLE)[0],
            "prior_tickets": [history_entry(by_id.loc[t]) for t in sorted(history_ids)],
            "hand_authored": False,
        }

    for cid, spec in FLAGSHIP_CUSTOMERS.items():
        profiles[cid] = {
            "name": spec["name"],
            "email": spec["email"],
            "vip_tier": spec["vip_tier"],
            "account_age_days": spec["account_age_days"],
            "churn_risk": spec["churn_risk"],
            "prior_tickets": [history_entry(by_id.loc[t]) for t in spec["prior_ticket_ids"]],
            "hand_authored": True,
        }

    for p in profiles.values():
        p["prior_ticket_count"] = len(p["prior_tickets"])  # derived, never independent
    return profiles


def assign_incoming(profiles: dict, tickets, ticket_ids: list[str], rng: random.Random) -> dict[str, str]:
    """Give each dev/eval ticket a customer. Half go to a repeat customer whose cluster queue matches."""
    queue_of = tickets.set_index("ticket_id")["queue"]
    ordinary = sorted(c for c, p in profiles.items() if not p["hand_authored"])
    repeat_by_queue: dict[str, list[str]] = {}
    for c in ordinary:
        p = profiles[c]
        if p["prior_ticket_count"] >= 3:
            repeat_by_queue.setdefault(p["prior_tickets"][0]["queue"], []).append(c)

    out = {}
    for tid in ticket_ids:
        matches = repeat_by_queue.get(queue_of[tid], [])
        out[tid] = rng.choice(matches) if matches and rng.random() < P_CLUSTER_MATCH else rng.choice(ordinary)
    return out


def generate_notes(profiles: dict) -> dict[str, str]:
    """LLM-written flavor text. Cosmetic only. The model is given ONLY deterministic facts, to avoid invented details."""
    from app.llm.provider import get_llm

    llm = get_llm(temperature=0.7)
    notes = {}
    for cid, p in profiles.items():
        history = "; ".join(f"{t['queue']}: {t['summary']}" for t in p["prior_tickets"]) or "none"
        prompt = (
            "Write a 1-2 sentence internal CRM account note about a customer for a support team. "
            "Use ONLY the facts below. Do not invent refunds, amounts, dates, product names or events.\n"
            f"- Tier: {p['vip_tier']}\n- Account age: {p['account_age_days']} days\n"
            f"- Churn risk: {p['churn_risk']}\n- Prior tickets ({p['prior_ticket_count']}): {history}\n"
            "Note:"
        )
        for attempt in range(3):
            try:
                # the model emits non-breaking hyphens (U+2011); normalize so the text is plain-searchable
                notes[cid] = llm.invoke(prompt).content.strip().replace("‑", "-")
                break
            except Exception as e:  # rate limit etc. - cosmetic step, so degrade gracefully
                print(f"  {cid} attempt {attempt + 1} failed: {type(e).__name__}")
                time.sleep(2 * (attempt + 1))
        time.sleep(0.3)
    return notes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", action="store_true", help="also generate LLM flavor notes (account_notes.json)")
    args = parser.parse_args()

    tickets = load_tickets()
    splits = json.loads(config.SPLITS.read_text(encoding="utf-8"))
    rng = random.Random(config.SEED)

    profiles = build_profiles(tickets, splits["corpus"], rng)
    assignments = assign_incoming(profiles, tickets, splits["dev"] + splits["eval"], rng)

    def dump(path, obj):
        path.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")

    dump(config.CUSTOMER_PROFILES, profiles)
    dump(config.TICKET_CUSTOMERS, assignments)
    dump(config.FLAGSHIP_SCENARIOS, FLAGSHIP_SCENARIOS)
    print(f"{len(profiles)} customers, {len(assignments)} dev/eval tickets assigned -> {config.SYNTHETIC_DIR}")

    if args.notes:
        notes = generate_notes(profiles)
        dump(config.ACCOUNT_NOTES, notes)
        print(f"{len(notes)}/{len(profiles)} LLM notes -> {config.ACCOUNT_NOTES}")


if __name__ == "__main__":
    main()
