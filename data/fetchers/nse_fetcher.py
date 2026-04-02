"""
nse_fetcher.py — NSE India session + option chain + delivery % + PCR fetcher.
NSE requires a live session (cookies from homepage) before hitting any API.
"""

import time
import logging
import requests
from datetime import datetime
from io import StringIO
from typing import Optional
from urllib.parse import quote

import pandas as pd
from config import NSE_HEADERS
from data.cache.redis_cache import cache_get, cache_set
from config import CACHE_TTL, FNO_STOCKS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# NSE SESSION
# ─────────────────────────────────────────────

def get_nse_session() -> requests.Session:
    """
    Build a requests Session with NSE cookies.
    Always hit the homepage first so NSE sets the required cookies.
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        # Step 1: Get cookies from homepage
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
        # Step 2: Hit market data page to refresh cookies
        session.get("https://www.nseindia.com/market-data/live-equity-market", timeout=10)
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"NSE session warm-up failed: {e}")
    return session


def _get_json_with_retry(session: requests.Session, url: str, *, retries: int = 2) -> dict:
    """Fetch JSON from NSE with a light retry after refreshing cookies."""
    last_error = None

    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()

            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "json" not in content_type:
                raise ValueError(
                    f"Expected JSON from NSE, got {content_type or 'unknown content type'}"
                )

            return resp.json()
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(1)
                session = get_nse_session()

    raise last_error


def _get_text_with_retry(session: requests.Session, url: str, *, retries: int = 2) -> str:
    """Fetch text content from NSE with a light retry after refreshing cookies."""
    last_error = None

    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(1)
                session = get_nse_session()

    raise last_error


def _today_ymd() -> str:
    return datetime.now().strftime("%d-%m-%Y")


def _parse_deal_rows(rows: list[dict]) -> list[dict]:
    parsed = []
    for row in rows or []:
        normalized = {str(k).strip(): v for k, v in row.items()}
        parsed.append(
            {
                "symbol": str(
                    normalized.get("Symbol")
                    or normalized.get("SYMBOL")
                    or normalized.get("symbol")
                    or ""
                ).upper(),
                "clientName": str(
                    normalized.get("Client Name")
                    or normalized.get("CLIENT NAME")
                    or normalized.get("clientName")
                    or normalized.get("client")
                    or ""
                ).strip(),
                "buySell": str(
                    normalized.get("Buy/Sell")
                    or normalized.get("BUY/SELL")
                    or normalized.get("buySell")
                    or normalized.get("buyOrSell")
                    or ""
                ).upper(),
                "quantityTraded": float(
                    normalized.get("Quantity Traded")
                    or normalized.get("QUANTITY TRADED")
                    or normalized.get("quantityTraded")
                    or normalized.get("quantity")
                    or 0
                ),
                "tradePrice": float(
                    normalized.get("Trade Price / Wght. Avg. Price")
                    or normalized.get("TRADE PRICE / WGHT. AVG. PRICE")
                    or normalized.get("tradePrice")
                    or normalized.get("price")
                    or 0
                ),
            }
        )
    return parsed


def _fetch_historical_deals(option_type: str) -> Optional[list]:
    """
    Fetch deal rows from NSE's current historical endpoint used by the live report page.
    """
    session = get_nse_session()
    today = _today_ymd()
    url = (
        "https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
        f"?optionType={quote(option_type)}&from={today}&to={today}"
    )
    try:
        text = _get_text_with_retry(session, url)

        content_type = ""
        try:
            probe = session.get(url, timeout=10)
            content_type = (probe.headers.get("Content-Type") or "").lower()
            text = probe.text
        except Exception:
            pass

        if "json" in content_type:
            data = requests.models.complexjson.loads(text)
            if isinstance(data, dict):
                rows = data.get("data") or data.get("rows") or data.get("value") or []
            elif isinstance(data, list):
                rows = data
            else:
                rows = []
            return _parse_deal_rows(rows)

        tables = pd.read_html(StringIO(text))
        if not tables:
            return []
        rows = tables[0].to_dict(orient="records")
        return _parse_deal_rows(rows)
    except Exception as e:
        logger.error(f"NSE historical deal fetch failed for {option_type}: {e}")
        return None


def _has_option_chain_data(data: dict) -> bool:
    """Return True when NSE returned a usable option-chain payload."""
    if not isinstance(data, dict) or not data:
        return False

    records = data.get("records", {}).get("data", [])
    filtered = data.get("filtered", {})
    return bool(records) or bool(filtered)


def _parse_expiry_date(value: str):
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def get_nearest_expiry_records(option_chain_data: dict) -> tuple[str, list[dict]]:
    """Return the nearest available expiry and its records only."""
    records = option_chain_data.get("records", {}).get("data", []) or []
    if not records:
        return "", []

    expiries = sorted(
        {
            record.get("expiryDate")
            for record in records
            if record.get("expiryDate")
        },
        key=lambda value: _parse_expiry_date(value) or datetime.max,
    )
    if not expiries:
        return "", records

    nearest = expiries[0]
    filtered = [record for record in records if record.get("expiryDate") == nearest]
    return nearest, filtered


def get_market_status_hint(nse_symbol: str = "NIFTY") -> dict:
    """
    Infer whether the NSE market appears closed today from live endpoint behavior.
    Returns a dict like:
      {
        "is_closed": bool,
        "reason": str,
      }
    """
    key = f"nse_market_status_hint_{nse_symbol}"
    cached = cache_get(key)
    if cached:
        return cached

    session = get_nse_session()
    quote_url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol}&section=trade_info"
    nifty_oc_url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

    is_closed = False
    reason = "Live NSE market data appears available"

    try:
        quote_data = _get_json_with_retry(session, quote_url)
        trade_info = quote_data.get("marketDeptOrderBook", {}).get("tradeInfo", {})
        total_volume = float(trade_info.get("totalTradedVolume", 0) or 0)
        last_price = trade_info.get("lastPrice")
        last_update_time = trade_info.get("lastUpdateTime")

        nifty_oc = _get_json_with_retry(session, nifty_oc_url)
        nifty_oc_available = _has_option_chain_data(nifty_oc)

        if (
            not nifty_oc_available and
            (total_volume == 0 or (last_price in (None, "", 0) and not last_update_time))
        ):
            is_closed = True
            reason = "NSE market appears closed today or holiday data is not being published"
        elif total_volume == 0:
            reason = "No traded volume reported yet today"
    except Exception as e:
        reason = f"Could not confirm market status from NSE ({e})"

    result = {"is_closed": is_closed, "reason": reason}
    cache_set(key, result, 300)
    return result


# ─────────────────────────────────────────────
# OPTION CHAIN
# ─────────────────────────────────────────────

def fetch_option_chain(nse_symbol: str) -> dict:
    """
    Fetch full option chain from NSE for an equity stock.
    Returns raw JSON dict from NSE API.
    """
    key = f"nse_oc_{nse_symbol}"
    last_good_key = f"{key}_last_good"
    cached = cache_get(key)
    if cached:
        return cached

    session = get_nse_session()
    url = f"https://www.nseindia.com/api/option-chain-equities?symbol={nse_symbol}"
    try:
        data = _get_json_with_retry(session, url)
        if not _has_option_chain_data(data):
            stale = cache_get(last_good_key)
            if stale:
                logger.warning(
                    f"NSE returned empty option chain for {nse_symbol}; using last known good data"
                )
                return stale
            logger.warning(f"NSE returned empty option chain for {nse_symbol}")
            return {}
        cache_set(key, data, CACHE_TTL["option_chain"])
        cache_set(last_good_key, data, 172800)
        return data
    except Exception as e:
        stale = cache_get(last_good_key)
        if stale:
            logger.warning(
                f"NSE option chain fetch failed for {nse_symbol}; using last known good data ({e})"
            )
            return stale
        logger.error(f"NSE option chain fetch failed for {nse_symbol}: {e}")
        return {}


def fetch_nifty_option_chain() -> dict:
    """Fetch Nifty index option chain (for PCR calculation)."""
    key = "nse_oc_NIFTY"
    last_good_key = f"{key}_last_good"
    cached = cache_get(key)
    if cached:
        return cached

    session = get_nse_session()
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    try:
        data = _get_json_with_retry(session, url)
        if not _has_option_chain_data(data):
            stale = cache_get(last_good_key)
            if stale:
                logger.warning("NSE returned empty NIFTY option chain; using last known good data")
                return stale
            logger.warning("NSE returned empty NIFTY option chain")
            return {}
        cache_set(key, data, CACHE_TTL["option_chain"])
        cache_set(last_good_key, data, 172800)
        return data
    except Exception as e:
        stale = cache_get(last_good_key)
        if stale:
            logger.warning(f"NSE Nifty OC fetch failed; using last known good data ({e})")
            return stale
        logger.error(f"NSE Nifty OC fetch failed: {e}")
        return {}


# ─────────────────────────────────────────────
# MAX PAIN CALCULATOR
# ─────────────────────────────────────────────

def calculate_max_pain(option_chain_data: dict) -> float:
    """
    Calculate max pain strike price from NSE option chain data.
    Max pain = strike where total dollar pain for all option holders is maximum.
    """
    try:
        records = option_chain_data.get("records", {}).get("data", [])
        if not records:
            return 0.0

        pain_dict: dict[float, float] = {}

        for record in records:
            strike = float(record.get("strikePrice", 0))
            ce_oi  = record.get("CE", {}).get("openInterest", 0) or 0
            pe_oi  = record.get("PE", {}).get("openInterest", 0) or 0
            pain_dict[strike] = {"CE_OI": ce_oi, "PE_OI": pe_oi}

        strikes = sorted(pain_dict.keys())
        total_pain: dict[float, float] = {}

        for test_strike in strikes:
            pain = 0.0
            for strike, oi_data in pain_dict.items():
                # CE holders lose if price < strike
                ce_loss = max(0, strike - test_strike) * oi_data["CE_OI"]
                # PE holders lose if price > strike
                pe_loss = max(0, test_strike - strike) * oi_data["PE_OI"]
                pain += ce_loss + pe_loss
            total_pain[test_strike] = pain

        # Max pain = strike with minimum total pain for writers = maximum pain for holders
        max_pain_strike = min(total_pain, key=total_pain.get)
        return max_pain_strike

    except Exception as e:
        logger.error(f"Max pain calculation error: {e}")
        return 0.0


def get_option_chain_context(option_chain_data: dict, current_price: float = 0.0) -> dict:
    """
    Build a lightweight summary around the nearest expiry so strategy checks
    do not over-react to stale or far-expiry positioning.
    """
    expiry, records = get_nearest_expiry_records(option_chain_data)
    if not records:
        return {
            "expiry": "",
            "record_count": 0,
            "atm_strike": 0.0,
            "atm_call_oi": 0.0,
            "atm_put_oi": 0.0,
            "atm_pcr": 1.0,
            "total_call_oi": 0.0,
            "total_put_oi": 0.0,
        }

    total_call_oi = 0.0
    total_put_oi = 0.0
    atm_record = None
    best_distance = float("inf")

    for record in records:
        strike = float(record.get("strikePrice", 0) or 0)
        ce_oi = float(record.get("CE", {}).get("openInterest", 0) or 0)
        pe_oi = float(record.get("PE", {}).get("openInterest", 0) or 0)
        total_call_oi += ce_oi
        total_put_oi += pe_oi

        distance = abs(strike - current_price) if current_price > 0 else 0
        if atm_record is None or distance < best_distance:
            best_distance = distance
            atm_record = record

    atm_call_oi = float(atm_record.get("CE", {}).get("openInterest", 0) or 0) if atm_record else 0.0
    atm_put_oi = float(atm_record.get("PE", {}).get("openInterest", 0) or 0) if atm_record else 0.0
    atm_pcr = round(atm_put_oi / atm_call_oi, 3) if atm_call_oi > 0 else 1.0

    return {
        "expiry": expiry,
        "record_count": len(records),
        "atm_strike": float(atm_record.get("strikePrice", 0) or 0) if atm_record else 0.0,
        "atm_call_oi": atm_call_oi,
        "atm_put_oi": atm_put_oi,
        "atm_pcr": atm_pcr,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
    }


# ─────────────────────────────────────────────
# PCR (Put-Call Ratio)
# ─────────────────────────────────────────────

def calculate_pcr(option_chain_data: dict) -> float:
    """
    Calculate PCR from option chain data.
    PCR = Total Put OI / Total Call OI
    """
    try:
        context = get_option_chain_context(option_chain_data)
        total_ce_oi = context.get("total_call_oi", 0) or 0
        total_pe_oi = context.get("total_put_oi", 0) or 0

        if total_ce_oi == 0 or total_pe_oi == 0:
            filtered = option_chain_data.get("filtered", {})
            total_ce_oi = filtered.get("CE", {}).get("totOI", 0) or 0
            total_pe_oi = filtered.get("PE", {}).get("totOI", 0) or 0

        if total_ce_oi == 0:
            return 1.0

        return round(total_pe_oi / total_ce_oi, 3)
    except Exception as e:
        logger.error(f"PCR calculation error: {e}")
        return 1.0


# ─────────────────────────────────────────────
# DELIVERY PERCENTAGE
# ─────────────────────────────────────────────

def fetch_delivery_data(nse_symbol: str) -> dict:
    """
    Fetch delivery/trade info from NSE quote-equity API.
    Returns dict with delivery %, total volume, etc.
    """
    key = f"nse_delivery_{nse_symbol}"
    cached = cache_get(key)
    if cached:
        return cached

    session = get_nse_session()
    url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol}&section=trade_info"
    try:
        data = _get_json_with_retry(session, url)
        result = _parse_delivery_data(data)
        cache_set(key, result, CACHE_TTL["stock_price"])
        return result
    except Exception as e:
        logger.error(f"NSE delivery fetch failed for {nse_symbol}: {e}")
        return {}


def _parse_delivery_data(raw: dict) -> dict:
    """Parse NSE trade_info response to extract delivery metrics."""
    try:
        trade_info = raw.get("marketDeptOrderBook", {}).get("tradeInfo", {})
        total_traded_volume = trade_info.get("totalTradedVolume", 0) or 0
        delivery_qty        = trade_info.get("deliveryQuantity", 0) or 0
        delivery_pct        = trade_info.get("deliveryToTradedQuantity", 0) or 0

        if delivery_pct == 0 and total_traded_volume > 0 and delivery_qty > 0:
            delivery_pct = (delivery_qty / total_traded_volume) * 100

        return {
            "total_volume":   float(total_traded_volume),
            "delivery_qty":   float(delivery_qty),
            "delivery_pct":   float(delivery_pct),
        }
    except Exception as e:
        logger.error(f"Delivery parse error: {e}")
        return {}


# ─────────────────────────────────────────────
# BULK DEAL / BLOCK DEAL SCANNER
# ─────────────────────────────────────────────

def fetch_bulk_deals() -> Optional[list]:
    """
    Fetch today's bulk deals from NSE.
    A bulk deal is >= 0.5% of company equity traded in a single transaction.
    Returns list of deal dicts with keys: symbol, clientName, buySell, quantityTraded, tradePrice.
    """
    key = "nse_bulk_deals_today"
    cached = cache_get(key)
    if cached is not None:
        return cached

    session = get_nse_session()
    url = "https://www.nseindia.com/api/bulk-deals"
    try:
        data = _get_json_with_retry(session, url)
        deals = data.get("data", []) if isinstance(data, dict) else []
        cache_set(key, deals, 1800)   # refresh every 30 min
        return deals
    except Exception as e:
        logger.debug(f"Legacy NSE bulk deals endpoint failed, trying historical fallback: {e}")
        deals = _fetch_historical_deals("bulk_deals")
        if deals is not None:
            cache_set(key, deals, 1800)
            return deals
        logger.error(f"NSE bulk deals fetch failed and fallback unavailable: {e}")
        return None


def fetch_block_deals() -> Optional[list]:
    """
    Fetch today's block deals from NSE.
    Block deals are >= Rs 10 Cr or 5 lakh shares traded in the pre-open block window.
    Returns list of deal dicts with keys: symbol, clientName, buySell, quantityTraded, tradePrice.
    """
    key = "nse_block_deals_today"
    cached = cache_get(key)
    if cached is not None:
        return cached

    session = get_nse_session()
    url = "https://www.nseindia.com/api/block-deals"
    try:
        data = _get_json_with_retry(session, url)
        deals = data.get("data", []) if isinstance(data, dict) else []
        cache_set(key, deals, 1800)
        return deals
    except Exception as e:
        logger.debug(f"Legacy NSE block deals endpoint failed, trying historical fallback: {e}")
        deals = _fetch_historical_deals("block_deals")
        if deals is not None:
            cache_set(key, deals, 1800)
            return deals
        logger.error(f"NSE block deals fetch failed and fallback unavailable: {e}")
        return None


def remember_delivery_baseline(nse_symbol: str, delivery_data: dict) -> None:
    """Store the latest useful delivery snapshot for future relative comparisons."""
    if not delivery_data:
        return

    delivery_pct = float(delivery_data.get("delivery_pct", 0) or 0)
    total_volume = float(delivery_data.get("total_volume", 0) or 0)
    if delivery_pct <= 0 or total_volume <= 0:
        return

    cache_set(f"nse_delivery_baseline_{nse_symbol}", delivery_data, 604800)  # 7 days


def get_delivery_baseline(nse_symbol: str) -> dict:
    """Return the last known useful delivery snapshot if available."""
    return cache_get(f"nse_delivery_baseline_{nse_symbol}") or {}
