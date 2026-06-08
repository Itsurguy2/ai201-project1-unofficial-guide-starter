"""Milestone 5 interface: a Gradio Q&A app over the healthcare RAG pipeline.

Run from src/:  python app.py   (then open the printed local URL)
Requires GROQ_API_KEY in a .env file (see .env.example).
"""

import gradio as gr

from generate import answer
from retrieve import TEST_QUESTIONS

INTRO = (
    "# The Unofficial Guide: U.S. Healthcare Costs vs. the World\n"
    "Ask about U.S. health spending, what drives it, and how it compares to "
    "other countries. Answers are grounded **only** in the collected sources "
    "(KFF, OECD, WHO, Peterson-KFF, Commonwealth Fund, CRS, Worldometer) and "
    "cite the passages they rely on."
)


def respond(query, history):
    """Chat handler: returns a grounded answer plus a formatted source list."""
    if not query or not query.strip():
        return "Please enter a question."
    try:
        result = answer(query)
    except RuntimeError as e:
        return f"⚠️ {e}"
    lines = [result["answer"], "", "**Sources:**"]
    for s in result["sources"]:
        lines.append(f"- [{s['n']}] {s['source']} ({s['year']}) — {s['url']}")
    return "\n".join(lines)


with gr.Blocks(title="Unofficial Guide: U.S. Healthcare Costs") as demo:
    gr.Markdown(INTRO)
    gr.ChatInterface(
        fn=respond,
        examples=TEST_QUESTIONS,
        cache_examples=False,
    )


if __name__ == "__main__":
    demo.launch()
