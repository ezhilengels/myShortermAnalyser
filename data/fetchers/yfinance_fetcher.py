"""
yfinance_fetcher.py — Fetch stock price, historical OHLCV, and fundamental info
from Yahoo Finance using the yfinance library.
"""

import logging
import json
import yfinance as yf
import pandas as pd
from data.cache.redis_cache import cache_get, cache_set
from config import CACHE_TTL

logger = logging.getLogger(__name__)


def _serialize_df(df: pd.DataFrame) -> dict:
    """Convert a DataFrame into a JSON-safe payload for cache storage."""
    return {
        "__type__": "dataframe",
        "split": json.loads(df.to_json(orient="split", date_format="iso")),
    }


def _deserialize_df(payload) -> pd.DataFrame:
    """Restore a cached DataFrame payload back into a pandas DataFrame."""
    if not payload:
        return pd.DataFrame()

    if isinstance(payload, dict) and payload.get("__type__") == "dataframe":
        split = payload.get("split", {})
        df = pd.DataFrame(split.get("data", []), columns=split.get("columns", []))

        if split.get("index") is not None:
            df.index = split["index"]
            try:
                df.index = pd.to_datetime(df.index)
            except (TypeError, ValueError):
                pass
        return df

    return pd.DataFrame(payload)


def get_ticker_info(symbol: str) -> dict:
    """Return .info dict for a ticker (cached 3 min)."""
    key = f"yf_info_{symbol}"
    cached = cache_get(key)
    if cached:
        return cached
    try:
        info = yf.Ticker(symbol).info
        if not isinstance(info, dict):
            logger.warning(f"Unexpected yfinance info payload for {symbol}")
            return {}
        cache_set(key, info, CACHE_TTL["stock_price"])
        return info
    except Exception as e:
        logger.error(f"yfinance info error for {symbol}: {e}")
        return {}


def get_historical_data(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Return OHLCV DataFrame for technical analysis.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
    interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk
    """
    key = f"yf_hist_{symbol}_{period}_{interval}"
    cached = cache_get(key)
    if cached:
        return _deserialize_df(cached)
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()
        cache_set(key, _serialize_df(df), CACHE_TTL["stock_price"])
        return df
    except Exception as e:
        logger.error(f"yfinance history error for {symbol}: {e}")
        return pd.DataFrame()


def get_1h_data(symbol: str) -> pd.DataFrame:
    """Return last 5 days of 1-hour candles for intraday trend check."""
    return get_historical_data(symbol, period="5d", interval="1h")


def get_financials(symbol: str) -> pd.DataFrame:
    """Return annual income statement for earnings/revenue growth."""
    key = f"yf_financials_{symbol}"
    cached = cache_get(key)
    if cached:
        return _deserialize_df(cached)
    try:
        ticker = yf.Ticker(symbol)
        fin = ticker.financials
        if fin is not None and not fin.empty:
            cache_set(key, _serialize_df(fin), 3600)  # 1 hour
        return fin if fin is not None else pd.DataFrame()
    except Exception as e:
        logger.error(f"yfinance financials error for {symbol}: {e}")
        return pd.DataFrame()


def get_balance_sheet(symbol: str) -> pd.DataFrame:
    """Return annual balance sheet for fallback equity/debt calculations."""
    key = f"yf_balance_sheet_{symbol}"
    cached = cache_get(key)
    if cached:
        return _deserialize_df(cached)
    try:
        ticker = yf.Ticker(symbol)
        bs = ticker.balance_sheet
        if bs is not None and not bs.empty:
            cache_set(key, _serialize_df(bs), 3600)  # 1 hour
        return bs if bs is not None else pd.DataFrame()
    except Exception as e:
        logger.error(f"yfinance balance sheet error for {symbol}: {e}")
        return pd.DataFrame()


def get_current_price(symbol: str) -> float:
    """Quick helper to get only the current price."""
    info = get_ticker_info(symbol)
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    return float(price)


def get_market_history(symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    """
    Lightweight alias for non-stock Yahoo symbols such as indices, sectors, and VIX.
    Uses the same safe history path and returns an empty DataFrame on failure.
    """
    return get_historical_data(symbol, period=period, interval=interval)
