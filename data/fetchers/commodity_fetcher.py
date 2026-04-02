"""
commodity_fetcher.py — Fetches commodity prices via yfinance.
Covers: LME Aluminium, Zinc, COMEX Silver, Brent Crude, Copper.
"""

import logging
from data.cache.redis_cache import cache_get, cache_set
from config import CACHE_TTL
from data.fetchers.yfinance_fetcher import get_market_history

logger = logging.getLogger(__name__)

# Yahoo Finance commodity tickers
COMMODITY_TICKERS = {
    "ALI=F": "LME Aluminium",
    "ZNC=F": "LME Zinc",
    "SI=F":  "COMEX Silver",
    "BZ=F":  "Brent Crude",
    "HG=F":  "COMEX Copper",
    "^NSEI": "Nifty 50",
    "^INDIAVIX": "India VIX",
    "^VIX":  "US VIX",
}


def get_commodity_price(ticker: str) -> dict:
    """
    Return last price and 2-day % change for a commodity ticker.
    Returns dict: {ticker, name, price, change_pct}
    """
    key = f"commodity_{ticker}"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        hist = get_market_history(ticker, period="5d", interval="1d")
        if hist.empty or len(hist) < 2:
            return {"ticker": ticker, "name": COMMODITY_TICKERS.get(ticker, ticker), "price": 0.0, "change_pct": 0.0}

        last_price = hist["Close"].iloc[-1]
        prev_price = hist["Close"].iloc[-3] if len(hist) >= 3 else hist["Close"].iloc[-2]
        change_pct = ((last_price - prev_price) / prev_price) * 100 if prev_price != 0 else 0.0

        result = {
            "ticker":     ticker,
            "name":       COMMODITY_TICKERS.get(ticker, ticker),
            "price":      round(float(last_price), 2),
            "change_pct": round(float(change_pct), 2),
        }
        cache_set(key, result, CACHE_TTL["commodity"])
        return result
    except Exception as e:
        logger.error(f"Commodity fetch error for {ticker}: {e}")
        return {"ticker": ticker, "name": COMMODITY_TICKERS.get(ticker, ticker), "price": 0.0, "change_pct": 0.0}


def get_all_commodities() -> dict:
    """Return prices for all tracked commodities as a dict keyed by ticker."""
    results = {}
    for ticker in ["ALI=F", "ZNC=F", "SI=F", "BZ=F", "HG=F"]:
        results[ticker] = get_commodity_price(ticker)
    return results


def get_india_vix() -> float:
    """Return current India VIX value."""
    data = get_commodity_price("^INDIAVIX")
    return data.get("price", 0.0)


def get_us_vix() -> float:
    """Return current US VIX value."""
    data = get_commodity_price("^VIX")
    return data.get("price", 0.0)
