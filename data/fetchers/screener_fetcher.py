"""
screener_fetcher.py — India-focused company fundamentals fallback via Screener.
Used to improve core fundamental checks when Yahoo fields are weak or missing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from config import CACHE_TTL, SCREENER_COMPANY_CODES
from data.cache.redis_cache import cache_get, cache_set

logger = logging.getLogger(__name__)

SCREENER_BASE_URL = "https://www.screener.in/company/{code}/consolidated/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def resolve_screener_code(symbol: str) -> str:
    raw = (symbol or "").replace(".NS", "").replace(".BO", "").upper()
    return SCREENER_COMPANY_CODES.get(raw, raw)


def _parse_number(value: str) -> float | None:
    text = (value or "").strip()
    if not text or "login" in text.lower() or "x,xxx" in text.lower():
        return None

    text = text.replace("%", "").replace("₹", "").replace(",", "").replace("Cr.", "").replace("Cr", "")
    text = text.replace("+", "").strip()
    if text in {"", "-"}:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _find_section(soup: BeautifulSoup, title: str):
    for section in soup.select("section"):
        heading = section.select_one("h2")
        if heading and heading.get_text(" ", strip=True) == title:
            return section
    return None


def _parse_ratio_section(soup: BeautifulSoup) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for item in soup.select("ul#top-ratios li"):
        name_tag = item.select_one("span.name")
        value_tag = item.select_one("span.number")
        if not name_tag or not value_tag:
            continue
        key = name_tag.get_text(" ", strip=True).lower()
        value = _parse_number(value_tag.get_text(" ", strip=True))
        if value is not None:
            ratios[key] = value
    return ratios


def _parse_table(section) -> dict[str, Any]:
    table = section.select_one("table")
    if table is None:
        return {"headers": [], "rows": {}}

    rows = table.select("tr")
    headers = [cell.get_text(" ", strip=True) for cell in rows[0].select("th,td")][1:]
    parsed_rows: dict[str, list[float | None]] = {}

    for row in rows[1:]:
        cells = [cell.get_text(" ", strip=True) for cell in row.select("th,td")]
        if len(cells) < 2:
            continue
        label = cells[0]
        parsed_rows[label] = [_parse_number(cell) for cell in cells[1:]]

    return {"headers": headers, "rows": parsed_rows}


def _series_metrics(values: list[float | None]) -> dict[str, float]:
    nums = [float(v) for v in values if v is not None]
    if len(nums) < 2:
        return {"latest": 0.0, "prev": 0.0, "yoy": 0.0, "cagr": 0.0}

    latest = nums[-1]
    prev = nums[-2]
    yoy = ((latest - prev) / abs(prev)) * 100 if prev else 0.0

    cagr = 0.0
    oldest = nums[0]
    periods = len(nums) - 1
    if oldest > 0 and latest > 0 and periods > 0:
        cagr = (((latest / oldest) ** (1 / periods)) - 1) * 100

    return {
        "latest": latest,
        "prev": prev,
        "yoy": yoy,
        "cagr": cagr,
    }


def _row_metrics(rows: dict[str, list[float | None]], labels: list[str]) -> dict[str, float]:
    """Return series metrics for the first matching row label (exact or fuzzy)."""
    # 1. Try exact matches first
    for label in labels:
        if label in rows:
            return _series_metrics(rows.get(label, []))

    # 2. Try case-insensitive fuzzy matches
    for label in labels:
        clean_target = label.lower().replace("+", "").strip()
        for row_label in rows.keys():
            clean_row = row_label.lower().replace("+", "").strip()
            if clean_target in clean_row or clean_row in clean_target:
                return _series_metrics(rows.get(row_label, []))

    return {"latest": 0.0, "prev": 0.0, "yoy": 0.0, "cagr": 0.0}

def get_screener_snapshot(symbol: str) -> dict:

    code = resolve_screener_code(symbol)
    key = f"screener_snapshot_{code}"
    cached = cache_get(key)
    if cached and "mf_latest" in ((cached.get("shareholding") or {})):
        return cached

    url = SCREENER_BASE_URL.format(code=code)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        ratios = _parse_ratio_section(soup)
        profit_loss = _parse_table(_find_section(soup, "Profit & Loss")) if _find_section(soup, "Profit & Loss") else {"headers": [], "rows": {}}
        quarterly = _parse_table(_find_section(soup, "Quarterly Results")) if _find_section(soup, "Quarterly Results") else {"headers": [], "rows": {}}
        balance_sheet = _parse_table(_find_section(soup, "Balance Sheet")) if _find_section(soup, "Balance Sheet") else {"headers": [], "rows": {}}
        cash_flow = _parse_table(_find_section(soup, "Cash Flows")) if _find_section(soup, "Cash Flows") else {"headers": [], "rows": {}}
        shareholding = _parse_table(_find_section(soup, "Shareholding Pattern")) if _find_section(soup, "Shareholding Pattern") else {"headers": [], "rows": {}}

        bs_rows = balance_sheet.get("rows", {})
        pl_rows = profit_loss.get("rows", {})
        cf_rows = cash_flow.get("rows", {})
        
        equity_capital = _row_metrics(bs_rows, ["Equity Capital"])
        reserves = _row_metrics(bs_rows, ["Reserves"])
        borrowings = _row_metrics(bs_rows, ["Borrowings +", "Borrowings"])
        
        # Helper to get first matching row values
        def _get_row(rows_dict, candidates):
            for c in candidates:
                if c in rows_dict: return rows_dict[c]
            return []

        sales_row = _get_row(pl_rows, ["Sales +", "Revenue +"])
        profit_row = _get_row(pl_rows, ["Net Profit +", "Net Profit"])
        q_sales_row = _get_row(quarterly.get("rows", {}), ["Sales +", "Revenue +"])
        q_profit_row = _get_row(quarterly.get("rows", {}), ["Net Profit +", "Net Profit"])

        current_price = ratios.get("current price", 0.0)
        book_value = ratios.get("book value", 0.0)
        pb = (current_price / book_value) if current_price and book_value else 0.0

        promoter_metrics = _row_metrics(shareholding.get("rows", {}), ["Promoters +", "Promoter +", "Promoters"])
        fii_metrics = _row_metrics(shareholding.get("rows", {}), ["FIIs +", "FII +", "FIIs"])
        dii_metrics = _row_metrics(shareholding.get("rows", {}), ["DIIs +", "DII +", "DIIs"])
        mf_metrics = _row_metrics(shareholding.get("rows", {}), ["Mutual Funds +", "Mutual Funds", "MFs +", "MF +"])

        result = {
            "source_ok": True,
            "source": "Screener",
            "code": code,
            "url": url,
            "ratios": {
                "pe": ratios.get("stock p/e", 0.0),
                "roe": ratios.get("roe", 0.0),
                "roce": ratios.get("roce", 0.0),
                "book_value": book_value,
                "price_to_book": pb,
                "current_price": current_price,
                "market_cap_cr": ratios.get("market cap", 0.0),
                "dividend_yield": ratios.get("dividend yield", 0.0),
                "face_value": ratios.get("face value", 0.0),
            },
            "growth": {
                "annual_sales": _series_metrics(sales_row),
                "annual_profit": _series_metrics(profit_row),
                "quarterly_sales": _series_metrics(q_sales_row),
                "quarterly_profit": _series_metrics(q_profit_row),
            },
            "margins": {
                "annual_opm_latest": _row_metrics(pl_rows, ["OPM %", "Operating Profit Margin"]).get("latest", 0.0),
                "quarterly_opm_latest": _row_metrics(quarterly.get("rows", {}), ["OPM %"]).get("latest", 0.0),
            },
            "profit_loss": {
                "pbt_latest": _row_metrics(pl_rows, ["Profit before tax", "PBT", "Financing Profit"]).get("latest", 0.0),
                "tax_latest": _row_metrics(pl_rows, ["Tax %"]).get("latest", 0.0),
                "interest_latest": _row_metrics(pl_rows, ["Interest", "Finance Costs"]).get("latest", 0.0),
                "depreciation_latest": _row_metrics(pl_rows, ["Depreciation", "Depreciation & amortization"]).get("latest", 0.0),
            },
            "balance_sheet": {
                "borrowings_latest": _row_metrics(bs_rows, ["Borrowings +", "Borrowings", "Total Debt"]).get("latest", 0.0),
                "equity_latest": _series_metrics([
                    (cap or 0.0) + (res or 0.0)
                    for cap, res in zip(bs_rows.get("Equity Capital", []), bs_rows.get("Reserves", []))
                    if cap is not None or res is not None
                ]).get("latest", 0.0),
                "investments_latest": _row_metrics(bs_rows, ["Investments"]).get("latest", 0.0),
                "other_liabilities_latest": _row_metrics(bs_rows, ["Other Liabilities +", "Other Liabilities"]).get("latest", 0.0),
            },
            "cash_flow": {
                "operating_latest": _row_metrics(cf_rows, ["Cash from Operating Activity +", "Cash from Operating Activity", "CFO"]).get("latest", 0.0),
                "investing_latest": _row_metrics(cf_rows, ["Cash from Investing Activity +", "Cash from Investing Activity"]).get("latest", 0.0),
                "capex_latest": abs(_row_metrics(cf_rows, ["Fixed assets purchased", "Capital Expenditure", "Asset purchase", "Investing Activities"]).get("latest", 0.0)),
            },
            "shareholding": {
                "promoter_latest": promoter_metrics.get("latest", 0.0),
                "promoter_prev": promoter_metrics.get("prev", 0.0),
                "fii_latest": fii_metrics.get("latest", 0.0),
                "fii_prev": fii_metrics.get("prev", 0.0),
                "dii_latest": dii_metrics.get("latest", 0.0),
                "dii_prev": dii_metrics.get("prev", 0.0),
                "mf_latest": mf_metrics.get("latest", 0.0),
                "mf_prev": mf_metrics.get("prev", 0.0),
                "mf_yoy": mf_metrics.get("yoy", 0.0),
            },
        }
        cache_set(key, result, 3600)
        return result
    except Exception as e:
        logger.error(f"Screener fetch failed for {symbol}: {e}")
        return {
            "source_ok": False,
            "source": "Screener",
            "code": code,
            "url": url,
        }
