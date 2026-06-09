# Add four stretch features: hybrid search, chunking comparison, metadata filtering, conversational memory

## Summary

Implements all four extra-credit stretch features from the project brief. Each
was specced in `planning.md` *before* implementation, and each ships with
measured results against the live pipeline (not just claims).

## Features

### A. Hybrid Search (BM25 + semantic)
- `hybrid.py`: pure-Python BM25 (Okapi) over the existing `chunks.jsonl` corpus —
  **no new dependency** — fused with the semantic ChromaDB search via Reciprocal
  Rank Fusion. Single entry point `search(query, k, mode)` with
  `mode ∈ {semantic, bm25, hybrid}`, keeping the per-source diversity cap.
- `compare_search.py` scores semantic vs hybrid by gold-source recall@k.
- **Result:** both recover 5/6 gold sources; hybrid improves Q2 rank (3→2). Q4's
  `who_usa` chunk still eludes both — documented gap, not over-tuned.

### B. Chunking Strategy Comparison
- `compare_chunking.py` holds corpus/model/retrieval constant and varies only the
  prose chunker across 3 strategies, embedding each into an in-memory Chroma
  collection.

  | strategy | recall@k | avg gold rank |
  |---|---|---|
  | sentence_400_60 | 5/6 | 1.6 |
  | **sentence_800_120 (prod)** | 5/6 | **1.4** |
  | fixed_1600_0 | 5/6 | 1.4 |

  Production size wins on precision (small chunks dropped Q3 to rank 2). Honest
  caveat recorded: `fixed_1600_0` didn't collapse despite truncation only because
  answer text sits early in its chunks.

### C. Metadata Filtering
- `filters = {source_ids, min_year, max_year}` applied uniformly across all search
  modes — a Chroma `where` clause for the semantic path, a Python predicate for
  BM25. Verified source-restriction, year cutoff, and graceful empty-result
  handling.

### D. Conversational Memory (multi-turn)
- `generate.py` adds `condense_query()`: history-aware rewriting of elliptical
  follow-ups into standalone questions before retrieval (skipped on the first
  turn). Verified that "How does that compare to Belgium?" is rewritten to name
  "U.S." + "GDP" and pulls Belgium's OECD rows into context.

### UI
- `app.py`: search-mode radio, source multiselect, "published since" year slider,
  chat-history threading, and a note showing the rewritten query when memory
  changes it.

## Notes
- `generate.answer()` now defaults to `mode="hybrid"` (was plain semantic), so the
  Milestone-5 CLI uses the stronger retriever.
- Cross-source Q4-style comparisons remain bounded by the documented retrieval gap
  (the matching clean U.S.-% chunk doesn't co-occur with Belgium rows under the
  per-source cap).

## Test plan
- `python compare_search.py` — semantic vs hybrid recall@k
- `python compare_chunking.py` — 3-strategy chunking comparison
- `python generate.py "..."` — grounded answer via hybrid retrieval
- `python app.py` — full UI with all controls
