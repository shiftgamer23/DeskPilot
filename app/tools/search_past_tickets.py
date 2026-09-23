"""Tool: search_past_tickets(query, mode, k) -> similar past tickets + their real resolutions.

Three retrieval modes over the same corpus (see app/tools/corpus.py):
  bm25   - keyword overlap (rank_bm25). Exact wording matches; no semantic understanding.
  vector - MiniLM embeddings in Chroma. Catches paraphrase; no exact-keyword guarantee.
  hybrid - both ranked lists merged with Reciprocal Rank Fusion (default; usually the safest choice).

Every result carries a `score`: cosine similarity in [0,1] for vector, RRF score for hybrid (not directly
comparable to the other modes' scores - it's a rank-fusion score, not a similarity). This is what the
confidence gate reads later - a low top score means "nothing like this on record".
"""
import re
from functools import lru_cache

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app import config
from app.tools.corpus import load_corpus

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _Index:
    """Loaded once per process; every _Index() call after the first is a no-op cache hit."""

    def __init__(self):
        self.corpus = load_corpus()
        self.ids = self.corpus["ticket_id"].tolist()
        self.bm25 = BM25Okapi([_tokenize(t) for t in self.corpus["text"]])
        self.embedder = SentenceTransformer(config.EMBEDDING_MODEL)
        self.collection = chromadb.PersistentClient(path=str(config.CHROMA_DIR)).get_collection(
            config.CHROMA_COLLECTION
        )
        assert self.collection.count() == len(self.corpus), (
            "Chroma index is stale vs. the corpus - rerun `python -m app.tools.build_index`"
        )


@lru_cache(maxsize=1)
def _index() -> _Index:
    return _Index()


def _row(ticket_id: str, score: float, rank: int) -> dict:
    r = _index().corpus.set_index("ticket_id").loc[ticket_id]
    return {
        "ticket_id": ticket_id,
        "rank": rank,
        "score": round(float(score), 4),
        "subject": r["subject"] if isinstance(r["subject"], str) else None,
        "body": r["body"],
        "answer": r["answer"],
        "queue": r["queue"],
        "type": r["type"],
        "priority": r["priority"],
        "tag_1": r["tag_1"],
        "tag_2": r["tag_2"],
    }


def _search_bm25(query: str, k: int) -> list[tuple[str, float]]:
    idx = _index()
    scores = idx.bm25.get_scores(_tokenize(query))
    top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [(idx.ids[i], scores[i]) for i in top]


def _search_vector(query: str, k: int) -> list[tuple[str, float]]:
    idx = _index()
    q_emb = idx.embedder.encode([query], normalize_embeddings=True).tolist()
    res = idx.collection.query(query_embeddings=q_emb, n_results=k)
    # Chroma (cosine space) returns a distance in [0,2]; similarity = 1 - distance/2.
    return [(tid, 1 - dist / 2) for tid, dist in zip(res["ids"][0], res["distances"][0])]


def _search_hybrid(query: str, k: int, rrf_k: int = 60) -> list[tuple[str, float]]:
    # Reciprocal Rank Fusion: a ticket's score is 1/(rrf_k + rank) summed over every list it appears in.
    # Rewards showing up near the top of *either* ranking; needs no score normalization between them.
    pool_size = max(k * 4, 20)
    fused: dict[str, float] = {}
    for ranked in (_search_bm25(query, pool_size), _search_vector(query, pool_size)):
        for rank, (tid, _) in enumerate(ranked, start=1):
            fused[tid] = fused.get(tid, 0.0) + 1 / (rrf_k + rank)
    return sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]


_MODES = {"bm25": _search_bm25, "vector": _search_vector, "hybrid": _search_hybrid}


def search_past_tickets(query: str, mode: str = "hybrid", k: int = 5) -> list[dict]:
    """Find the k most similar past resolved tickets. `query` is normally the incoming ticket's subject+body."""
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {list(_MODES)}, got {mode!r}")
    if not query or not query.strip():
        return []
    ranked = _MODES[mode](query, k)
    return [_row(tid, score, rank) for rank, (tid, score) in enumerate(ranked, start=1)]


if __name__ == "__main__":
    import json

    for m in _MODES:
        hits = search_past_tickets("I can't log into my account, it keeps saying invalid password", mode=m, k=3)
        print(f"--- {m} ---")
        for h in hits:
            print(f"  {h['ticket_id']}  score={h['score']}  {h['queue']}/{h['tag_1']}  {h['subject']}")
