"""
bse_fetcher.py — Scrapes BSE India insider/promoter trading data.
Used for Secret Strategy #4 (Promoter Activity).
"""

import logging
import requests
from datetime import datetime, timedelta
from data.cache.redis_cache import cache_get, cache_set

logger = logging.getLogger(__name__)

BSE_INSIDER_URL = "https://www.bseindia.com/corporates/Insider_Trading_new.html"
BSE_INSIDER_API = "https://api.bseindia.com/BseIndiaAPI/api/InsiderTrading/w"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bseindia.com/",
    "Accept":  "application/json, text/plain, */*",
}


def _get_bse_session() -> requests.Session:
    """Warm a BSE session so the API is less likely to return HTML/challenge pages."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(BSE_INSIDER_URL, timeout=10)
    except Exception as e:
        logger.warning(f"BSE session warm-up failed: {e}")
    return session


def fetch_insider_transactions(nse_symbol: str, days: int = 30) -> dict:
    """
    Fetch promoter/insider trading transactions for the given stock (last N days).
    Returns {'buys': int, 'sells': int, 'transactions': list}
    """
    key = f"bse_insider_{nse_symbol}_{days}"
    cached = cache_get(key)
    if cached:
        return cached

    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    to_date   = datetime.now().strftime("%Y%m%d")

    params = {
        "strName":    nse_symbol,
        "dtFromDate": from_date,
        "dtToDate":   to_date,
    }

    try:
        session = _get_bse_session()
        resp = session.get(BSE_INSIDER_API, params=params, timeout=10)
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "json" not in content_type:
            logger.warning(
                f"BSE insider API returned non-JSON content for {nse_symbol}: "
                f"{content_type or 'unknown'}"
            )
            return {
                "buys": 0, "sells": 0, "transactions": [],
                "source_ok": False,
                "source_note": f"Non-JSON response: {content_type or 'unknown'}",
            }

        data = resp.json()

        transactions = data if isinstance(data, list) else data.get("Table", [])
        buys  = 0
        sells = 0
        buy_qty = 0.0
        sell_qty = 0.0
        tx_list = []

        for tx in transactions:
            tx_type = (tx.get("Acqui_Disp", "") or "").upper()
            name    = tx.get("Name", "") or tx.get("PersonName", "")
            qty_raw = (
                tx.get("NoofShares")
                or tx.get("NoOfShare")
                or tx.get("Noofsecurity")
                or tx.get("Qty")
                or 0
            )
            try:
                qty = float(str(qty_raw).replace(",", "") or 0)
            except Exception:
                qty = 0.0

            if "ACQUI" in tx_type or "BUY" in tx_type or "PURCHASE" in tx_type:
                buys += 1
                buy_qty += qty
                tx_list.append({"type": "BUY", "name": name, "qty": qty})
            elif "DISP" in tx_type or "SELL" in tx_type:
                sells += 1
                sell_qty += qty
                tx_list.append({"type": "SELL", "name": name, "qty": qty})

        result = {
            "buys": buys,
            "sells": sells,
            "buy_qty": buy_qty,
            "sell_qty": sell_qty,
            "transactions": tx_list,
            "source_ok": True,
            "source_note": "",
        }
        cache_set(key, result, 3600)  # 1 hour
        return result

    except Exception as e:
        logger.error(f"BSE insider fetch failed for {nse_symbol}: {e}")
        return {
            "buys": 0, "sells": 0, "transactions": [],
            "buy_qty": 0.0, "sell_qty": 0.0,
            "source_ok": False,
            "source_note": str(e),
        }
