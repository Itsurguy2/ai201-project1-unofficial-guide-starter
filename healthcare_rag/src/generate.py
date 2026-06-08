"""Stage 5: Grounded generation.

answer(query) retrieves the top-k chunks and asks a Groq LLM to answer using
ONLY those passages, with inline [n] citations that map back to sources. The
grounding is enforced two ways: structurally (only retrieved chunks are put in
context) and via the system prompt (refuse when the context lacks the answer).

CLI:  python generate.py                # runs the 5 evaluation questions
      python generate.py "your question"
"""

import os
import sys

from dotenv import load_dotenv
from groq import Groq

from config import GROQ_MODEL
from retrieve import TEST_QUESTIONS, retrieve

load_dotenv()

SYSTEM_PROMPT = (
    "You are a careful research assistant for an unofficial guide on U.S. "
    "healthcare cost and outcomes versus other countries. Answer the user's "
    "question using ONLY the numbered context passages provided.\n\n"
    "Rules:\n"
    "1. Use only facts stated in the context. Do NOT add outside knowledge.\n"
    "2. If the context does not contain the answer, reply exactly: "
    "\"I don't have enough information in my sources to answer that.\"\n"
    "3. Cite the passage number(s) that support each claim, like [1] or [2][4].\n"
    "4. When a figure has a year, include the year. Prefer the most recent "
    "data and note if sources disagree.\n"
    "5. Be concise — a few sentences."
)


def _client():
    key = os.environ.get("GROQ_API_KEY")
    if not key or key == "your_key_here":
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your "
            "free key from https://console.groq.com"
        )
    return Groq(api_key=key)


def format_context(hits) -> str:
    """Render retrieved chunks as numbered passages with source labels."""
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(
            f"[{i}] (Source: {h['source']}, {h['year']})\n{h['text']}"
        )
    return "\n\n".join(blocks)


def answer(query: str, k: int = 5) -> dict:
    """Retrieve, generate a grounded answer, and return it with its sources."""
    hits = retrieve(query, k=k)
    context = format_context(hits)
    user_msg = (
        f"Context passages:\n\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the passages above, with [n] citations."
    )
    resp = _client().chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    return {
        "query": query,
        "answer": resp.choices[0].message.content.strip(),
        "sources": [
            {"n": i, "source": h["source"], "url": h["url"], "year": h["year"]}
            for i, h in enumerate(hits, 1)
        ],
    }


def _print(result):
    print(f"\nQ: {result['query']}\n")
    print(result["answer"])
    print("\nSources:")
    for s in result["sources"]:
        print(f"  [{s['n']}] {s['source']} ({s['year']}) — {s['url']}")
    print("-" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _print(answer(" ".join(sys.argv[1:])))
    else:
        for q in TEST_QUESTIONS:
            _print(answer(q))
