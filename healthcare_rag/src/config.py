"""Central configuration for the healthcare RAG pipeline.

Defines where the data lives, the chunking parameters, and the per-source
catalog (with the scoping decisions made in planning.md). Keeping all of this
in one place means the ingestion/chunking code stays generic and every
document-specific choice is visible and tunable here.
"""

from pathlib import Path

# --- Paths ---------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent
PKG_DIR = SRC_DIR.parent                      # healthcare_rag/
RAW_DIR = PKG_DIR / "data" / "raw_pdfs"
PROCESSED_DIR = PKG_DIR / "data" / "processed"
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"

# --- Chunking parameters (see planning.md "Chunking Strategy") -----------
# Prose path: ~200 tokens stays under all-MiniLM-L6-v2's 256-token limit.
# ~4 chars/token for English -> ~800 chars target, ~120 chars (~15%) overlap.
PROSE_TARGET_CHARS = 800
PROSE_OVERLAP_CHARS = 120
PROSE_HARD_MAX_CHARS = 1000   # a single sentence longer than this is force-split

# --- Embedding + vector store (see planning.md "Retrieval Approach") -----
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"   # 384-dim, 256-token limit, local
CHROMA_DIR = str(PROCESSED_DIR / "chroma")
COLLECTION_NAME = "healthcare_rag"
TOP_K = 5

# --- Generation (Milestone 5) --------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"   # strong instruction-following on Groq

# --- Source catalog ------------------------------------------------------
# kind:
#   "prose"        -> narrative PDF, prose chunker
#   "who_profile"  -> figure-heavy WHO PDF, prose chunker + extra garbage filter
#   "csv"          -> OECD structured data, one templated sentence per row
#   "ranking_pdf"  -> Worldometer ranking table, regex row -> templated sentence
# pages: (start, end_exclusive) to scope the two oversized docs; None = all pages.
SOURCES = [
    {
        "id": "kff_employer_survey",
        "file": "2025 Employer Health Benefits Survey _ KFF.pdf",
        "source": "KFF — 2025 Employer Health Benefits Survey",
        "url": "https://www.kff.org/health-costs/2025-employer-health-benefits-survey/",
        "kind": "prose",
        "year": 2025,
        "pages": (0, 30),   # narrative + figures A-M; appendix tables (30+) skipped
    },
    {
        "id": "investopedia_6reasons",
        "file": "6 Reasons Healthcare Is So Expensive in the U.S_.pdf",
        "source": "Investopedia — 6 Reasons Healthcare Is So Expensive in the U.S.",
        "url": "https://www.investopedia.com/articles/personal-finance/080615/6-reasons-healthcare-so-expensive-us.asp",
        "kind": "prose",
        "year": 2025,
        "pages": None,
    },
    {
        "id": "who_afghanistan",
        "file": "Afghanistan.pdf",
        "source": "WHO — Afghanistan country profile",
        "url": "https://data.who.int/countries/004",
        "kind": "who_profile",
        "year": 2023,
        "pages": None,
    },
    {
        "id": "crs_cdc_funding",
        "file": "Centers for Disease Control and Prevention (CDC) Funding Overview _ Congress.gov _ Library of Congress.pdf",
        "source": "CRS / Congress.gov — CDC Funding Overview (R47207)",
        "url": "https://www.congress.gov/crs-product/R47207",
        "kind": "prose",
        "year": 2026,
        "pages": None,
    },
    {
        "id": "peterson_compare",
        "file": "How does health spending in the U.S. compare to other countries_ - Peterson-KFF Health System Tracker.pdf",
        "source": "Peterson-KFF — How does U.S. health spending compare?",
        "url": "https://www.healthsystemtracker.org/chart-collection/health-spending-u-s-compare-countries/",
        "kind": "prose",
        "year": 2026,
        "pages": None,
    },
    {
        "id": "worldometer_life_expectancy",
        "file": "Life Expectancy by Country and in the World (2026) - Worldometer.pdf",
        "source": "Worldometer — Life Expectancy by Country 2026",
        "url": "https://www.worldometers.info/demographics/life-expectancy/",
        "kind": "ranking_pdf",
        "year": 2026,
        "pages": None,
    },
    {
        "id": "oecd_health_expenditure",
        "file": "OECD.ELS.HD,DSD_SHA@DF_SHA,+.A.EXP_HEALTH.PT_B1GQ._T.._T.._T.csv",
        "source": "OECD Health Statistics — Health expenditure (% of GDP)",
        "url": "https://data-explorer.oecd.org/ (SHA: Health expenditure and financing)",
        "kind": "csv",
        "year": 2024,
        "pages": None,
    },
    {
        "id": "commonwealth_global",
        "file": "U.S. Health Care from Global Perspective 2026 Expanded Edition _ Commonwealth Fund.pdf",
        "source": "Commonwealth Fund — U.S. Health Care from a Global Perspective 2026",
        "url": "https://www.commonwealthfund.org/publications/issue-briefs/2026/may/us-health-care-global-perspective-2026",
        "kind": "prose",
        "year": 2026,
        "pages": None,
    },
    {
        "id": "who_usa",
        "file": "United States of America.pdf",
        "source": "WHO — United States country profile",
        "url": "https://data.who.int/countries/840",
        "kind": "who_profile",
        "year": 2023,
        "pages": None,
    },
    {
        "id": "peterson_drivers",
        "file": "What drives health spending in the U.S. compared to other countries_ - Peterson-KFF Health System Tracker.pdf",
        "source": "Peterson-KFF — What drives U.S. health spending?",
        "url": "https://www.healthsystemtracker.org/brief/what-drives-health-spending-in-the-u-s-compared-to-other-countries/",
        "kind": "prose",
        "year": 2024,
        "pages": None,
    },
    {
        "id": "whr_2000",
        "file": "whr-2000.pdf",
        "source": "WHO — World Health Report 2000: Health Systems",
        "url": "https://www.who.int/publications/i/item/924156198X",
        "kind": "prose",
        "year": 2000,
        "pages": (0, 60),   # front matter + Ch.1 overview + Ch.2 performance/ranking
    },
]
