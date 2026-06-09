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
from hybrid import search
from retrieve import TEST_QUESTIONS

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


CONDENSE_PROMPT = (
    "You rewrite a follow-up question into a standalone question for a search "
    "engine, using the conversation so far to resolve references like 'that', "
    "'it', 'those', or 'compare'. Output ONLY the rewritten question, nothing "
    "else. If the latest question is already self-contained, return it unchanged."
)


def _normalize_history(history) -> list[dict]:
    """Accept Gradio 'messages' (list of {role,content}) or 'tuples' history.

    Returns a flat list of {"role", "content"} dicts (user/assistant only).
    """
    msgs = []
    for turn in history or []:
        if isinstance(turn, dict):
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                msgs.append({"role": turn["role"], "content": str(turn["content"])})
        elif isinstance(turn, (list, tuple)) and len(turn) == 2:
            user, bot = turn
            if user:
                msgs.append({"role": "user", "content": str(user)})
            if bot:
                msgs.append({"role": "assistant", "content": str(bot)})
    return msgs


def condense_query(query: str, history, max_turns: int = 6) -> str:
    """Rewrite an elliptical follow-up into a standalone question (Feature D).

    With no history the query is returned unchanged (skips the LLM call), so a
    first turn behaves exactly like the original single-turn app.
    """
    msgs = _normalize_history(history)
    if not msgs:
        return query
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in msgs[-max_turns:])
    resp = _client().chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": CONDENSE_PROMPT},
            {"role": "user",
             "content": f"Conversation so far:\n{transcript}\n\n"
                        f"Follow-up question: {query}\n\nStandalone question:"},
        ],
    )
    return resp.choices[0].message.content.strip() or query


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


def answer(
    query: str,
    k: int = 5,
    mode: str = "hybrid",
    filters: dict | None = None,
    history=None,
) -> dict:
    """Retrieve, generate a grounded answer, and return it with its sources.

    mode / filters route through hybrid.search (Features A + C). When `history`
    is supplied, the question is first condensed into a standalone query
    (Feature D) so follow-ups retrieve the right chunks.
    """
    standalone = condense_query(query, history)
    hits = search(standalone, k=k, mode=mode, filters=filters)
    if not hits:
        return {
            "query": query,
            "standalone_query": standalone,
            "answer": "I don't have enough information in my sources to answer "
                      "that" + (" under the selected filters." if filters else "."),
            "sources": [],
        }
    context = format_context(hits)
    user_msg = (
        f"Context passages:\n\n{context}\n\n"
        f"Question: {standalone}\n\n"
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
        "standalone_query": standalone,
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
