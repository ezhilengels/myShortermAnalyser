"""
ai_selector.py — V3 AI ranking stage for /stocktips.

This module takes the top ranked shortlist candidates from the V3 validator and
asks the AI layer to choose the final top 3. It is intentionally separate from
the current single-stock AI decision flow.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ai.groq_engine import get_groq_client
from config import (
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    SECTOR_FLOW_LABELS,
    STOCK_NAMES,
    STOCK_SECTOR_BENCHMARKS,
)

logger = logging.getLogger(__name__)


SECTOR_DIVERSIFICATION_RULES = {
    "max_per_sector": 1,
    "dominance_gap": 2.0,
}


def _sector_label(symbol: str) -> str:
    benchmark = STOCK_SECTOR_BENCHMARKS.get(symbol, "")
    return SECTOR_FLOW_LABELS.get(benchmark, benchmark or "Unknown")


def _ranking_score(candidate: dict[str, Any]) -> float:
    return float(candidate.get("adjusted_score", candidate.get("score", 0.0)))


def _is_sector_dominant(candidate: dict[str, Any], alternatives: list[dict[str, Any]]) -> bool:
    same_sector = _sector_label(candidate.get("symbol", ""))
    for other in alternatives:
        if other.get("symbol") == candidate.get("symbol"):
            continue
        if _sector_label(other.get("symbol", "")) == same_sector:
            continue
        return _ranking_score(candidate) - _ranking_score(other) >= SECTOR_DIVERSIFICATION_RULES["dominance_gap"]
    return True


def _enforce_sector_diversification(
    ordered_symbols: list[str],
    candidates: list[dict[str, Any]],
) -> list[str]:
    candidate_map = {item.get("symbol", ""): item for item in candidates}
    remaining = [item for item in candidates if item.get("symbol")]
    diversified: list[str] = []
    per_sector: dict[str, int] = {}

    for symbol in ordered_symbols:
        candidate = candidate_map.get(symbol)
        if not candidate:
            continue
        sector = _sector_label(symbol)
        sector_count = per_sector.get(sector, 0)
        if sector_count >= SECTOR_DIVERSIFICATION_RULES["max_per_sector"] and not _is_sector_dominant(candidate, remaining):
            continue
        diversified.append(symbol)
        per_sector[sector] = sector_count + 1
        if len(diversified) >= min(3, len(candidates)):
            return diversified

    for candidate in remaining:
        symbol = candidate.get("symbol", "")
        if not symbol or symbol in diversified:
            continue
        diversified.append(symbol)
        if len(diversified) >= min(3, len(candidates)):
            break

    return diversified


def _compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": candidate.get("symbol", ""),
        "name": STOCK_NAMES.get(candidate.get("symbol", ""), candidate.get("symbol", "")),
        "sector": _sector_label(candidate.get("symbol", "")),
        "score": candidate.get("score", 0.0),
        "adjusted_score": candidate.get("adjusted_score", candidate.get("score", 0.0)),
        "technical_score": candidate.get("technical_score", 0.0),
        "fundamental_score": candidate.get("fundamental_score", 0.0),
        "context_score": candidate.get("context_score", 0.0),
        "confidence": candidate.get("confidence", 0.0),
        "top_positives": candidate.get("top_positives", []),
        "top_negatives": candidate.get("top_negatives", []),
        "summary": candidate.get("summary", ""),
    }


def _build_selector_prompt(candidates: list[dict[str, Any]]) -> str:
    payload = json.dumps([_compact_candidate(item) for item in candidates], indent=2)
    return f"""You are selecting daily Indian stock ideas for a /stocktips shortlist.

You will receive up to 10 pre-ranked NSE candidates that have already passed:
1. broad quantitative pre-filtering
2. V3 shortlist validation

Your job is NOT to invent new stocks.
You must choose only from the provided shortlist and rank the best 3 for today.

Selection rules:
- Prefer strong technical + fundamental alignment.
- Use context scores to refine ranking, not to dominate it.
- Penalize candidates with weak fundamentals, low confidence, or obvious conflicting negatives.
- Prefer sector diversification in the final top 3.
- Do not pick multiple names from the same sector unless the duplicate is clearly dominant versus the next best cross-sector alternative.
- Be conservative. If the shortlist quality is weak, still pick the best 3 from the list, but say so clearly.
- Do not output any stock that is not in the shortlist.
- Avoid duplicate symbols.

Return JSON only in this format:
{{
  "top_3": [
    {{
      "rank": 1,
      "symbol": "NSE symbol from shortlist",
      "name": "display name",
      "why": "One concise reason",
      "risk": "One concise risk"
    }},
    {{
      "rank": 2,
      "symbol": "NSE symbol from shortlist",
      "name": "display name",
      "why": "One concise reason",
      "risk": "One concise risk"
    }},
    {{
      "rank": 3,
      "symbol": "NSE symbol from shortlist",
      "name": "display name",
      "why": "One concise reason",
      "risk": "One concise risk"
    }}
  ],
  "watchouts": [
    "Short note 1",
    "Short note 2"
  ],
  "market_note": "One concise portfolio-level comment"
}}

SHORTLIST:
{payload}
"""


def _fallback_pick(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    diversified_symbols = _enforce_sector_diversification(
        [item.get("symbol", "") for item in candidates],
        candidates,
    )
    candidate_map = {item.get("symbol", ""): item for item in candidates}
    picks = []
    for idx, symbol in enumerate(diversified_symbols[:3], start=1):
        item = candidate_map[symbol]
        picks.append(
            {
                "rank": idx,
                "symbol": symbol,
                "name": STOCK_NAMES.get(symbol, symbol),
                "why": (
                    f"Score {item.get('score', 0):+.2f} with "
                    f"tech {item.get('technical_score', 0):+.2f} and "
                    f"fund {item.get('fundamental_score', 0):+.2f}"
                ),
                "risk": (
                    ", ".join(item.get("top_negatives", [])[:2])
                    or "AI unavailable; review risk manually"
                ),
            }
        )

    return {
        "top_3": picks,
        "watchouts": ["AI selector unavailable; using score-ranked fallback shortlist"],
        "market_note": "Fallback mode used. Ranked by V3 shortlist scores only.",
        "mode": "fallback",
    }


def _parse_selector_response(raw: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    shortlist_symbols = {item.get("symbol", "") for item in candidates}
    candidate_map = {item.get("symbol", ""): item for item in candidates}

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end <= 0:
            raise ValueError("No JSON found in AI selector response")

        parsed = json.loads(raw[start:end])
        top_3 = parsed.get("top_3", [])

        cleaned = []
        seen = set()
        for idx, pick in enumerate(top_3, start=1):
            symbol = str(pick.get("symbol", "")).strip().upper()
            if not symbol or symbol not in shortlist_symbols or symbol in seen:
                continue
            seen.add(symbol)
            cleaned.append(
                {
                    "rank": len(cleaned) + 1,
                    "symbol": symbol,
                    "name": pick.get("name") or STOCK_NAMES.get(symbol, symbol),
                    "why": str(pick.get("why", "")).strip() or "Selected by AI shortlist ranking",
                    "risk": str(pick.get("risk", "")).strip() or "Review manually",
                }
            )

        diversified_order = _enforce_sector_diversification(
            [pick["symbol"] for pick in cleaned],
            candidates,
        )

        diversified = []
        for symbol in diversified_order:
            pick = next((item for item in cleaned if item["symbol"] == symbol), None)
            if pick:
                diversified.append(
                    {
                        **pick,
                        "rank": len(diversified) + 1,
                    }
                )

        if len(diversified) < min(3, len(candidates)):
            remaining_symbols = _enforce_sector_diversification(
                diversified_order + [item.get("symbol", "") for item in candidates],
                candidates,
            )
            for symbol in remaining_symbols:
                if symbol in {item["symbol"] for item in diversified}:
                    continue
                candidate = candidate_map.get(symbol)
                if not candidate:
                    continue
                diversified.append(
                    {
                        "rank": len(diversified) + 1,
                        "symbol": symbol,
                        "name": STOCK_NAMES.get(symbol, symbol),
                        "why": "Added from ranked shortlist to preserve sector diversification",
                        "risk": ", ".join(candidate.get("top_negatives", [])[:2]) or "Review manually",
                    }
                )
                if len(diversified) >= min(3, len(candidates)):
                    break

        if len(diversified) < min(3, len(candidates)):
            raise ValueError("AI selector returned incomplete or invalid shortlist")

        return {
            "top_3": diversified,
            "watchouts": parsed.get("watchouts", [])[:3],
            "market_note": parsed.get("market_note", "").strip() or "AI ranked the shortlist.",
            "mode": "ai",
        }
    except Exception as e:
        logger.error(f"V3 AI selector parse error: {e}. Raw: {raw[:200]}")
        return _fallback_pick(candidates)


def select_top3_with_ai(
    ranked_candidates: list[dict[str, Any]],
    max_candidates: int = 10,
) -> dict[str, Any]:
    """
    Ask the AI layer to choose the final top 3 from the V3 shortlist.
    """
    shortlist = [item for item in ranked_candidates if item.get("symbol")][:max_candidates]
    if not shortlist:
        return {
            "top_3": [],
            "watchouts": ["No shortlist candidates available"],
            "market_note": "V3 AI selector skipped because the shortlist was empty.",
            "mode": "empty",
        }

    if len(shortlist) <= 3:
        return {
            **_fallback_pick(shortlist),
            "watchouts": ["Shortlist had 3 or fewer names; AI ranking skipped"],
        }

    try:
        client = get_groq_client()
        prompt = _build_selector_prompt(shortlist)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=min(GROQ_TEMPERATURE, 0.3),
            max_tokens=min(GROQ_MAX_TOKENS, 900),
        )
        raw_content = response.choices[0].message.content or ""
        return _parse_selector_response(raw_content, shortlist)
    except Exception as e:
        logger.error(f"V3 AI selector error: {e}")
        return _fallback_pick(shortlist)
