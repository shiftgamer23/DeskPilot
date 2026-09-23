"""One-time build: embed every corpus ticket with MiniLM and store the vectors in a persistent Chroma collection.

Run: python -m app.tools.build_index
Rerun whenever the corpus changes (e.g. eval/build_eval_slice.py was rerun with different sizes/seed).
"""
import chromadb
from sentence_transformers import SentenceTransformer

from app import config
from app.tools.corpus import load_corpus

BATCH = 256


def main() -> None:
    corpus = load_corpus()
    print(f"Embedding {len(corpus)} corpus tickets with {config.EMBEDDING_MODEL}...")

    model = SentenceTransformer(config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    client.delete_collection(config.CHROMA_COLLECTION) if config.CHROMA_COLLECTION in {
        c.name for c in client.list_collections()
    } else None
    collection = client.create_collection(config.CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})

    meta_cols = ["queue", "type", "priority", "tag_1", "tag_2", "subject", "answer"]
    for start in range(0, len(corpus), BATCH):
        batch = corpus.iloc[start : start + BATCH]
        embeddings = model.encode(batch["text"].tolist(), show_progress_bar=False, normalize_embeddings=True)
        collection.add(
            ids=batch["ticket_id"].tolist(),
            embeddings=embeddings.tolist(),
            documents=batch["text"].tolist(),
            metadatas=[
                {c: (row[c] if isinstance(row[c], str) else "") for c in meta_cols} for _, row in batch.iterrows()
            ],
        )
        print(f"  {min(start + BATCH, len(corpus))}/{len(corpus)}")

    print(f"Done. {collection.count()} vectors -> {config.CHROMA_DIR}")


if __name__ == "__main__":
    main()
