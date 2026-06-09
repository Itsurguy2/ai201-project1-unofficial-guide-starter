# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

**U.S. healthcare cost vs. outcomes in global perspective** — why the United States spends far more on healthcare than other wealthy nations yet does not achieve longer life expectancy or universal coverage. The guide covers what Americans pay (employer premiums, drug prices, hospital and physician costs), what drives that spending, and the outcomes and coverage it buys, benchmarked against OECD/WHO peer countries.

This knowledge is hard to find through official channels because it is fragmented across government reports, OECD/WHO statistical databases, think-tank chart collections, and journalism — no single official source connects the dollars spent to the outcomes achieved. The guide consolidates these siloed, differently-formatted sources so a user can ask one question and get a sourced, cross-referenced answer.

---

https://share.vidyard.com/watch/Tm5fP6n5ynBGnZeBEqPh5Y
<img src='' title='Video Walkthrough' width='' alt='Video Walkthrough' />


## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | KFF — 2025 Employer Health Benefits Survey | Long report (web capture) | https://www.kff.org/health-costs/2025-employer-health-benefits-survey/ |
| 2 | Investopedia — *6 Reasons Healthcare Is So Expensive in the U.S.* | Short web article | https://www.investopedia.com/articles/personal-finance/080615/6-reasons-healthcare-so-expensive-us.asp |
| 3 | Peterson-KFF Health System Tracker — *How does U.S. health spending compare?* | Chart collection | https://www.healthsystemtracker.org/chart-collection/health-spending-u-s-compare-countries/ |
| 4 | Peterson-KFF — *What drives U.S. health spending?* | Issue brief | https://www.healthsystemtracker.org/brief/what-drives-health-spending-in-the-u-s-compared-to-other-countries/ |
| 5 | Commonwealth Fund — *U.S. Health Care from a Global Perspective 2026* | Issue brief | https://www.commonwealthfund.org/publications/issue-briefs/2026/may/us-health-care-global-perspective-2026 |
| 6 | Worldometer — *Life Expectancy by Country 2026* | Ranked data table | https://www.worldometers.info/demographics/life-expectancy/ |
| 7 | OECD Health Statistics — Health expenditure (% of GDP) | CSV dataset | `healthcare_rag/data/raw_pdfs/OECD.ELS.HD,DSD_SHA@DF_SHA,+.A.EXP_HEALTH.PT_B1GQ._T.._T.._T.csv` |
| 8 | WHO — United States country profile | Data profile (figure-heavy) | https://data.who.int/countries/840 |
| 9 | WHO — Afghanistan country profile | Data profile (figure-heavy) | https://data.who.int/countries/004 |
| 10 | CRS / Congress.gov — *CDC Funding Overview* (R47207) | Government report | https://www.congress.gov/crs-product/R47207 |
| 11 | WHO — *World Health Report 2000: Health Systems* | Long formal report | `healthcare_rag/data/raw_pdfs/whr-2000.pdf` (https://www.who.int/publications/i/item/924156198X) |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** Hybrid, by document type. **Prose path** (the 8 narrative/report PDFs): ~800 characters (~200 tokens). **Record path** (OECD CSV + Worldometer ranking table): one templated sentence per data row.

**Overlap:** ~120 characters (~15%, roughly one sentence) on the prose path; **none** on the record path (each record is already a self-contained fact).

**Why these choices fit your documents:** The corpus is structurally heterogeneous, so one splitter doesn't fit it. (1) The likely embedding model, `all-MiniLM-L6-v2`, truncates past **256 tokens**, so prose chunks are capped at ~200 tokens with headroom — verified: the largest chunk produced is 919 chars (~229 tokens), so nothing is silently truncated. (2) The narrative briefs state a complete comparative claim in one short paragraph, which ~200 tokens captures; the 15% overlap keeps such a claim from being split across a boundary. (3) The OECD CSV and Worldometer table are *atomic facts per row* — character splitting would sever the country↔number link, so each row is instead converted to a sentence (e.g., *"In 2022, Belgium spent 10.74% of GDP on health."*). **Preprocessing before chunking:** stripped web-capture boilerplate (timestamp headers, footer URLs, "SKIP TO CONTENT", ad text) and filtered the doubled-character garble in the figure-heavy WHO profiles (token-level). **Scoping:** the two oversized documents were scoped to their high-value sections (KFF → first 30 pages of narrative/figures, skipping the 300+ appendix-table pages; WHR-2000 → first 60 pages of overview + the health-system-performance chapter, skipping the dense annex tables).

**Final chunk count:** **1,391 chunks** across 11 sources (largest contributors: OECD records 499, Worldometer 215, WHR-2000 341, CDC 99, KFF 68).

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** `all-MiniLM-L6-v2` via `sentence-transformers` (384-dim, 256-token max), with vectors stored in ChromaDB (cosine space). Chosen because it runs locally (free, no API key or rate limits), is fast enough for an interactive UI, and is a strong general-purpose model for English prose — which is what this corpus is (health policy/economics, not clinical text). Its 256-token limit is what set the ~200-token prose chunk size, so the embedder and chunker are co-designed.

**Production tradeoff reflection:** If cost weren't a constraint: (1) **Accuracy on domain text** — a larger general model (`all-mpnet-base-v2`, `BGE-large`, or API `text-embedding-3-large`) would sharpen precision on subtle comparative claims (e.g., *per-capita* vs. *% of GDP* spending). Notably, a clinical/biomedical embedder (PubMedBERT, MedCPT) would *not* help and might hurt — this is health economics, not clinical text. (2) **Context length** — MiniLM's 256-token cap forced small chunks on the long reports, which is the root of my Q4-style chunk-isolation problem; a long-context embedder (e.g., `text-embedding-3-large`, 8,191 tokens) would let me embed whole coherent sections without splitting, and is the tradeoff I'd most want to buy. (3) **Multilingual** — not needed (corpus is all English), but would matter if I added non-English OECD/WHO sources. (4) **Latency / local vs. hosted** — local MiniLM is millisecond-fast and private; a hosted model adds round-trips, rate limits, and recurring cost, weighed against its accuracy gain.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

Grounding is enforced **two ways** — structurally and by prompt.

**Structural:** only the retrieved top-k chunks are placed in the model's context (`generate.py` → `format_context()`), so the LLM physically cannot see anything outside the retrieved passages. Each passage is numbered and labeled with its source and year:

```
[1] (Source: KFF — 2025 Employer Health Benefits Survey, 2025)
<chunk text>

[2] (Source: OECD Health Statistics — Health expenditure (% of GDP), 2024)
<chunk text>
```

**System prompt grounding instruction (verbatim from `generate.py`):**

> "Answer the user's question using ONLY the numbered context passages provided. Rules: (1) Use only facts stated in the context. Do NOT add outside knowledge. (2) If the context does not contain the answer, reply exactly: *"I don't have enough information in my sources to answer that."* (3) Cite the passage number(s) that support each claim, like [1] or [2][4]. (4) When a figure has a year, include the year. Prefer the most recent data and note if sources disagree. (5) Be concise."

The model runs at `temperature=0.1` to keep it close to the source text.

**How source attribution is surfaced in the response:** The model cites passage numbers inline (e.g. `[1][2]`), and `answer()` returns a `sources` list mapping each number back to its source name, year, and URL. The Gradio UI renders the answer followed by a **Sources** list, so every cited `[n]` resolves to a named, linkable source.

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

> Run with `all-MiniLM-L6-v2` retrieval (top-k=5, per-source cap) + Groq `llama-3.3-70b-versatile` generation at temperature 0.1.

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | 2025 family premium + worker contribution? | ~$26,993 family premium (up 6%); workers paid ~$6,850 | Gave 2025 family-premium figures by firm type ($26k–$28k) but **honestly stated the worker contribution "is not specified"** in the retrieved passages | Partially relevant — KFF premium chunks, but the headline-summary chunk with the $6,850 figure wasn't in top-k | Partially accurate |
| 2 | Primary driver of higher U.S. spending? | Hospital & physician (service) payments, not retail drugs | "Higher payments to hospitals and physicians [4]"; added $12,197 vs $6,514 per person (2021) | Relevant — `peterson_drivers` surfaced after the diversity cap | Accurate |
| 3 | How much more for prescription drugs? | Almost 4× developed-country prices | "Americans pay almost four times as much [2]"; added $963 vs $466 per person (2022) | Relevant — Investopedia "four times" chunk retrieved | Accurate |
| 4 | U.S. vs. Belgium health spend as % of GDP? | U.S. ~17% (WHO 17.36%, 2021); Belgium ~10.7% (OECD 10.74%, 2022) | **Refused the U.S. half** ("I don't have enough information…"); gave Belgium 10.9–11.5% across years | Partially relevant — Belgium strong; U.S. figure never retrieved (see Failure Case) | Partially accurate |
| 5 | Countries without universal coverage? | U.S. and Mexico (only 2 of 20) | "The U.S. and Mexico are the only countries…lacks any form of health insurance [1]" | Relevant — Commonwealth Fund coverage chunk | Accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

**Grounding check (out-of-domain):** Asked *"What is the best pizza place in Chicago?"* — the system returned exactly *"I don't have enough information in my sources to answer that."*, confirming it refuses rather than answering from outside the corpus.

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:** Q4 — *"What share of GDP does the U.S. spend on health, and how does it compare to Belgium?"* (a deliberately cross-source comparison: the U.S. figure lives in the WHO U.S. profile and the OECD CSV, the Belgium figure in the OECD CSV).

**What the system returned:** Retrieval returned a strong Belgium answer but **no clean U.S. figure** — the top-5 chunks were dominated by OECD Belgium-across-years rows (10.9%–11.5% of GDP) plus Peterson-KFF context, while the explicit U.S. figure (WHO: 17.36% of GDP, 2021) never entered even the top-60 candidate pool. Given that context, the generator did the *right* thing: it answered *"I don't have enough information in my sources to answer what share of GDP the U.S. spends on health"* and reported only Belgium — i.e., the grounding correctly refused to fabricate the missing half rather than hallucinating a plausible-looking U.S. number. The failure is therefore a **retrieval** failure surfaced honestly by generation, not a hallucination.

**Root cause (tied to a specific pipeline stage): the retrieval/embedding stage, compounded by the record-chunking choice.** The OECD records were templated as *"In {year}, {country} spent {value}% of GDP on health"* — phrasing that is *near-identical to the query* and exists in ~500 copies (every country × year). These flood the semantic neighborhood of any "% of GDP" query. The U.S. figure that *does* exist is embedded inside the WHO profile chunk surrounded by demographic text ("population 343,477,335…"), which dilutes its similarity to a pure spending query. A per-source diversity cap (`max_per_source=2`) over a widened pool was added and *did* fix a related case (Q2), but it can only diversify among sources that reach the candidate pool — and the U.S. spending chunk ranks below it.

**What you would change to fix it:** (1) **Deduplicate the OECD records** to the latest 1–2 years per country, cutting ~500 redundant chunks to ~100 so they stop flooding the pool. (2) **Add U.S.-specific records from the OECD CSV** via the same template so the U.S. figure is phrased like the query instead of buried in WHO prose. (3) Consider **query-side decomposition** (retrieve for "U.S." and "Belgium" separately, then merge) for explicitly comparative questions. Option (1) is the cheapest and most targeted.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:** Writing the Chunking Strategy *before* coding forced me to skim every document and notice the corpus was structurally heterogeneous (narrative briefs vs. atomic data tables vs. figure-heavy WHO profiles). That observation became the spec's central decision — a two-path hybrid chunker — which I then implemented directly. Because the spec also pinned the ~200-token prose size to the embedding model's 256-token limit, the chunker and embedder were co-designed, and I caught a real bug during testing (early chunks reached 2,001 chars, which would have been silently truncated) precisely because the spec gave me a number to verify against.

**One way your implementation diverged from the spec, and why:** The spec estimated 600–900 total chunks; the build produced **1,391**. The gap is entirely the record path — I under-counted the OECD CSV (499 records) and Worldometer table (215), which I'd loosely estimated. This divergence is benign for chunk *quality* (records are tiny and atomic) but it surfaced an unanticipated consequence at retrieval: those ~500 near-identical OECD records flood "% of GDP" queries (see Failure Case, Q4). The spec had anticipated big-document crowding from WHR-2000/KFF, but the real crowding came from the *record path* I had treated as low-risk — a reminder that chunk count and chunk *redundancy* are different problems.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1 — building the chunker from my spec**

- *What I gave the AI:* I gave Claude my Chunking Strategy section from `planning.md` together with a few real text samples I'd pulled from the documents (one narrative brief, one WHO country profile, and a single OECD CSV row), and asked it to build the two-path chunker I'd specified.
- *What it produced:* `ingest.py` and `chunk.py` — a prose chunker (~200 tokens, ~15% overlap) and a record chunker that turns each data row into a single sentence.
- *What I changed or overrode:* The first version was wrong — it produced 2,001-character chunks because its overlap logic re-added giant, unpunctuated "sentences" pulled from tables. I caught this because my spec had set a token budget to check against, so I rejected that version and had it rewrite the splitter to break on word boundaries with a bounded overlap. I then confirmed the largest chunk dropped to 919 characters, safely under my embedding model's 256-token limit.

**Instance 2 — deciding what to do about a failed test question**

- *What I gave the AI:* I gave Claude the output of my retrieval test, where my Q4 question (U.S. vs. Belgium spending as a share of GDP) came back with five Belgium OECD rows and no U.S. figure at all.
- *What it produced:* a per-source diversity cap over a wider candidate pool, which fixed a different question (Q2) but not Q4, plus a suggestion to deduplicate the OECD records to force Q4 to pass.
- *What I changed or overrode:* I decided not to tune the system just to make Q4 pass. I kept the retrieval logic simple and instead documented Q4 as a genuine failure case, tracing it to the ~500 near-identical OECD records crowding the results. I'd rather submit a partial result I can explain than a perfect-looking score I engineered after the fact.
