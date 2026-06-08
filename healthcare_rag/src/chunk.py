"""Stage 2: Hybrid chunking.

Two paths (see planning.md "Chunking Strategy"):
  - chunk_prose:    sentence-packed ~800-char chunks with ~120-char overlap.
  - chunk_csv_records / chunk_ranking_rows: one self-contained templated
    sentence per data row, no overlap.

Every chunk is a dict: {id, text, source, source_id, url, year, kind, chunk_index}.
"""

import re

from config import PROSE_OVERLAP_CHARS, PROSE_TARGET_CHARS

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WS_RE = re.compile(r"\s+")


def _make_chunk(text, meta, index):
    return {
        "id": f"{meta['id']}::{index}",
        "text": text.strip(),
        "source": meta["source"],
        "source_id": meta["id"],
        "url": meta["url"],
        "year": meta["year"],
        "kind": meta["kind"],
        "chunk_index": index,
    }


def _split_long_unit(unit):
    """Word-wrap a unit (a long, unpunctuated 'sentence') into <=target pieces.

    Tables and figure captions often extract without sentence punctuation, so a
    single split 'sentence' can be huge. We pack whole words up to the target so
    no piece ever exceeds it.
    """
    pieces, cur = [], ""
    for word in unit.split():
        if cur and len(cur) + 1 + len(word) > PROSE_TARGET_CHARS:
            pieces.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def _overlap_seed(text):
    """Last ~overlap chars of a chunk, trimmed to a word boundary (bounded)."""
    if len(text) <= PROSE_OVERLAP_CHARS:
        return text
    tail = text[-PROSE_OVERLAP_CHARS:]
    return tail[tail.find(" ") + 1:] if " " in tail else tail


def chunk_prose(text, meta):
    """Pack sentences into ~target-sized chunks with bounded char overlap.

    Guarantees every chunk is <= PROSE_TARGET_CHARS + PROSE_OVERLAP_CHARS, which
    keeps it under the embedding model's 256-token limit (no silent truncation).
    """
    text = _WS_RE.sub(" ", text).strip()
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    units = []
    for s in sentences:
        units.extend(_split_long_unit(s) if len(s) > PROSE_TARGET_CHARS else [s])

    chunks, cur, idx = [], "", 0
    for u in units:
        if cur and len(cur) + 1 + len(u) > PROSE_TARGET_CHARS:
            chunks.append(_make_chunk(cur, meta, idx))
            idx += 1
            cur = _overlap_seed(cur)              # bounded overlap into next chunk
        cur = f"{cur} {u}".strip() if cur else u
    if cur.strip():
        chunks.append(_make_chunk(cur, meta, idx))
    return chunks


def chunk_csv_records(rows, meta):
    """OECD rows -> 'In {year}, {country} spent {value}% of GDP on health.'"""
    chunks, idx = [], 0
    for row in rows:
        country = (row.get("Reference area") or "").strip()
        year = (row.get("TIME_PERIOD") or "").strip()
        value = (row.get("OBS_VALUE") or "").strip()
        unit = (row.get("Unit of measure") or "").strip()
        if not (country and year and value):
            continue
        unit_phrase = "% of GDP" if "GDP" in unit else unit
        text = (
            f"In {year}, {country} spent {value}{unit_phrase} on health "
            f"(OECD Health Statistics, health expenditure as a share of GDP)."
        )
        chunks.append(_make_chunk(text, meta, idx))
        idx += 1
    return chunks


# Worldometer ranking row: "1 Monaco 86.73 88.85 84.78"
_RANK_ROW_RE = re.compile(
    r"^\s*(\d{1,3})\s+([A-Za-z][A-Za-z .,'()\-]+?)\s+"
    r"(\d{2,3}(?:\.\d+)?)\s+(\d{2,3}(?:\.\d+)?)\s+(\d{2,3}(?:\.\d+)?)\s*$"
)


def chunk_ranking_rows(raw_text, meta):
    """Worldometer life-expectancy rows -> one templated sentence each."""
    chunks, idx, seen = [], 0, set()
    for line in raw_text.splitlines():
        m = _RANK_ROW_RE.match(line.strip())
        if not m:
            continue
        rank, country, both, female, male = m.groups()
        country = country.strip()
        if country in seen:        # the table repeats across pages; dedupe by country
            continue
        seen.add(country)
        text = (
            f"{country} ranks #{rank} in the world for life expectancy at birth: "
            f"{both} years overall ({female} for females, {male} for males) "
            f"(Worldometer, 2026)."
        )
        chunks.append(_make_chunk(text, meta, idx))
        idx += 1
    return chunks
