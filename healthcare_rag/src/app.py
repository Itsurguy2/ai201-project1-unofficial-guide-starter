"""Milestone 5 interface (+ stretch features): a Gradio Q&A app over the
healthcare RAG pipeline.

Stretch features wired into the UI:
  - A. Search mode selector: hybrid (BM25+semantic) / semantic / bm25.
  - C. Metadata filters: restrict by source and by "published since" year.
  - D. Conversational memory: follow-up questions are condensed against the
       chat history before retrieval, so "how does that compare to Belgium?"
       works after asking about U.S. spending.

Run from src/:  python app.py   (then open the printed local URL)
Requires GROQ_API_KEY in a .env file (see .env.example).
"""

import gradio as gr

from config import SOURCES
from generate import answer
from retrieve import TEST_QUESTIONS

INTRO = (
    "# The Unofficial Guide: U.S. Healthcare Costs vs. the World\n"
    "Ask about U.S. health spending, what drives it, and how it compares to "
    "other countries. Answers are grounded **only** in the collected sources "
    "(KFF, OECD, WHO, Peterson-KFF, Commonwealth Fund, CRS, Worldometer) and "
    "cite the passages they rely on.\n\n"
    "*Use the controls below the box to switch search mode, filter sources, or "
    "limit by year. Follow-up questions remember the conversation.*"
)

# (label, value) choices for the source multiselect.
SOURCE_CHOICES = [(s["source"], s["id"]) for s in SOURCES]
MIN_CORPUS_YEAR = min(s["year"] for s in SOURCES)
MAX_CORPUS_YEAR = max(s["year"] for s in SOURCES)


def _build_filters(source_ids, min_year):
    """Assemble a filter spec from the UI controls (empty controls -> no filter)."""
    filters = {}
    if source_ids:
        filters["source_ids"] = source_ids
    if min_year and min_year > MIN_CORPUS_YEAR:
        filters["min_year"] = int(min_year)
    return filters or None


def respond(query, history, mode, source_ids, min_year):
    """Chat handler: condense against history, retrieve under mode+filters, answer."""
    if not query or not query.strip():
        return "Please enter a question."
    filters = _build_filters(source_ids, min_year)
    try:
        result = answer(query, mode=mode, filters=filters, history=history)
    except RuntimeError as e:
        return f"⚠️ {e}"

    lines = [result["answer"]]
    # Feature D transparency: show the rewritten query when memory changed it.
    standalone = result.get("standalone_query")
    if standalone and standalone.strip() != query.strip():
        lines += ["", f"*↪ interpreted as: “{standalone}”*"]
    if result["sources"]:
        lines += ["", "**Sources:**"]
        for s in result["sources"]:
            lines.append(f"- [{s['n']}] {s['source']} ({s['year']}) — {s['url']}")
    return "\n".join(lines)


mode_input = gr.Radio(
    choices=["hybrid", "semantic", "bm25"],
    value="hybrid",
    label="Search mode",
    info="hybrid = BM25 + semantic (RRF); semantic = embeddings only; bm25 = keyword only",
)
source_input = gr.Dropdown(
    choices=SOURCE_CHOICES,
    value=[],
    multiselect=True,
    label="Limit to sources (empty = all)",
)
year_input = gr.Slider(
    minimum=MIN_CORPUS_YEAR,
    maximum=MAX_CORPUS_YEAR,
    value=MIN_CORPUS_YEAR,
    step=1,
    label="Published since (year)",
    info=f"{MIN_CORPUS_YEAR} = no date filter",
)


with gr.Blocks(title="Unofficial Guide: U.S. Healthcare Costs") as demo:
    gr.Markdown(INTRO)
    gr.ChatInterface(
        fn=respond,
        additional_inputs=[mode_input, source_input, year_input],
        examples=[[q] for q in TEST_QUESTIONS],
        cache_examples=False,
    )


if __name__ == "__main__":
    demo.launch()
