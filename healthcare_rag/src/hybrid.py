"""Stretch Feature A: Hybrid search (BM25 + semantic), fused with RRF.

Three retrieval modes through one entry point, `search(query, k, mode)`:
  - "semantic": dense MiniLM + ChromaDB cosine (the existing retrieve() path).
  - "bm25":     sparse lexical BM25 (Okapi) over the same chunks.jsonl corpus.
  - "hybrid":   Reciprocal Rank Fusion of the two ranked lists.

BM25 is implemented in pure Python (no extra dependency). RRF is rank-based, so
it needs no score normalization between cosine similarity and BM25 term scores.
The same per-source diversity cap used by retrieve() is applied after fusion.

CLI smoke test:  python hybrid.py            # prints hybrid hits per question
                 python hybrid.py "query"    # one query, all three modes
"""

import json
import math
import re
import sys
from collections import Counter, defaultdict

import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    CHROMA_DIR,
    CHUNKS_PATH,
    COLLECTION_NAME,
    EMBED_MODEL_NAME,
    TOP_K,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# --- BM25 (Okapi) --------------------------------------------------------
class BM25:
    """Minimal BM25-Okapi ranker over an in-memory list of documents."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = corpus_tokens
        self.doc_len = [len(toks) for toks in corpus_tokens]
        self.n_docs = len(corpus_tokens)
        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0
        self.doc_freqs = [Counter(toks) for toks in corpus_tokens]

        df = Counter()
        for toks in corpus_tokens:
            for term in set(toks):
                df[term] += 1
        # BM25+ style idf, floored at 0 to avoid negative weights on common terms.
        self.idf = {
            term: max(math.log((self.n_docs - n + 0.5) / (n + 0.5) + 1.0), 0.0)
            for term, n in df.items()
        }

    def scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.n_docs
        for term in query_tokens:
            idf = self.idf.get(term)
            if not idf:
                continue
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(term)
                if not tf:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * (tf * (self.k1 + 1) / denom)
        return scores


# --- lazy singletons -----------------------------------------------------
_model = None
_collection = None
_chunks = None
_bm25 = None


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


def _get_chunks() -> list[dict]:
    global _chunks
    if _chunks is None:
        with open(CHUNKS_PATH, encoding="utf-8") as f:
            _chunks = [json.loads(line) for line in f]
    return _chunks


def _get_bm25() -> BM25:
    global _bm25
    if _bm25 is None:
        _bm25 = BM25([_tokenize(c["text"]) for c in _get_chunks()])
    return _bm25


# --- metadata filtering (Feature C) --------------------------------------
def build_where(filters: dict | None) -> dict | None:
    """Translate a filter spec into a ChromaDB `where` clause (or None)."""
    if not filters:
        return None
    clauses = []
    if filters.get("source_ids"):
        clauses.append({"source_id": {"$in": list(filters["source_ids"])}})
    if filters.get("min_year") is not None:
        clauses.append({"year": {"$gte": int(filters["min_year"])}})
    if filters.get("max_year") is not None:
        clauses.append({"year": {"$lte": int(filters["max_year"])}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _passes_filter(chunk: dict, filters: dict | None) -> bool:
    """Python equivalent of build_where(), for the BM25 candidate list."""
    if not filters:
        return True
    if filters.get("source_ids") and chunk["source_id"] not in filters["source_ids"]:
        return False
    if filters.get("min_year") is not None and chunk["year"] < filters["min_year"]:
        return False
    if filters.get("max_year") is not None and chunk["year"] > filters["max_year"]:
        return False
    return True


def _chunk_to_hit(chunk: dict) -> dict:
    """Shape a chunks.jsonl record like retrieve()'s hit dicts."""
    return {
        "text": chunk["text"],
        "source": chunk["source"],
        "source_id": chunk["source_id"],
        "url": chunk["url"],
        "year": chunk["year"],
    }


def _apply_source_cap(hits: list[dict], k: int, max_per_source: int) -> list[dict]:
    """Keep best hits while allowing <= max_per_source from any one source."""
    selected, counts, leftovers = [], defaultdict(int), []
    for hit in hits:
        sid = hit["source_id"]
        if counts[sid] < max_per_source:
            selected.append(hit)
            counts[sid] += 1
        else:
            leftovers.append(hit)
        if len(selected) == k:
            return selected
    selected.extend(leftovers[: k - len(selected)])
    return selected


def _semantic_ranking(query: str, pool: int, filters: dict | None = None) -> list[dict]:
    """Top `pool` chunks by cosine similarity, best-first (optionally filtered)."""
    q_emb = _get_model().encode([query], normalize_embeddings=True)[0].tolist()
    where = build_where(filters)
    res = _get_collection().query(
        query_embeddings=[q_emb],
        n_results=pool,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    if not res["documents"] or not res["documents"][0]:
        return []
    hits = []
    for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append(
            {
                "text": d,
                "source": m["source"],
                "source_id": m["source_id"],
                "url": m["url"],
                "year": m["year"],
                "similarity": round(1 - dist, 3),
            }
        )
    return hits


def _bm25_ranking(query: str, pool: int, filters: dict | None = None) -> list[dict]:
    """Top `pool` chunks by BM25 score, best-first (zero-score docs dropped)."""
    chunks = _get_chunks()
    scores = _get_bm25().scores(_tokenize(query))
    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    hits = []
    for i in ranked:
        if scores[i] <= 0 or len(hits) >= pool:
            break
        if not _passes_filter(chunks[i], filters):
            continue
        hit = _chunk_to_hit(chunks[i])
        hit["bm25"] = round(scores[i], 3)
        hits.append(hit)
    return hits


def _rrf_fuse(rankings: list[list[dict]], rrf_k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion over several ranked hit lists, keyed by chunk text."""
    fused: dict[str, dict] = {}
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            key = hit["text"]
            scores[key] += 1.0 / (rrf_k + rank)
            fused.setdefault(key, hit)
    ordered = sorted(fused.values(), key=lambda h: scores[h["text"]], reverse=True)
    for h in ordered:
        h["rrf"] = round(scores[h["text"]], 5)
    return ordered


def search(
    query: str,
    k: int = TOP_K,
    mode: str = "hybrid",
    max_per_source: int = 2,
    filters: dict | None = None,
) -> list[dict]:
    """Retrieve top-k chunks for a query under the given mode.

    mode: "semantic" | "bm25" | "hybrid". `filters` optionally restricts results
    by source_ids / min_year / max_year (see build_where). The per-source
    diversity cap is applied after ranking/fusion so one source's near-duplicates
    can't dominate top-k.
    """
    pool = max(k * 12, 60)
    if mode == "semantic":
        ranked = _semantic_ranking(query, pool, filters)
    elif mode == "bm25":
        ranked = _bm25_ranking(query, pool, filters)
    elif mode == "hybrid":
        ranked = _rrf_fuse([
            _semantic_ranking(query, pool, filters),
            _bm25_ranking(query, pool, filters),
        ])
    else:
        raise ValueError(f"unknown mode: {mode!r} (use semantic|bm25|hybrid)")
    return _apply_source_cap(ranked, k, max_per_source)


if __name__ == "__main__":
    from retrieve import TEST_QUESTIONS

    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        for mode in ("semantic", "bm25", "hybrid"):
            print(f"\n=== {mode.upper()} :: {q}")
            for r in search(q, mode=mode):
                print(f"   {r['source_id']:<28} {r['text'][:80]}")
    else:
        for i, q in enumerate(TEST_QUESTIONS, 1):
            print(f"\nQ{i} (hybrid): {q}")
            for r in search(q, mode="hybrid"):
                print(f"   {r['source_id']:<28} {r['text'][:80]}")
