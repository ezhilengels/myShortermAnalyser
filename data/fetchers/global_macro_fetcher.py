"""
global_macro_fetcher.py — Lightweight global macro data helpers used by
non-scoring additional signals.
"""

from __future__ import annotations

import logging
import re
from calendar import month_abbr, monthrange
from datetime import datetime
from io import StringIO

import requests
import pandas as pd

from data.cache.redis_cache import cache_get, cache_set

logger = logging.getLogger(__name__)

TRADING_ECONOMICS_CHINA_PMI_URL = "https://tradingeconomics.com/china/manufacturing-pmi"
NSDL_SECTOR_FLOW_URL = (
    "https://pilot.fpi.nsdl.co.in/StaticReports/"
    "Fortnightly_Sector_wise_FII_Investment_Data/FIIInvestSector_{stamp}.html"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def get_china_manufacturing_pmi() -> dict:
    """
    Fetch the latest China manufacturing PMI snapshot.
    Uses a public TradingEconomics page as a lightweight monthly source.
    Returns:
        {
            "source_ok": bool,
            "source": str,
            "value": float,
            "previous": float,
            "detail": str,
        }
    """
    key = "china_manufacturing_pmi_latest"
    cached = cache_get(key)
    if cached:
        return cached

    try:
        resp = requests.get(TRADING_ECONOMICS_CHINA_PMI_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        text = resp.text

        value_match = re.search(
            r"Manufacturing PMI in China (?:increased|decreased|was unchanged)?\s*to\s*([0-9]+(?:\.[0-9]+)?)\s*points\s*in\s*([A-Za-z]+)",
            text,
            flags=re.IGNORECASE,
        )
        prev_match = re.search(
            r"from\s*([0-9]+(?:\.[0-9]+)?)\s*in\s*([A-Za-z]+)",
            text,
            flags=re.IGNORECASE,
        )

        if not value_match:
            result = {
                "source_ok": False,
                "source": "TradingEconomics",
                "value": 0.0,
                "previous": 0.0,
                "detail": "China PMI page did not expose a parseable value",
            }
            cache_set(key, result, 21600)
            return result

        value = float(value_match.group(1))
        month = value_match.group(2)
        previous = float(prev_match.group(1)) if prev_match else 0.0
        prev_month = prev_match.group(2) if prev_match else "previous month"

        result = {
            "source_ok": True,
            "source": "TradingEconomics",
            "value": value,
            "previous": previous,
            "detail": f"China manufacturing PMI {value:.1f} in {month} vs {previous:.1f} in {prev_month}",
        }
        cache_set(key, result, 604800)  # 7 days; PMI updates monthly
        return result
    except Exception as e:
        logger.error(f"China PMI fetch failed: {e}")
        return {
            "source_ok": False,
            "source": "TradingEconomics",
            "value": 0.0,
            "previous": 0.0,
            "detail": "China PMI source unavailable",
        }


def _candidate_fortnight_stamps(limit: int = 18) -> list[str]:
    now = datetime.now()
    year = now.year
    month = now.month
    stamps: list[str] = []

    while len(stamps) < limit:
        last_day = monthrange(year, month)[1]
        for day in (last_day, 15):
            stamp = f"{month_abbr[month]}{day:02d}{year}"
            if stamp not in stamps:
                stamps.append(stamp)
                if len(stamps) >= limit:
                    break
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return stamps


def _safe_float(value) -> float:
    try:
        text = str(value).replace(",", "").strip()
        return float(text)
    except Exception:
        return 0.0


def _parse_nsdl_sector_flow(html: str) -> dict | None:
    tables = pd.read_html(StringIO(html))
    if not tables:
        return None

    df = tables[0]
    if df.shape[0] < 6 or df.shape[1] < 52:
        return None

    sector_col = 1
    current_col = None
    previous_col = None

    for col in range(df.shape[1]):
        level0 = str(df.iloc[0, col])
        level1 = str(df.iloc[1, col])
        level2 = str(df.iloc[2, col])
        level3 = str(df.iloc[3, col])
        if "Net Investment" in level0 and "IN INR Cr." in level1 and level2 == "Equity" and level3 == "Equity":
            if previous_col is None:
                previous_col = col
            else:
                current_col = col

    if current_col is None or previous_col is None:
        return None

    current_period = str(df.iloc[0, current_col])
    previous_period = str(df.iloc[0, previous_col])
    rows = {}

    for idx in range(4, len(df)):
        sector = str(df.iloc[idx, sector_col]).strip()
        if not sector or sector.lower() in {"nan", "total"}:
            continue
        rows[sector] = {
            "current_equity_inr_cr": _safe_float(df.iloc[idx, current_col]),
            "previous_equity_inr_cr": _safe_float(df.iloc[idx, previous_col]),
        }

    return {
        "source_ok": True,
        "source": "NSDL fortnightly sector FPI report",
        "current_period": current_period,
        "previous_period": previous_period,
        "rows": rows,
    }


def get_latest_fpi_sector_flow() -> dict:
    """
    Fetch the latest available official NSDL fortnightly sector-wise FPI flow report.
    """
    key = "nsdl_latest_fpi_sector_flow"
    cached = cache_get(key)
    if cached:
        return cached

    for stamp in _candidate_fortnight_stamps():
        url = NSDL_SECTOR_FLOW_URL.format(stamp=stamp)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            parsed = _parse_nsdl_sector_flow(resp.text)
            if not parsed:
                continue
            parsed["url"] = url
            cache_set(key, parsed, 604800)
            return parsed
        except Exception as e:
            logger.warning(f"NSDL sector flow fetch failed for {stamp}: {e}")

    return {
        "source_ok": False,
        "source": "NSDL fortnightly sector FPI report",
        "rows": {},
    }
