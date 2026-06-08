"""Stage 1: Document ingestion + preprocessing.

Loads raw PDFs (pdfplumber) and the OECD CSV (csv module), and cleans the
web-capture boilerplate and garbled chart text that would otherwise pollute
chunks (see planning.md "Anticipated Challenges" #1).
"""

import csv
import re

import pdfplumber

# --- Boilerplate patterns to drop, line by line --------------------------
# Header timestamp left by the "print to PDF" capture, e.g. "6/8/26, 1:01 AM".
_TIMESTAMP_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*(AM|PM)?", re.I)
# A line that is essentially just a URL (often a page-footer like ".../foo  1/11").
_URL_LINE_RE = re.compile(r"^\s*https?://\S+(\s+\d+/\d+)?\s*$", re.I)
_URL_INLINE_RE = re.compile(r"https?://\S+")

_BOILERPLATE_SNIPPETS = (
    "skip to content",
    "top stories",
    "news release:",
)


def _dup_pair_ratio(s: str) -> float:
    """Fraction of adjacent character pairs that are identical."""
    if len(s) < 2:
        return 0.0
    return sum(s[i] == s[i + 1] for i in range(len(s) - 1)) / (len(s) - 1)


def _is_garbled_token(tok: str) -> bool:
    """A single word from overlapping chart layers, e.g. 'AAffgghhaanniissttaann'."""
    return len(tok) > 4 and _dup_pair_ratio(tok) > 0.45


def _strip_garbled_tokens(line: str) -> str:
    """Drop garbled words but keep the clean ones around them.

    The WHO profiles interleave doubled-character chart labels with clean text on
    the same line, so whole-line filtering misses them; this works word by word.
    """
    kept = [t for t in line.split() if not _is_garbled_token(t)]
    return " ".join(kept)


def clean_lines(text: str, drop_garbage: bool = False) -> str:
    """Strip boilerplate (and optionally garbled) lines, return cleaned text."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _TIMESTAMP_RE.match(line):
            # The capture header is prepended to the first line of each page;
            # keep any real content that follows the timestamp on the same line.
            line = _TIMESTAMP_RE.sub("", line).strip()
            if not line:
                continue
        if _URL_LINE_RE.match(line):
            continue
        low = line.lower()
        if any(sn in low for sn in _BOILERPLATE_SNIPPETS):
            continue
        # Strip inline trailing URLs that ride along with real text.
        line = _URL_INLINE_RE.sub("", line).strip()
        if drop_garbage:
            line = _strip_garbled_tokens(line)
        if len(line) >= 3:
            out.append(line)
    return "\n".join(out)


def load_pdf_text(path, pages=None, drop_garbage=False) -> str:
    """Extract and clean text from a PDF, optionally scoped to a page range."""
    parts = []
    with pdfplumber.open(path) as pdf:
        page_list = pdf.pages
        if pages is not None:
            start, end = pages
            page_list = page_list[start:end]
        for page in page_list:
            parts.append(page.extract_text() or "")
    return clean_lines("\n".join(parts), drop_garbage=drop_garbage)


def load_pdf_raw_text(path, pages=None) -> str:
    """Uncleaned page text -- used by the ranking-table regex extractor."""
    parts = []
    with pdfplumber.open(path) as pdf:
        page_list = pdf.pages if pages is None else pdf.pages[pages[0]:pages[1]]
        for page in page_list:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def load_csv_rows(path) -> list[dict]:
    """Read a CSV into a list of dict rows (UTF-8, replacing bad bytes)."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))
