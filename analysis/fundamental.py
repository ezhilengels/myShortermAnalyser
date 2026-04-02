"""
fundamental.py — Fundamental Analysis Checks 7 through 10.

Check 7:  Earnings & Revenue Growth (YoY)
Check 8:  Profit Margin & ROE
Check 9:  Debt Level (Debt/Equity)
Check 10: Valuation (Trailing PE vs Industry PE)
"""

import logging
from typing import Optional
import pandas as pd
from config import (
    INDUSTRY_PE,
    VALUATION_PEERS,
    VALUATION_PE_DISCOUNT,
    VALUATION_PB_UNDERVALUED,
    VALUATION_PE_FAIR,
    VALUATION_PE_CAUTION,
    VALUATION_PB_CAUTION,
)
from data.fetchers.screener_fetcher import get_screener_snapshot

logger = logging.getLogger(__name__)


def _screener_ratio(screener_data: dict, key: str) -> float:
    return float(((screener_data or {}).get("ratios") or {}).get(key, 0) or 0)


def _screener_growth(screener_data: dict, section: str, metric: str) -> float:
    return float((((screener_data or {}).get("growth") or {}).get(section) or {}).get(metric, 0) or 0)


def _screener_margin(screener_data: dict, key: str) -> float:
    return float(((screener_data or {}).get("margins") or {}).get(key, 0) or 0)


def _screener_balance(screener_data: dict, key: str) -> float:
    return float(((screener_data or {}).get("balance_sheet") or {}).get(key, 0) or 0)


def _find_first_matching_row(df: pd.DataFrame, keys: list[str]) -> pd.Series:
    """Return the first matching financial-statement row for any candidate key."""
    if df is None or df.empty:
        return pd.Series(dtype=float)

    for key in keys:
        matches = df.loc[df.index.str.contains(key, case=False, regex=False)]
        if not matches.empty:
            return matches.iloc[0].dropna()
    return pd.Series(dtype=float)


def _calculate_yoy_growth(financials: pd.DataFrame, row_key: str) -> float:
    """Helper: Calculate Year-over-Year growth % for a financials row."""
    try:
        if financials is None or financials.empty:
            return 0.0
        row = _find_first_matching_row(financials, [row_key])
        if row.empty:
            return 0.0
        values = row.values
        if len(values) < 2:
            return 0.0
        latest = float(values[0])
        prev   = float(values[1])
        if prev == 0:
            return 0.0
        return ((latest - prev) / abs(prev)) * 100
    except Exception as e:
        logger.error(f"YoY growth calc error for {row_key}: {e}")
        return 0.0


def _derive_roe(financials: pd.DataFrame, balance_sheet: pd.DataFrame) -> float:
    """Derive ROE % from statements when the summary field is missing."""
    try:
        income_row = _find_first_matching_row(financials, [
            "Net Income From Continuing Operation Net Minority Interest",
            "Net Income",
            "Normalized Income",
        ])
        equity_row = _find_first_matching_row(balance_sheet, [
            "Stockholders Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
        ])

        if income_row.empty or equity_row.empty:
            return 0.0

        net_income = float(income_row.iloc[0])
        equity_values = equity_row.values[:2]
        if len(equity_values) == 0:
            return 0.0

        avg_equity = float(sum(equity_values) / len(equity_values))
        if avg_equity == 0:
            return 0.0

        return (net_income / avg_equity) * 100
    except Exception as e:
        logger.error(f"ROE derivation error: {e}")
        return 0.0


def _derive_debt_to_equity(balance_sheet: pd.DataFrame) -> Optional[float]:
    """Derive debt/equity % from the balance sheet when summary field is missing."""
    try:
        debt_row = _find_first_matching_row(balance_sheet, [
            "Total Debt",
            "Total Debt And Capital Lease Obligation",
            "Net Debt",
            "Long Term Debt",
        ])
        equity_row = _find_first_matching_row(balance_sheet, [
            "Stockholders Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
        ])

        if debt_row.empty or equity_row.empty:
            return None

        debt = float(debt_row.iloc[0])
        equity = float(equity_row.iloc[0])
        if equity == 0:
            return None

        return (debt / equity) * 100
    except Exception as e:
        logger.error(f"Debt/equity derivation error: {e}")
        return None


def _calculate_cagr_from_row(row: pd.Series) -> float:
    """Calculate CAGR % from a financial-statement row ordered newest -> oldest."""
    try:
        values = [float(v) for v in row.values if pd.notna(v)]
        if len(values) < 3:
            return 0.0

        latest = values[0]
        oldest = values[-1]
        periods = len(values) - 1
        if oldest <= 0 or latest <= 0 or periods <= 0:
            return 0.0

        return (((latest / oldest) ** (1 / periods)) - 1) * 100
    except Exception as e:
        logger.error(f"CAGR calc error: {e}")
        return 0.0


def _peer_median_valuation(stock_symbol: str) -> dict:
    """Fetch a simple live peer-median valuation snapshot using cached Yahoo info."""
    try:
        from data.fetchers.yfinance_fetcher import get_ticker_info

        peers = VALUATION_PEERS.get(stock_symbol, [])
        if not peers:
            return {}

        pe_values = []
        pb_values = []
        ev_ebitda_values = []

        for peer in peers:
            info = get_ticker_info(peer)
            pe = info.get("trailingPE") or info.get("forwardPE")
            pb = info.get("priceToBook")
            ev_ebitda = info.get("enterpriseToEbitda")

            if pe and float(pe) > 0:
                pe_values.append(float(pe))
            if pb and float(pb) > 0:
                pb_values.append(float(pb))
            if ev_ebitda and float(ev_ebitda) > 0:
                ev_ebitda_values.append(float(ev_ebitda))

        result = {}
        if len(pe_values) >= 2:
            result["pe_median"] = float(pd.Series(pe_values).median())
        if len(pb_values) >= 2:
            result["pb_median"] = float(pd.Series(pb_values).median())
        if len(ev_ebitda_values) >= 2:
            result["ev_ebitda_median"] = float(pd.Series(ev_ebitda_values).median())
        return result
    except Exception as e:
        logger.error(f"Peer valuation benchmark error for {stock_symbol}: {e}")
        return {}


def check_earnings_growth(ticker_info: dict, financials: pd.DataFrame, screener_data: Optional[dict] = None) -> tuple[str, str]:
    """
    Check 7 — Earnings & Revenue Growth YoY.
    Returns (signal, detail_message)
    """
    try:
        # Try from yfinance .info first (quick path)
        revenue_growth = float(ticker_info.get("revenueGrowth") or 0) * 100
        earnings_growth = float(ticker_info.get("earningsGrowth") or 0) * 100
        quarterly_growth = float(ticker_info.get("earningsQuarterlyGrowth") or 0) * 100

        revenue_row = _find_first_matching_row(financials, ["Total Revenue"])
        earnings_row = _find_first_matching_row(financials, [
            "Net Income From Continuing Operation Net Minority Interest",
            "Net Income",
        ])

        revenue_cagr = _calculate_cagr_from_row(revenue_row)
        earnings_cagr = _calculate_cagr_from_row(earnings_row)

        screener_sales_yoy = _screener_growth(screener_data, "annual_sales", "yoy")
        screener_profit_yoy = _screener_growth(screener_data, "annual_profit", "yoy")
        screener_sales_cagr = _screener_growth(screener_data, "annual_sales", "cagr")
        screener_profit_cagr = _screener_growth(screener_data, "annual_profit", "cagr")
        screener_quarterly_profit = _screener_growth(screener_data, "quarterly_profit", "yoy")

        # Fallback to financials DataFrame
        if revenue_growth == 0 and financials is not None and not financials.empty:
            revenue_growth  = _calculate_yoy_growth(financials, "Total Revenue")
            earnings_growth = _calculate_yoy_growth(
                financials, "Net Income From Continuing Operation Net Minority Interest"
            ) or _calculate_yoy_growth(financials, "Net Income")

        revenue_trend = max(revenue_growth, revenue_cagr, screener_sales_yoy, screener_sales_cagr)
        earnings_trend = max(earnings_growth, earnings_cagr, screener_profit_yoy, screener_profit_cagr)
        quarterly_hint = max(quarterly_growth, screener_quarterly_profit)

        if revenue_trend > 20 and earnings_trend > 25:
            return "STRONG", (
                f"Revenue trend +{revenue_trend:.1f}%, PAT trend +{earnings_trend:.1f}%"
                f"{f', quarterly +{quarterly_hint:.1f}%' if quarterly_hint else ''} — strong growth!"
            )
        elif revenue_trend > 10 and earnings_trend > 15:
            return "BULLISH", (
                f"Revenue trend +{revenue_trend:.1f}%, PAT trend +{earnings_trend:.1f}% — healthy growth"
            )
        elif revenue_trend > 0 and earnings_trend > 0:
            return "MODERATE", (
                f"Revenue trend +{revenue_trend:.1f}%, PAT trend +{earnings_trend:.1f}% — modest growth"
            )
        elif revenue_trend == 0 and earnings_trend == 0:
            return "UNAVAILABLE", "Earnings growth data unavailable"
        else:
            return "WEAK", (
                f"Revenue trend {revenue_trend:.1f}%, PAT trend {earnings_trend:.1f}% — weak/declining earnings"
            )
    except Exception as e:
        logger.error(f"Earnings growth check error: {e}")
        return "UNAVAILABLE", "Earnings growth check error"


def check_margins(
    ticker_info: dict,
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    screener_data: Optional[dict] = None,
) -> tuple[str, str]:
    """
    Check 8 — Profit Margin & Return on Equity.
    Returns (signal, detail_message)
    """
    try:
        roe            = float(ticker_info.get("returnOnEquity") or 0) * 100
        profit_margin  = float(ticker_info.get("profitMargins")  or 0) * 100
        gross_margin   = float(ticker_info.get("grossMargins")   or 0) * 100
        operating_margin = float(ticker_info.get("operatingMargins") or 0) * 100

        screener_roe = _screener_ratio(screener_data, "roe")
        screener_roce = _screener_ratio(screener_data, "roce")
        screener_opm = _screener_margin(screener_data, "annual_opm_latest")

        if screener_roe > 0:
            roe = max(roe, screener_roe)
        if screener_opm > 0:
            operating_margin = max(operating_margin, screener_opm)

        if roe == 0:
            roe = _derive_roe(financials, balance_sheet)

        if roe == 0 and profit_margin == 0:
            return "UNAVAILABLE", "Margin/ROE data unavailable"

        if roe == 0 and profit_margin > 0:
            return "UNAVAILABLE", (
                f"Net Margin {profit_margin:.1f}% available, but ROE could not be derived"
            )

        if profit_margin == 0 and roe > 0:
            return "UNAVAILABLE", (
                f"ROE {roe:.1f}% available, but net margin data unavailable"
            )

        if roe > 22 and profit_margin > 18:
            return "STRONG", (
                f"ROE {roe:.1f}%, Net Margin {profit_margin:.1f}%"
                f"{f', ROCE {screener_roce:.1f}%' if screener_roce else ''}"
                f"{f', Op Margin {operating_margin:.1f}%' if operating_margin else ''} — excellent profitability"
            )
        elif roe > 15 and profit_margin > 10:
            return "BULLISH", f"ROE {roe:.1f}%, Net Margin {profit_margin:.1f}% — good margins"
        elif roe > 8 and profit_margin > 5:
            return "MODERATE", f"ROE {roe:.1f}%, Net Margin {profit_margin:.1f}% — moderate"
        else:
            return "WEAK", f"ROE {roe:.1f}%, Net Margin {profit_margin:.1f}% — thin margins"
    except Exception as e:
        logger.error(f"Margins check error: {e}")
        return "UNAVAILABLE", "Margins check error"


def check_debt(ticker_info: dict, balance_sheet: pd.DataFrame, screener_data: Optional[dict] = None) -> tuple[str, str]:
    """
    Check 9 — Debt-to-Equity Level.
    yfinance reports D/E as % (e.g., 0.25 = 25%).
    Returns (signal, detail_message)
    """
    try:
        # yfinance debtToEquity is sometimes in % (e.g. 25.5 means 25.5%)
        de = ticker_info.get("debtToEquity")
        if de is None:
            de = _derive_debt_to_equity(balance_sheet)
        screener_borrowings = _screener_balance(screener_data, "borrowings_latest")
        screener_equity = _screener_balance(screener_data, "equity_latest")
        screener_de = None
        if screener_equity > 0:
            screener_de = (screener_borrowings / screener_equity) * 100
        if de is None:
            de = screener_de
            if de is None:
                return "UNAVAILABLE", "Debt/Equity data unavailable"
        de = float(de)

        if de == 0:
            return "EXCELLENT", "Debt/Equity 0% — debt-free company!"
        elif de < 15:
            return "EXCELLENT", f"Debt/Equity {de:.1f}% — nearly debt-free"
        elif de < 50:
            return "GOOD", f"Debt/Equity {de:.1f}% — low, manageable debt"
        elif de < 100:
            return "MODERATE", f"Debt/Equity {de:.1f}% — moderate leverage, monitor"
        elif de < 200:
            return "CAUTION", f"Debt/Equity {de:.1f}% — high leverage, risk factor"
        else:
            return "HIGH_RISK", f"Debt/Equity {de:.1f}% — very high debt, avoid"
    except Exception as e:
        logger.error(f"Debt check error: {e}")
        return "UNAVAILABLE", "Debt check error"


from v4.valuation_runner import run_v4_valuation

def check_valuation_v4(stock_symbol: str) -> tuple[str, str]:
    """
    Check 10 — Strategy V4 Multi-Model Intrinsic Valuation.
    """
    try:
        res = run_v4_valuation(stock_symbol)
        if not res.get("success"):
            return "UNAVAILABLE", res.get("reason", "Valuation failed")
        
        iv = res["iv"]
        cmp = res["cmp"]
        mos = res["margin_of_safety"]
        model = res["model_used"]
        verdict = res["verdict"]
        
        ey_yield = res.get("earnings_yield", 0.0)
        ey_verdict = res.get("yield_verdict", "N/A")
        
        detail = (
            f"IV ({model}) ₹{iv:.2f} vs CMP ₹{cmp:.2f} | "
            f"MoS: {mos:+.1f}% → {verdict} | "
            f"EY: {ey_yield:.1f}% ({ey_verdict})"
        )
        
        # Map V4 verdict to signal
        signal_map = {
            "UNDERVALUED": "STRONG",
            "FAIRLY_VALUED": "BULLISH",
            "OVERVALUED": "CAUTION",
            "UNAVAILABLE": "UNAVAILABLE"
        }
        return signal_map.get(verdict, "MODERATE"), detail
    except Exception as e:
        logger.error(f"V4 valuation check error: {e}")
        return "UNAVAILABLE", "V4 valuation check error"

def check_peer_valuation_v4(stock_symbol: str) -> tuple[str, str]:
    """
    Check 11 — Peer Relative Valuation (V4 MoS comparison).
    Compares the stock's Margin of Safety against the median MoS of its peers.
    """
    try:
        from config import VALUATION_PEERS
        peers = VALUATION_PEERS.get(stock_symbol, [])
        if not peers:
            return "INFO", "No peers defined for relative comparison"
        
        main_res = run_v4_valuation(stock_symbol)
        if not main_res.get("success"):
            return "UNAVAILABLE", "Main stock valuation failed"
        
        main_mos = main_res["margin_of_safety"]
        peer_mos_list = []
        
        for p in peers:
            p_res = run_v4_valuation(p)
            if p_res.get("success"):
                peer_mos_list.append(p_res["margin_of_safety"])
        
        if not peer_mos_list:
            return "INFO", "Peer valuations unavailable for comparison"
        
        peer_median_mos = float(pd.Series(peer_mos_list).median())
        diff = main_mos - peer_median_mos
        
        if diff > 15:
            return "STRONG", f"Top in sector! MoS {main_mos:+.1f}% vs Peer Median {peer_median_mos:+.1f}% (Diff: {diff:+.1f}%)"
        elif diff > 5:
            return "BULLISH", f"Relatively cheap: MoS {main_mos:+.1f}% vs Peer Median {peer_median_mos:+.1f}% (Diff: {diff:+.1f}%)"
        elif diff < -15:
            return "WEAK", f"Sector laggard: MoS {main_mos:+.1f}% vs Peer Median {peer_median_mos:+.1f}% (Diff: {diff:+.1f}%)"
        else:
            return "MODERATE", f"Sector inline: MoS {main_mos:+.1f}% vs Peer Median {peer_median_mos:+.1f}% (Diff: {diff:+.1f}%)"
            
    except Exception as e:
        logger.error(f"Peer V4 valuation check error: {e}")
        return "UNAVAILABLE", "Peer V4 valuation check error"

def run_all_fundamental_checks(
    stock_symbol: str,
    ticker_info: dict,
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
) -> list[dict]:
    """
    Run all fundamental checks and return structured results list.
    """
    screener_data = get_screener_snapshot(stock_symbol)

    checks = [
        (7,  "Earnings Growth",    check_earnings_growth(ticker_info, financials, screener_data)),
        (8,  "Profit Margin/ROE",  check_margins(ticker_info, financials, balance_sheet, screener_data)),
        (9,  "Debt Level",         check_debt(ticker_info, balance_sheet, screener_data)),
        (10, "Intrinsic Valuation", check_valuation_v4(stock_symbol)),
    ]

    return [
        {
            "check_number": num,
            "category":     "Fundamental",
            "name":         name,
            "signal":       result[0],
            "detail":       result[1],
        }
        for num, name, result in checks
    ]

def run_additional_fundamental_signals(stock_symbol: str) -> list[dict]:
    """
    Run non-scoring fundamental signals.
    """
    signals = [
        ("Peer Valuation (V4)", check_peer_valuation_v4(stock_symbol)),
    ]

    return [
        {
            "category": "Additional Signals",
            "name": name,
            "signal": result[0],
            "detail": result[1],
        }
        for name, result in signals
    ]
