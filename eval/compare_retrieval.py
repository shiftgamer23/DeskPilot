"""LLM-free retrieval quality comparison: bm25 vs vector vs hybrid.

For every held-out eval ticket, retrieve top-k past tickets under each mode and check how often those
results' queue/tag_1 agree with the eval ticket's real (already-known) label. No LLM calls - this only
tests the retrieval step, not the agent's decisions (that's Phase 5).

Metrics, per mode, averaged over all eval tickets:
  top1_queue_acc  - does the single best match share the eval ticket's queue?
  top1_tag1_acc   - same, for tag_1 (finer-grained)
  precision@5_queue - of the top-5 matches, what fraction share the queue?
  precision@5_tag1  - of the top-5 matches, what fraction share tag_1?

Run: python eval/compare_retrieval.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config
from app.data_loader import load_tickets
from app.tools.search_past_tickets import _MODES, search_past_tickets

K = 5
RESULTS_PATH = Path(__file__).parent / "results" / "retrieval_comparison.json"


def evaluate_mode(mode: str, eval_tickets) -> dict:
    top1_queue = top1_tag1 = prec_queue = prec_tag1 = 0.0
    n = len(eval_tickets)
    for _, ticket in eval_tickets.iterrows():
        hits = search_past_tickets(ticket["text"], mode=mode, k=K)
        if not hits:
            continue
        top1_queue += hits[0]["queue"] == ticket["queue"]
        top1_tag1 += hits[0]["tag_1"] == ticket["tag_1"]
        prec_queue += sum(h["queue"] == ticket["queue"] for h in hits) / len(hits)
        prec_tag1 += sum(h["tag_1"] == ticket["tag_1"] for h in hits) / len(hits)
    return {
        "top1_queue_acc": round(top1_queue / n, 3),
        "top1_tag1_acc": round(top1_tag1 / n, 3),
        f"precision@{K}_queue": round(prec_queue / n, 3),
        f"precision@{K}_tag1": round(prec_tag1 / n, 3),
    }


def main() -> None:
    splits = json.loads(config.SPLITS.read_text(encoding="utf-8"))
    tickets = load_tickets()
    eval_tickets = tickets[tickets["ticket_id"].isin(set(splits["eval"]))]
    print(f"Comparing retrieval modes on {len(eval_tickets)} held-out eval tickets (k={K})...\n")

    results = {}
    for mode in _MODES:
        print(f"  running {mode}...")
        results[mode] = evaluate_mode(mode, eval_tickets)

    print(f"\n{'mode':8s} {'top1_queue':>11s} {'top1_tag1':>10s} {'prec@5_queue':>13s} {'prec@5_tag1':>12s}")
    for mode, m in results.items():
        print(
            f"{mode:8s} {m['top1_queue_acc']:>11.3f} {m['top1_tag1_acc']:>10.3f} "
            f"{m[f'precision@{K}_queue']:>13.3f} {m[f'precision@{K}_tag1']:>12.3f}"
        )

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"k": K, "n_eval": len(eval_tickets), **results}, indent=1), encoding="utf-8")
    print(f"\nSaved -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
