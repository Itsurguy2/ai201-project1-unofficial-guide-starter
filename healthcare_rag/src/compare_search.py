"""Stretch Feature A (eval): compare semantic-only vs. hybrid (BM25+semantic).

For each of the 5 evaluation questions we know the gold source_id(s) that should
appear in the retrieved set (from planning.md's evaluation table). We run each
question under both modes and report, per question:
  - which gold sources were recovered, and at what rank (1-based; "-" = missing)
  - a recall@k score (fraction of that question's gold sources found in top-k)

Run from src/:  python compare_search.py
"""

from hybrid import search
from retrieve import TEST_QUESTIONS

# Gold source_id(s) per question (see planning.md evaluation table).
GOLD = {
    1: ["kff_employer_survey"],
    2: ["peterson_drivers"],
    3: ["investopedia_6reasons"],
    4: ["who_usa", "oecd_health_expenditure"],   # cross-source comparison
    5: ["commonwealth_global"],
}

MODES = ["semantic", "hybrid"]


def gold_ranks(hits, gold_ids):
    """Map each gold source_id -> its best (lowest) 1-based rank in hits, or None."""
    ranks = {}
    for gid in gold_ids:
        rank = next((i for i, h in enumerate(hits, 1) if h["source_id"] == gid), None)
        ranks[gid] = rank
    return ranks


def main():
    totals = {m: {"found": 0, "possible": 0} for m in MODES}

    for i, q in enumerate(TEST_QUESTIONS, 1):
        gold_ids = GOLD[i]
        print(f"\nQ{i}: {q}")
        print(f"   gold: {', '.join(gold_ids)}")
        for mode in MODES:
            hits = search(q, mode=mode)
            ranks = gold_ranks(hits, gold_ids)
            found = sum(1 for r in ranks.values() if r is not None)
            totals[mode]["found"] += found
            totals[mode]["possible"] += len(gold_ids)
            detail = "  ".join(
                f"{gid}@{r if r else '-'}" for gid, r in ranks.items()
            )
            print(f"   {mode:<9} recall {found}/{len(gold_ids)}   [{detail}]")

    print("\n" + "=" * 60)
    print(f"{'mode':<10}{'gold recovered':>16}{'recall@k':>12}")
    print("-" * 60)
    for mode in MODES:
        f, p = totals[mode]["found"], totals[mode]["possible"]
        print(f"{mode:<10}{f:>10}/{p:<5}{f / p:>12.2%}")


if __name__ == "__main__":
    main()
