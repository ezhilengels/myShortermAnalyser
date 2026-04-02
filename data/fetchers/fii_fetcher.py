"""
fii_fetcher.py — Fetches FII/DII cash market data AND FII index futures
positions from NSE India's official API.
"""

import logging
from typing import Any
from data.fetchers.nse_fetcher import get_nse_session
from data.cache.redis_cache import cache_get, cache_set
from config import CACHE_TTL

logger = logging.getLogger(__name__)

FII_DII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"


def fetch_fii_dii_data() -> dict:
    """
    Fetch FII and DII cash market net buy/sell from NSE.
    Returns a structured dict with cash and futures data.
    """
    key = "fii_dii_data"
    cached = cache_get(key)
    if cached:
        return cached

    session = get_nse_session()
    try:
        resp = session.get(FII_DII_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = _parse_fii_dii(data)
        cache_set(key, result, CACHE_TTL["fii_dii"])
        return result
    except Exception as e:
        logger.error(f"FII/DII fetch failed: {e}")
        return _empty_fii_result(source_note=str(e))


def _parse_fii_dii(raw: list) -> dict:
    """Parse the raw NSE fiidiiTradeReact response into a clean dict."""
    try:
        fii_cash_row = _find_row(raw, ("fii", "cash")) or (raw[0] if raw else {})
        dii_cash_row = _find_row(raw, ("dii", "cash")) or (raw[1] if len(raw) > 1 else {})
        futures_row = _find_row(raw, ("fii", "index", "future"))

        fii_cash_net = _row_net_value(fii_cash_row)
        dii_cash_net = _row_net_value(dii_cash_row)

        fii_idx_buy = _extract_amount(futures_row, ("buyAmount", "buyAmt", "buyValue"))
        fii_idx_sell = _extract_amount(futures_row, ("sellAmount", "sellAmt", "sellValue"))
        fii_idx_net = _row_net_value(futures_row)
        if fii_idx_net == 0.0 and (fii_idx_buy or fii_idx_sell):
            fii_idx_net = fii_idx_buy - fii_idx_sell

        source_ok = bool(futures_row or fii_cash_row or dii_cash_row)
        source_note = ""
        if not futures_row:
            source_note = "Could not confidently locate FII index futures row in NSE response"

        return {
            "fii_cash_net":     fii_cash_net,
            "dii_cash_net":     dii_cash_net,
            "fii_futures_buy":  fii_idx_buy,
            "fii_futures_sell": fii_idx_sell,
            "fii_futures_net":  fii_idx_net,
            "source_ok":        source_ok,
            "source_note":      source_note,
        }
    except Exception as e:
        logger.error(f"FII/DII parse error: {e}")
        return _empty_fii_result(source_note=str(e))


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_amount(row: dict, candidate_keys: tuple[str, ...]) -> float:
    if not isinstance(row, dict):
        return 0.0
    for key in candidate_keys:
        if key in row:
            try:
                return float(row.get(key, 0) or 0)
            except Exception:
                continue
    return 0.0


def _row_net_value(row: dict) -> float:
    if not isinstance(row, dict):
        return 0.0
    for key in ("netVal", "netValue", "netAmount", "net"):
        if key in row:
            try:
                return float(row.get(key, 0) or 0)
            except Exception:
                continue
    buy = _extract_amount(row, ("buyAmount", "buyAmt", "buyValue"))
    sell = _extract_amount(row, ("sellAmount", "sellAmt", "sellValue"))
    return buy - sell


def _find_row(rows: list[dict], keywords: tuple[str, ...]) -> dict:
    if not isinstance(rows, list):
        return {}

    best_row = {}
    best_score = -1
    for row in rows:
        if not isinstance(row, dict):
            continue
        haystack = " ".join(_normalize_text(v) for v in row.values())
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_score = score
            best_row = row

    return best_row if best_score > 0 else {}


def _empty_fii_result(source_note: str = "") -> dict:
    return {
        "fii_cash_net":     0.0,
        "dii_cash_net":     0.0,
        "fii_futures_buy":  0.0,
        "fii_futures_sell": 0.0,
        "fii_futures_net":  0.0,
        "source_ok":        False,
        "source_note":      source_note,
    }
