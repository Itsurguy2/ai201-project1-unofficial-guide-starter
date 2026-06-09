"""Stretch Feature B: chunking strategy comparison.

Holds corpus + embedding model + retrieval constant and varies ONLY the prose
chunker, then measures gold-source recall@k on the 5 evaluation questions.

Strategies (prose path only; record/ranking chunks are held fixed):
  - sentence_400_60   small sentence-aware (~100 tokens)
  - sentence_800_120  the current production strategy (~200 tokens)
  - fixed_1600_0      naive 1600-char windows: exceeds MiniLM's 256-token limit
                      on purpose to expose silent truncation

Each strategy is embedded into a fresh in-memory ChromaDB collection so nothing
touches the persistent store. Retrieval reuses the same top-k + per-source cap.

Run from src/:  python compare_chunking.py   (loads the model once; ~1 min)
"""

import chromadb
from sentence_transformers import SentenceTransformer

import chunk as chunk_mod
from chunk import chunk_csv_records, chunk_prose, chunk_ranking_rows, _make_chunk
from compare_search import GOLD, gold_ranks
from config import EMBED_MODEL_NAME, RAW_DIR, SOURCES, TOP_K
from ingest import load_csv_rows, load_pdf_raw_text, load_pdf_text
from retrieve import TEST_QUESTIONS

PROSE_KINDS = {"prose", "who_profile"}


def chunk_fixed(text, meta, size, overlap):
    """Naive fixed-width character windows (no sentence/word awareness)."""
    text = chunk_mod._WS_RE.sub(" ", text).strip()
    chunks, idx, start, step = [], 0, 0, max(size - overlap, 1)
    while start < len(text):
        chunks.append(_make_chunk(text[start:start + size], meta, idx))
        idx += 1
        start += step
    return chunks


def build_prose_chunks(meta, strategy):
    """Load + prose-chunk one source under the named strategy."""
    path = RAW_DIR / meta["file"]
    text = load_pdf_text(
        path, pages=meta["pages"], drop_garbage=meta["kind"] == "who_profile"
    )
    if strategy == "sentence_400_60":
        chunk_mod.PROSE_TARGET_CHARS, chunk_mod.PROSE_OVERLAP_CHARS = 400, 60
        return chunk_prose(text, meta)
    if strategy == "sentence_800_120":
        chunk_mod.PROSE_TARGET_CHARS, chunk_mod.PROSE_OVERLAP_CHARS = 800, 120
        return chunk_prose(text, meta)
    if strategy == "fixed_1600_0":
        return chunk_fixed(text, meta, size=1600, overlap=0)
    raise ValueError(strategy)


def build_fixed_record_chunks():
    """The atomic record/ranking chunks — identical across all strategies."""
    out = []
    for meta in SOURCES:
        path = RAW_DIR / meta["file"]
        if not path.exists():
            continue
        if meta["kind"] == "csv":
            out.extend(chunk_csv_records(load_csv_rows(path), meta))
        elif meta["kind"] == "ranking_pdf":
            out.extend(chunk_ranking_rows(load_pdf_raw_text(path, meta["pages"]), meta))
    return out


def build_all(strategy, fixed_records):
    chunks = list(fixed_records)
    for meta in SOURCES:
        if meta["kind"] in PROSE_KINDS and (RAW_DIR / meta["file"]).exists():
            chunks.extend(build_prose_chunks(meta, strategy))
    return chunks


def index(model, chunks, name):
    """Embed chunks into a fresh in-memory cosine collection."""
    client = chromadb.EphemeralClient()
    col = client.create_collection(name, metadata={"hnsw:space": "cosine"})
    embs = model.encode(
        [c["text"] for c in chunks], batch_size=64, normalize_embeddings=True
    )
    col.add(
        ids=[c["id"] for c in chunks],
        embeddings=embs.tolist(),
        metadatas=[{"source_id": c["source_id"]} for c in chunks],
    )
    return col


def retrieve(model, col, query, k=TOP_K, max_per_source=2):
    """Top-k with the same per-source diversity cap used in production."""
    q = model.encode([query], normalize_embeddings=True)[0].tolist()
    res = col.query(query_embeddings=[q], n_results=max(k * 12, 60),
                    include=["metadatas"])
    selected, counts, leftovers = [], {}, []
    for m in res["metadatas"][0]:
        sid = m["source_id"]
        hit = {"source_id": sid}
        if counts.get(sid, 0) < max_per_source:
            selected.append(hit)
            counts[sid] = counts.get(sid, 0) + 1
        else:
            leftovers.append(hit)
        if len(selected) == k:
            break
    selected.extend(leftovers[: k - len(selected)])
    return selected


def main():
    print(f"Loading model '{EMBED_MODEL_NAME}'...")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    fixed_records = build_fixed_record_chunks()

    strategies = ["sentence_400_60", "sentence_800_120", "fixed_1600_0"]
    summary = []

    for strat in strategies:
        chunks = build_all(strat, fixed_records)
        prose = [c for c in chunks if c["source_id"] not in
                 {"oecd_health_expenditure", "worldometer_life_expectancy"}]
        lengths = [len(c["text"]) for c in prose]
        avg = round(sum(lengths) / len(lengths)) if lengths else 0
        col = index(model, chunks, name=strat)

        print(f"\n### {strat}  ({len(chunks)} chunks, prose avg {avg} / "
              f"max {max(lengths) if lengths else 0} chars)")
        found = possible = rank_sum = rank_n = 0
        for i, q in enumerate(TEST_QUESTIONS, 1):
            hits = retrieve(model, col, q)
            ranks = gold_ranks(hits, GOLD[i])
            f = sum(1 for r in ranks.values() if r)
            found += f
            possible += len(GOLD[i])
            for r in ranks.values():
                if r:
                    rank_sum += r
                    rank_n += 1
            detail = "  ".join(f"{g}@{r or '-'}" for g, r in ranks.items())
            print(f"   Q{i} {f}/{len(GOLD[i])}   [{detail}]")
        avg_rank = round(rank_sum / rank_n, 2) if rank_n else None
        summary.append((strat, len(chunks), avg, found, possible, avg_rank))

    print("\n" + "=" * 72)
    print(f"{'strategy':<20}{'chunks':>8}{'prose_avg':>11}{'recall@k':>12}{'avg_gold_rank':>16}")
    print("-" * 72)
    for strat, n, avg, f, p, ar in summary:
        print(f"{strat:<20}{n:>8}{avg:>11}{f'{f}/{p}':>12}{str(ar):>16}")
    best = max(summary, key=lambda s: (s[3], -(s[5] or 99)))
    print("-" * 72)
    print(f"WINNER: {best[0]}  (recall {best[3]}/{best[4]}, avg gold rank {best[5]})")


if __name__ == "__main__":
    main()
