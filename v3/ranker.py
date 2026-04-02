"""
ranker.py — V3 shortlist validation and ranking engine for /stocktips.

This module runs a smaller, stronger subset of signals on pre-filter survivors.
It is intentionally separate from the current 21-check scored framework.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from typing import Any

from config import SIGNAL_WEIGHTS
from data.fetchers.screener_fetcher import get_screener_snapshot
from data.fetchers.yfinance_fetcher import (
    get_balance_sheet,
    get_financials,
    get_historical_data,
    get_ticker_info,
)
from analysis.technical import (
    check_dma_position,
    check_macd,
    check_moving_averages,
    check_relative_strength,
    check_rsi,
    check_supertrend,
    check_vpt,
    check_52w_breakout_club,
)
from analysis.fundamental import (
    check_debt,
    check_earnings_growth,
    check_margins,
    check_valuation_v4,
)
from analysis.macro import (
    check_china_pmi_signal,
    check_commodity,
    check_news_sentiment_score,
    check_sector_tailwind_alignment,
)

logger = logging.getLogger(__name__)


V3_QUALITY_GATES = {
    "min_score": 2.0,
    "min_technical_score": 1.5,
    "min_fundamental_score": 1.0,
    "min_confidence": 0.75,
    "max_negative_checks": 4,
}


V3_CHECKS = [
    ("technical", "DMA Position", 1.0, lambda ctx: check_dma_position(ctx["df"])),
    ("technical", "MACD", 0.9, lambda ctx: check_macd(ctx["df"])),
    ("technical", "RSI", 0.8, lambda ctx: check_rsi(ctx["df"])),
    ("technical", "Moving Avg Alignment", 1.0, lambda ctx: check_moving_averages(ctx["df"])),
    ("technical", "Supertrend", 0.9, lambda ctx: check_supertrend(ctx["df"])),
    ("technical", "Relative Strength", 1.0, lambda ctx: check_relative_strength(ctx["df"], ctx["symbol"])),
    ("technical", "VPT Accumulation", 0.8, lambda ctx: check_vpt(ctx["df"])),
    ("technical", "52W High Breakout Club", 0.9, lambda ctx: check_52w_breakout_club(ctx["df"], ctx["ticker_info"])),
    ("fundamental", "Earnings Growth", 0.9, lambda ctx: check_earnings_growth(ctx["ticker_info"], ctx["financials"], ctx["screener"])),
    ("fundamental", "Profit Margin / ROE", 1.0, lambda ctx: check_margins(ctx["ticker_info"], ctx["financials"], ctx["balance_sheet"], ctx["screener"])),
    ("fundamental", "Debt Level", 1.0, lambda ctx: check_debt(ctx["ticker_info"], ctx["balance_sheet"], ctx["screener"])),
    ("fundamental", "Valuation", 0.9, lambda ctx: check_valuation(ctx["ticker_info"], ctx["symbol"], ctx["screener"])),
    ("context", "Sector Alignment", 0.8, lambda ctx: check_sector_tailwind_alignment(ctx["symbol"])),
    ("context", "Commodity Tailwind", 0.7, lambda ctx: check_commodity(ctx["symbol"])),
    ("context", "China PMI", 0.5, lambda ctx: check_china_pmi_signal(ctx["symbol"])),
    ("context", "News Sentiment", 0.5, lambda ctx: check_news_sentiment_score(ctx["symbol"])),
]


def _v3_signal_score(signal: str, weight: float) -> float:
    base = float(SIGNAL_WEIGHTS.get(signal, 0))
    return round(base * weight, 2)


def _passes_quality_gates(
    total_score: float,
    technical_score: float,
    fundamental_score: float,
    confidence: float,
    negative_checks: int,
) -> bool:
    return (
        total_score >= V3_QUALITY_GATES["min_score"]
        and technical_score >= V3_QUALITY_GATES["min_technical_score"]
        and fundamental_score >= V3_QUALITY_GATES["min_fundamental_score"]
        and confidence >= V3_QUALITY_GATES["min_confidence"]
        and negative_checks <= V3_QUALITY_GATES["max_negative_checks"]
    )


def _adjusted_rank_score(
    technical_score: float,
    fundamental_score: float,
    context_score: float,
    confidence: float,
    negative_checks: int,
) -> float:
    capped_context = max(min(context_score, 1.0), -1.0)
    penalty = max(0, negative_checks - 2) * 0.4
    adjusted = technical_score + (fundamental_score * 1.15) + capped_context + (confidence - 0.75) - penalty
    return round(adjusted, 2)


def _build_context(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "df": get_historical_data(symbol, period="1y", interval="1d"),
        "ticker_info": get_ticker_info(symbol),
        "financials": get_financials(symbol),
        "balance_sheet": get_balance_sheet(symbol),
        "screener": get_screener_snapshot(symbol),
    }


def run_v3_validation(symbol: str) -> dict[str, Any]:
    """
    Run the V3 shortlist validation subset on one stock.
    """
    try:
        ctx = _build_context(symbol)
        df = ctx["df"]
        if df is None or df.empty or len(df) < 200:
            return {
                "symbol": symbol,
                "passed": False,
                "score": 0.0,
                "technical_score": 0.0,
                "fundamental_score": 0.0,
                "context_score": 0.0,
                "confidence": 0.0,
                "checks": [],
                "summary": "Insufficient history for V3 validation",
            }

        checks = []
        technical_score = 0.0
        fundamental_score = 0.0
        context_score = 0.0
        available = 0

        for bucket, name, weight, fn in V3_CHECKS:
            signal, detail = fn(ctx)
            score = _v3_signal_score(signal, weight)
            check = {
                "bucket": bucket,
                "name": name,
                "signal": signal,
                "detail": detail,
                "weight": weight,
                "score": score,
            }
            checks.append(check)
            if signal != "UNAVAILABLE":
                available += 1

            if bucket == "technical":
                technical_score += score
            elif bucket == "fundamental":
                fundamental_score += score
            else:
                context_score += score

        total_score = round(technical_score + fundamental_score + context_score, 2)
        confidence = round(available / len(V3_CHECKS), 2) if V3_CHECKS else 0.0
        positive_checks = [c for c in checks if c["score"] > 0]
        negative_checks = [c for c in checks if c["score"] < 0]
        positives = [c["name"] for c in positive_checks][:4]
        negatives = [c["name"] for c in negative_checks][:3]
        adjusted_score = _adjusted_rank_score(
            technical_score=technical_score,
            fundamental_score=fundamental_score,
            context_score=context_score,
            confidence=confidence,
            negative_checks=len(negative_checks),
        )
        passed = _passes_quality_gates(
            total_score=total_score,
            technical_score=technical_score,
            fundamental_score=fundamental_score,
            confidence=confidence,
            negative_checks=len(negative_checks),
        )

        return {
            "symbol": symbol,
            "passed": passed,
            "score": total_score,
            "adjusted_score": adjusted_score,
            "technical_score": round(technical_score, 2),
            "fundamental_score": round(fundamental_score, 2),
            "context_score": round(context_score, 2),
            "confidence": confidence,
            "checks": checks,
            "top_positives": positives,
            "top_negatives": negatives,
            "summary": (
                f"V3 score {total_score:+.2f} | adj {adjusted_score:+.2f} | "
                f"tech {technical_score:+.2f} | fund {fundamental_score:+.2f} | "
                f"ctx {context_score:+.2f} | conf {confidence:.2f}"
            ),
        }
    except Exception as e:
        logger.error(f"V3 validation error for {symbol}: {e}")
        return {
            "symbol": symbol,
            "passed": False,
            "score": 0.0,
            "adjusted_score": 0.0,
            "technical_score": 0.0,
            "fundamental_score": 0.0,
            "context_score": 0.0,
            "confidence": 0.0,
            "checks": [],
            "summary": f"V3 validation error: {e}",
        }


def rank_v3_candidates(
    symbols: list[str],
    max_workers: int = 6,
) -> dict[str, Any]:
    """
    Run V3 validation across shortlisted symbols and return ranked candidates.
    """
    clean_symbols = [symbol for symbol in symbols if symbol]
    if not clean_symbols:
        return {
            "total": 0,
            "ranked": [],
            "passed": [],
            "failed": [],
        }

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(run_v3_validation, symbol): symbol for symbol in clean_symbols}
        for future in as_completed(futures):
            results.append(future.result())

    ranked = sorted(
        results,
        key=lambda item: (
            item.get("adjusted_score", item["score"]),
            item["fundamental_score"],
            item["technical_score"],
            item["confidence"],
        ),
        reverse=True,
    )
    passed = [item for item in ranked if item["passed"]]
    failed = [item for item in ranked if not item["passed"]]

    return {
        "total": len(ranked),
        "ranked": ranked,
        "passed": passed,
        "failed": failed,
        "top10": passed[:10],
    }
