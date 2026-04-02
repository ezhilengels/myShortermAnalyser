"""
stocktips_pipeline.py — V3 orchestration entrypoint for /stocktips.

This module runs the full V3 pipeline:
1. load universe
2. fast pre-filter
3. shortlist validation / ranking
4. AI top-3 selection
"""

from __future__ import annotations

from typing import Any

from v3.ai_selector import select_top3_with_ai
from v3.prefilter import DEFAULT_PREFILTER_RULES, run_prefilter
from v3.ranker import rank_v3_candidates
from v3.universe_loader import load_universe, universe_summary


NO_PICK_RULES = {
    "min_passed_shortlist": 2,
    "min_top_score": 4.0,
    "min_top_confidence": 0.8,
    "min_top_gap": 1.5,
}


def run_stocktips_pipeline(
    universe: str = "watchlist",
    prefilter_rules: dict[str, Any] | None = None,
    max_prefilter_workers: int = 8,
    max_rank_workers: int = 6,
    max_ai_candidates: int = 10,
) -> dict[str, Any]:
    """
    Run the full V3 /stocktips pipeline and return a structured result.
    """
    summary = universe_summary(universe)
    symbols = load_universe(universe)

    prefilter = run_prefilter(
        symbols,
        rules=prefilter_rules,
        max_workers=max_prefilter_workers,
    )
    survivors = [row["symbol"] for row in prefilter["passed"]]

    ranking = rank_v3_candidates(
        survivors,
        max_workers=max_rank_workers,
    )
    passed_shortlist = ranking.get("passed", [])
    top_gap = 0.0
    if len(passed_shortlist) >= 2:
        top_gap = round(
            passed_shortlist[0].get("adjusted_score", passed_shortlist[0].get("score", 0))
            - passed_shortlist[1].get("adjusted_score", passed_shortlist[1].get("score", 0)),
            2,
        )

    if (
        len(passed_shortlist) < NO_PICK_RULES["min_passed_shortlist"]
        or not passed_shortlist
        or passed_shortlist[0].get("score", 0) < NO_PICK_RULES["min_top_score"]
        or passed_shortlist[0].get("confidence", 0) < NO_PICK_RULES["min_top_confidence"]
        or (len(passed_shortlist) >= 2 and top_gap < NO_PICK_RULES["min_top_gap"])
    ):
        ai_result = {
            "top_3": [],
            "watchouts": [
                "No high-conviction stocktips today under the current V3 quality gates",
            ],
            "market_note": (
                f"Skipped picks because shortlist quality was too weak. "
                f"Rules: min passed={NO_PICK_RULES['min_passed_shortlist']}, "
                f"top score>={NO_PICK_RULES['min_top_score']}, "
                f"top confidence>={NO_PICK_RULES['min_top_confidence']:.2f}, "
                f"top gap>={NO_PICK_RULES['min_top_gap']:.2f}. "
                f"Observed gap={top_gap:.2f}."
            ),
            "mode": "no_pick",
        }
    else:
        ai_result = select_top3_with_ai(
            passed_shortlist[:max_ai_candidates],
            max_candidates=max_ai_candidates,
        )

    return {
        "universe": summary,
        "prefilter": {
            "rules": dict(DEFAULT_PREFILTER_RULES, **(prefilter_rules or {})),
            "total": prefilter["total"],
            "passed": prefilter["passed"],
            "failed": prefilter["failed"],
            "pass_rate": prefilter["pass_rate"],
            "survivor_symbols": survivors,
        },
        "ranking": ranking,
        "ai_selection": ai_result,
        "no_pick_rules": dict(NO_PICK_RULES),
        "top_gap": top_gap,
    }


def format_stocktips_console(result: dict[str, Any]) -> str:
    """
    Render a concise console-friendly summary for quick testing.
    """
    universe = result.get("universe", {})
    prefilter = result.get("prefilter", {})
    ranking = result.get("ranking", {})
    selection = result.get("ai_selection", {})

    lines = []
    lines.append("V3 /stocktips")
    lines.append("=" * 60)
    lines.append(
        f"Universe: {universe.get('name', 'unknown')} | "
        f"count={universe.get('count', 0)}"
    )
    lines.append(
        f"Pre-filter: passed={len(prefilter.get('passed', []))}/"
        f"{prefilter.get('total', 0)} | pass_rate={prefilter.get('pass_rate', 0)}%"
    )
    lines.append(
        "Survivors: "
        + (", ".join(prefilter.get("survivor_symbols", [])) or "None")
    )
    lines.append(
        "Ranked: "
        + (", ".join(item["symbol"] for item in ranking.get("ranked", [])[:10]) or "None")
    )
    lines.append(
        "Passed shortlist gates: "
        + (", ".join(item["symbol"] for item in ranking.get("passed", [])[:10]) or "None")
    )
    lines.append("-" * 60)
    lines.append("Shortlist Details")
    for row in ranking.get("ranked", [])[:5]:
        checks = row.get("checks", [])
        passed = [c["name"] for c in checks if c["score"] > 0]
        failed = [c["name"] for c in checks if c["score"] < 0]
        lines.append(f"• {row['symbol']} | Score: {row['score']:+.2f} | Conf: {row['confidence']:.2f}")
        if passed:
            lines.append(f"  ✅ Passed: {', '.join(passed[:4])}")
        if failed:
            lines.append(f"  ❌ Failed: {', '.join(failed[:4])}")

    lines.append("-" * 60)
    lines.append("Top Picks")

    picks = selection.get("top_3", [])
    if not picks:
        lines.append("No picks available.")
    else:
        for pick in picks:
            lines.append(
                f"{pick['rank']}. {pick['name']} ({pick['symbol']})"
            )
            lines.append(f"   Why : {pick['why']}")
            lines.append(f"   Risk: {pick['risk']}")

    watchouts = selection.get("watchouts", [])
    if watchouts:
        lines.append("-" * 60)
        lines.append("Watchouts")
        for note in watchouts:
            lines.append(f"- {note}")

    market_note = selection.get("market_note")
    if market_note:
        lines.append("-" * 60)
        lines.append(f"Market note: {market_note}")

    return "\n".join(lines)
