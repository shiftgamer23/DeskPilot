"""Carve the English tickets into disjoint dev / held-out eval / retrieval-corpus sets (seeded, stratified by queue).

- eval:   final held-out slice, used only for the reported numbers
- dev:    tuning slice for prompt / gate iteration
- corpus: everything else - the only tickets `search_past_tickets` may index, so eval tickets can never
          retrieve themselves (or their own resolution).

Flagship-scenario anchor tickets are excluded from dev/eval so they always live in the corpus.

Run: python eval/build_eval_slice.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config
from app.data_loader import load_tickets
from app.flagship import RESERVED_TICKET_IDS

N_EVAL, N_DEV = 100, 60
MIN_PER_QUEUE = 3  # keep rare queues (e.g. General Inquiry) represented


def stratified_sample(df, n: int, rng: random.Random) -> list[str]:
    picked: list[str] = []
    for _, grp in sorted(df.groupby("queue"), key=lambda kv: kv[0]):
        k = max(MIN_PER_QUEUE, round(n * len(grp) / len(df)))
        picked += rng.sample(sorted(grp["ticket_id"]), k)
    return sorted(picked)


def main() -> None:
    tickets = load_tickets()
    ids = set(tickets["ticket_id"])
    missing = set(RESERVED_TICKET_IDS) - ids
    assert not missing, f"Flagship anchor tickets not in dataset: {missing}"

    rng = random.Random(config.SEED)
    pool = tickets[~tickets["ticket_id"].isin(RESERVED_TICKET_IDS)]
    eval_ids = stratified_sample(pool, N_EVAL, rng)
    dev_ids = stratified_sample(pool[~pool["ticket_id"].isin(eval_ids)], N_DEV, rng)
    held_out = set(eval_ids) | set(dev_ids)
    corpus_ids = sorted(ids - held_out)
    assert not set(eval_ids) & set(dev_ids)

    config.SPLITS.parent.mkdir(parents=True, exist_ok=True)
    config.SPLITS.write_text(
        json.dumps({"seed": config.SEED, "eval": eval_ids, "dev": dev_ids, "corpus": corpus_ids}, indent=1),
        encoding="utf-8",
    )
    print(f"eval={len(eval_ids)} dev={len(dev_ids)} corpus={len(corpus_ids)} -> {config.SPLITS}")


if __name__ == "__main__":
    main()
