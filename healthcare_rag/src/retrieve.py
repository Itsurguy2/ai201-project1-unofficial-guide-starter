"""Stage 4: Retrieval.

retrieve(query, k) embeds the query with the same model used for indexing and
returns the top-k most similar chunks from ChromaDB, with source metadata.

Run from src/ as a smoke test:  python retrieve.py
(prints the retrieved sources for each of the 5 evaluation questions)
"""

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL_NAME, TOP_K

_model = None
_collection = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def _to_hit(doc, meta, dist):
    return {
        "text": doc,
        "source": meta["source"],
        "source_id": meta["source_id"],
        "url": meta["url"],
        "year": meta["year"],
        "similarity": round(1 - dist, 3),   # cosine distance -> similarity
    }


def retrieve(query: str, k: int = TOP_K, max_per_source: int = 2) -> list[dict]:
    """Return the top-k chunks for a query, with a per-source diversity cap.

    Over-fetches a candidate pool, then takes the best chunks while allowing at
    most `max_per_source` from any single source. This stops one source's
    near-duplicate chunks (e.g. the OECD CSV's Belgium-across-years records) from
    crowding out the other half of a cross-source comparison. If the cap leaves
    fewer than k, remaining slots are filled with the next-best candidates.
    """
    q_emb = _get_model().encode([query], normalize_embeddings=True)[0].tolist()
    # Pool must be large enough that distinct sources enter before the per-source
    # cap applies; the OECD CSV's ~500 near-identical records otherwise flood it.
    pool = max(k * 12, 60)
    res = _get_collection().query(
        query_embeddings=[q_emb],
        n_results=pool,
        include=["documents", "metadatas", "distances"],
    )
    candidates = [
        _to_hit(d, m, dist)
        for d, m, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]

    selected, counts, leftovers = [], {}, []
    for hit in candidates:
        sid = hit["source_id"]
        if counts.get(sid, 0) < max_per_source:
            selected.append(hit)
            counts[sid] = counts.get(sid, 0) + 1
        else:
            leftovers.append(hit)
        if len(selected) == k:
            return selected
    # Cap left us short (too few distinct sources): backfill by similarity.
    selected.extend(leftovers[: k - len(selected)])
    return selected


# The 5 evaluation questions from planning.md (used for the smoke test).
TEST_QUESTIONS = [
    "How much did annual family premiums for employer health coverage cost in 2025, and how much did workers contribute?",
    "What is the primary driver of higher U.S. health spending compared to peer countries?",
    "How much more do Americans pay for prescription drugs than other developed countries?",
    "What share of GDP does the U.S. spend on health, and how does it compare to Belgium?",
    "Which countries have not achieved universal health coverage according to the Commonwealth Fund?",
]


if __name__ == "__main__":
    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"\nQ{i}: {q}")
        for r in retrieve(q):
            print(f"   [{r['similarity']:.3f}] {r['source_id']:<28} {r['text'][:90]}")
