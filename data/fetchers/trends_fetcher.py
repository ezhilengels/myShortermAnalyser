"""
trends_fetcher.py — Google Trends helpers for non-scoring additional signals.
"""

from __future__ import annotations

import logging
import warnings

from pytrends.request import TrendReq

from config import STOCK_NAMES
from data.cache.redis_cache import cache_get, cache_set

logger = logging.getLogger(__name__)


def _candidate_terms(stock_symbol: str) -> list[str]:
    raw = (stock_symbol or "").replace(".NS", "").replace(".BO", "")
    display = STOCK_NAMES.get(stock_symbol, raw)
    candidates = [
        f"{display} share",
        f"{display} stock",
        display,
        raw,
    ]
    seen = set()
    ordered = []
    for item in candidates:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(item.strip())
    return ordered


def get_google_trends_snapshot(stock_symbol: str) -> dict:
    """
    Return a conservative Google Trends snapshot for the stock in India.
    Uses 3 months of daily data and compares the latest week to the prior month.
    """
    key = f"google_trends_snapshot_{stock_symbol}"
    cached = cache_get(key)
    if cached:
        return cached

    terms = _candidate_terms(stock_symbol)
    pytrends = TrendReq(hl="en-IN", tz=330)

    for term in terms:
        try:
            pytrends.build_payload([term], timeframe="today 3-m", geo="IN")
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*Downcasting object dtype arrays on \\.fillna.*",
                    category=FutureWarning,
                )
                frame = pytrends.interest_over_time()
            if frame is None or frame.empty or term not in frame.columns:
                continue

            series = frame[term]
            if "isPartial" in frame.columns:
                series = series[~frame["isPartial"].fillna(False)]
            series = series.dropna()
            if len(series) < 35:
                continue

            latest_week = float(series.tail(7).mean())
            prior_month = series.iloc[-35:-7]
            baseline = float(prior_month.mean()) if len(prior_month) >= 14 else 0.0
            peak = float(series.max())

            result = {
                "source_ok": True,
                "source": "Google Trends",
                "term": term,
                "latest_week": latest_week,
                "baseline": baseline,
                "peak": peak,
                "ratio": (latest_week / baseline) if baseline > 0 else 0.0,
            }
            cache_set(key, result, 43200)
            return result
        except Exception as e:
            logger.warning(f"Google Trends fetch failed for term '{term}': {e}")

    return {
        "source_ok": False,
        "source": "Google Trends",
        "term": terms[0] if terms else stock_symbol,
        "latest_week": 0.0,
        "baseline": 0.0,
        "peak": 0.0,
        "ratio": 0.0,
    }
