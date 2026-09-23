"""The retrieval corpus: real, resolved English tickets minus everything held out for dev/eval/flagship.

Shared by the index-build script and both retrieval tools, so they can never drift out of sync with
what eval/build_eval_slice.py decided was "corpus".
"""
import json

import pandas as pd

from app import config
from app.data_loader import load_tickets


def load_corpus() -> pd.DataFrame:
    splits = json.loads(config.SPLITS.read_text(encoding="utf-8"))
    tickets = load_tickets()
    corpus = tickets[tickets["ticket_id"].isin(set(splits["corpus"]))].reset_index(drop=True)
    assert len(corpus) == len(splits["corpus"]), "corpus size mismatch - rerun build_eval_slice.py?"
    return corpus
