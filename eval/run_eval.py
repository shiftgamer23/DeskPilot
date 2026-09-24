"""Phase 5: run the held-out eval slice through the full agent pipeline and score it against real
historical outcomes. Repeatable - results are saved to eval/results/ for before/after comparison as the
project evolves.

Escalation behavior (the flagship scenarios, especially the deliberately ambiguous one) is reported
separately from raw queue/type/priority accuracy, not folded into one number - per the plan, whether the
agent actually escalates instead of guessing is as important a result as accuracy.

Run: python eval/run_eval.py [--provider groq] [--workers 3] [--limit N]
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config
from app.agent.triage_agent import triage
from app.data_loader import load_tickets
from app.flagship import FLAGSHIP_SCENARIOS
from app.infra import tracing

RESULTS_DIR = Path(__file__).parent / "results"


def run_one(ticket_id: str, row, customer_id: str | None, provider: str) -> dict:
    t0 = time.time()
    try:
        result = triage(row["subject"], row["body"], customer_id=customer_id, provider=provider)
        error = None
    except Exception as e:
        result, error = None, f"{type(e).__name__}: {e}"
    return {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "real_queue": row["queue"], "real_type": row["type"], "real_priority": row["priority"],
        "real_tag_1": row["tag_1"], "real_tag_2": row["tag_2"],
        "result": result, "error": error, "latency_s": round(time.time() - t0, 2),
    }


def run_eval_slice(provider: str, workers: int, limit: int | None) -> list[dict]:
    splits = json.loads(config.SPLITS.read_text(encoding="utf-8"))
    ticket_customers = json.loads(config.TICKET_CUSTOMERS.read_text(encoding="utf-8"))
    tickets = load_tickets().set_index("ticket_id")

    eval_ids = splits["eval"][:limit] if limit else splits["eval"]
    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(run_one, tid, tickets.loc[tid], ticket_customers.get(tid), provider): tid for tid in eval_ids
        }
        for fut in as_completed(futures):
            rows.append(fut.result())
            done += 1
            if done % 10 == 0 or done == len(eval_ids):
                print(f"  {done}/{len(eval_ids)} done")
    return rows


def run_flagship(provider: str) -> list[dict]:
    out = []
    for s in FLAGSHIP_SCENARIOS:
        result = triage(s["subject"], s["body"], customer_id=s["customer_id"], provider=provider)
        out.append({"id": s["id"], "expected_action": s["expected_action"], "result": result,
                    "passed": result["action"] == s["expected_action"]})
    return out


def summarize(rows: list[dict]) -> dict:
    errored = [r for r in rows if r["error"] is not None]
    # A turn-limit fallback (see app/agent/graph.py::fallback_node) is not a real decision - most commonly
    # caused by the LLM provider's rate/quota limit rejecting every call for that ticket. triage() doesn't
    # raise in that case (it's a deliberate safety net), so these look like ordinary rows unless filtered
    # out explicitly here - left in, they'd silently masquerade as low-confidence "escalate" decisions.
    system_failures = [r for r in rows if r["error"] is None and r["result"]["gate_reason"] == "turn_limit_exceeded"]
    ok = [r for r in rows if r["error"] is None and r["result"]["gate_reason"] != "turn_limit_exceeded"]
    n, errors = len(ok), len(errored)
    if n == 0:
        return {"n": 0, "errors": errors, "system_failures": len(system_failures)}

    queue_hit = [r["result"]["queue"] == r["real_queue"] for r in ok]
    type_hit = [r["result"]["type"] == r["real_type"] for r in ok]
    priority_hit = [r["result"]["priority"] == r["real_priority"] for r in ok]

    by_tag: dict[str, list[bool]] = defaultdict(list)
    for r, hit in zip(ok, queue_hit):
        by_tag[r["real_tag_1"]].append(hit)

    auto = [r for r in ok if r["result"]["action"] == "auto_resolve"]
    auto_hit = [r["result"]["queue"] == r["real_queue"] for r in auto]

    correct_conf = [r["result"]["confidence"] for r, hit in zip(ok, queue_hit) if hit]
    incorrect_conf = [r["result"]["confidence"] for r, hit in zip(ok, queue_hit) if not hit]

    return {
        "n": n,
        "errors": errors,
        "system_failures": len(system_failures),
        "action_distribution": dict(Counter(r["result"]["action"] for r in ok)),
        "queue_accuracy": round(sum(queue_hit) / n, 3),
        "type_accuracy": round(sum(type_hit) / n, 3),
        "priority_accuracy": round(sum(priority_hit) / n, 3),
        "queue_accuracy_by_tag_1": {tag: round(sum(v) / len(v), 3) for tag, v in sorted(by_tag.items())},
        "auto_resolve_rate": round(len(auto) / n, 3),
        "auto_resolve_queue_accuracy": round(sum(auto_hit) / len(auto), 3) if auto else None,
        "gate_overridden_rate": round(sum(r["result"]["gate_overridden"] for r in ok) / n, 3),
        "avg_confidence": round(sum(r["result"]["confidence"] for r in ok) / n, 3),
        "avg_confidence_when_queue_correct": round(sum(correct_conf) / len(correct_conf), 3) if correct_conf else None,
        "avg_confidence_when_queue_wrong": round(sum(incorrect_conf) / len(incorrect_conf), 3) if incorrect_conf else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="use only the first N eval tickets (quick run)")
    args = parser.parse_args()

    print("=== Flagship scenarios (escalation behavior) ===")
    flagship = run_flagship(args.provider)
    for f in flagship:
        status = "PASS" if f["passed"] else "FAIL"
        print(f"  {f['id']:18s} expected={f['expected_action']:12s} got={f['result']['action']:12s} {status}")

    print(f"\n=== Eval slice ({args.provider}, workers={args.workers}) ===")
    t0 = time.time()
    rows = run_eval_slice(args.provider, args.workers, args.limit)
    elapsed = round(time.time() - t0, 1)

    summary = summarize(rows)
    summary["provider"], summary["elapsed_s"] = args.provider, elapsed
    summary["flagship"] = {"pass_count": sum(f["passed"] for f in flagship), "total": len(flagship),
                            "details": [{"id": f["id"], "passed": f["passed"]} for f in flagship]}

    print(f"\n{json.dumps(summary, indent=2)}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"summary": summary, "rows": rows, "flagship": flagship}, indent=1, default=str)
    ts = time.strftime("%Y%m%d_%H%M%S")
    (RESULTS_DIR / f"eval_{ts}.json").write_text(payload, encoding="utf-8")
    (RESULTS_DIR / "latest.json").write_text(payload, encoding="utf-8")
    print(f"\nSaved -> eval/results/eval_{ts}.json (and latest.json)")

    tracing.flush()  # short-lived script - make sure buffered traces are sent before exit


if __name__ == "__main__":
    main()
