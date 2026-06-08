"""Milestone 3 entry point: ingest all sources, chunk them, write chunks.jsonl.

Run from the src/ directory:  python build_chunks.py
"""

import json

from chunk import (
    chunk_csv_records,
    chunk_prose,
    chunk_ranking_rows,
)
from config import CHUNKS_PATH, PROCESSED_DIR, RAW_DIR, SOURCES
from ingest import load_csv_rows, load_pdf_raw_text, load_pdf_text


def build_for_source(meta):
    path = RAW_DIR / meta["file"]
    if not path.exists():
        print(f"  !! MISSING FILE: {path.name}")
        return []

    kind = meta["kind"]
    if kind == "csv":
        return chunk_csv_records(load_csv_rows(path), meta)
    if kind == "ranking_pdf":
        return chunk_ranking_rows(load_pdf_raw_text(path, meta["pages"]), meta)

    drop_garbage = kind == "who_profile"
    text = load_pdf_text(path, pages=meta["pages"], drop_garbage=drop_garbage)
    return chunk_prose(text, meta)


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks, per_source = [], []

    for meta in SOURCES:
        chunks = build_for_source(meta)
        all_chunks.extend(chunks)
        lengths = [len(c["text"]) for c in chunks]
        avg = round(sum(lengths) / len(lengths)) if lengths else 0
        mx = max(lengths) if lengths else 0
        per_source.append((meta["id"], len(chunks), avg, mx))

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"{'source_id':<32}{'chunks':>8}{'avg_chars':>11}{'max_chars':>11}")
    print("-" * 62)
    for sid, n, avg, mx in per_source:
        flag = "  <-- over ~256 tok?" if mx > 1100 else ""
        print(f"{sid:<32}{n:>8}{avg:>11}{mx:>11}{flag}")
    print("-" * 62)
    print(f"{'TOTAL':<32}{len(all_chunks):>8}")
    print(f"\nWrote {len(all_chunks)} chunks -> {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
