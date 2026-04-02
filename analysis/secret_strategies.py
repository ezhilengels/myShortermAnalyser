"""
secret_strategies.py — Secret Strategy Checks 16 through 21.

Check 16: Max Pain Theory (Option Chain)
Check 17: Delivery Percentage (Operator Detection)
Check 18: PCR (Put-Call Ratio) Reversal Trap
Check 19: Promoter / Insider Activity (BSE)
Check 20: FII Index Futures Position
Check 21: 52-Week Low Reversal Formula
"""

import logging
from typing import Optional

from data.fetchers.nse_fetcher     import (
    fetch_option_chain, fetch_nifty_option_chain,
    calculate_max_pain, calculate_pcr, get_option_chain_context,
    fetch_delivery_data, get_market_status_hint,
    remember_delivery_baseline, get_delivery_baseline
)
from data.fetchers.fii_fetcher     import fetch_fii_dii_data
from data.fetchers.yfinance_fetcher import get_current_price
from data.fetchers.screener_fetcher import get_screener_snapshot
from config import FNO_STOCKS

logger = logging.getLogger(__name__)


def _format_expiry_suffix(context: dict) -> str:
    expiry = context.get("expiry", "")
    if not expiry:
        return ""
    return f" for {expiry}"


def _market_closed_message(stock_symbol: str) -> str:
    nse_symbol = stock_symbol.replace(".NS", "")
    status = get_market_status_hint(nse_symbol)
    if status.get("is_closed"):
        return "NSE market appears closed today — derivative and delivery signals are unavailable"
    return ""


def check_max_pain(stock_symbol: str, ticker_info: dict) -> tuple[str, str]:
    """
    Check 16 — Max Pain Theory.
    Only applicable to F&O eligible stocks.
    """
    try:
        nse_symbol = stock_symbol.replace(".NS", "")

        if nse_symbol not in FNO_STOCKS:
            return "UNAVAILABLE", f"{nse_symbol} is not F&O eligible — Max Pain N/A"

        closed_msg = _market_closed_message(stock_symbol)
        if closed_msg:
            return "UNAVAILABLE", closed_msg

        oc_data = fetch_option_chain(nse_symbol)
        if not oc_data:
            return "UNAVAILABLE", "Option chain data unavailable today (market may be closed or NSE returned empty data)"

        max_pain_strike = calculate_max_pain(oc_data)
        if max_pain_strike == 0:
            return "UNAVAILABLE", "Max Pain calculation failed"

        current_price = float(
            ticker_info.get("currentPrice") or
            ticker_info.get("regularMarketPrice") or
            get_current_price(stock_symbol)
        )

        if current_price == 0:
            return "UNAVAILABLE", "Price data unavailable for max pain"

        context = get_option_chain_context(oc_data, current_price)
        expiry_suffix = _format_expiry_suffix(context)
        atm_pcr = float(context.get("atm_pcr", 1.0) or 1.0)
        record_count = int(context.get("record_count", 0) or 0)
        if record_count < 5:
            return "UNAVAILABLE", f"Nearest-expiry option chain too thin{expiry_suffix}"

        diff_pct = ((max_pain_strike - current_price) / current_price) * 100

        if diff_pct > 5 and atm_pcr >= 0.95:
            return "BULLISH", (
                f"Nearest-expiry max pain{expiry_suffix} at ₹{max_pain_strike:.0f} is {diff_pct:.1f}% above CMP "
                f"₹{current_price:.2f}; ATM PCR {atm_pcr:.2f} supports upward pinning"
            )
        elif diff_pct > 2:
            return "INFO", (
                f"Nearest-expiry max pain{expiry_suffix} is slightly above CMP, but ATM PCR {atm_pcr:.2f} "
                "is not strong enough for a high-conviction directional call"
            )
        elif diff_pct < -5 and atm_pcr <= 1.05:
            return "BEARISH", (
                f"Nearest-expiry max pain{expiry_suffix} at ₹{max_pain_strike:.0f} is {abs(diff_pct):.1f}% below CMP "
                f"₹{current_price:.2f}; ATM PCR {atm_pcr:.2f} does not show strong put support"
            )
        elif diff_pct < -2:
            return "INFO", (
                f"Nearest-expiry max pain{expiry_suffix} is mildly below CMP, but the option positioning is not one-sided"
            )
        else:
            return "NEUTRAL", (
                f"Nearest-expiry max pain{expiry_suffix} ₹{max_pain_strike:.0f} is near CMP ₹{current_price:.2f} — no strong pinning bias"
            )
    except Exception as e:
        logger.error(f"Max Pain check error for {stock_symbol}: {e}")
        return "UNAVAILABLE", "Max Pain check error"


def check_delivery_percentage(stock_symbol: str) -> tuple[str, str]:
    """
    Check 17 — Delivery Percentage (Smart Money / Operator Detection).
    High delivery % + high volume = real institutional buying.
    """
    try:
        nse_symbol   = stock_symbol.replace(".NS", "")
        closed_msg = _market_closed_message(stock_symbol)
        if closed_msg:
            return "UNAVAILABLE", closed_msg

        delivery_data = fetch_delivery_data(nse_symbol)

        if not delivery_data:
            return "UNAVAILABLE", "Delivery data unavailable from NSE"

        delivery_pct  = delivery_data.get("delivery_pct", 0)
        total_volume  = delivery_data.get("total_volume", 0)

        if total_volume == 0:
            return "UNAVAILABLE", "No traded volume reported today — market may be closed or data not published yet"

        if delivery_pct == 0:
            return "UNAVAILABLE", "Delivery percentage data not available today"

        baseline = get_delivery_baseline(nse_symbol)
        baseline_pct = float(baseline.get("delivery_pct", 0) or 0)
        baseline_vol = float(baseline.get("total_volume", 0) or 0)

        remember_delivery_baseline(nse_symbol, delivery_data)

        relative_pct = delivery_pct - baseline_pct if baseline_pct > 0 else 0.0
        volume_ratio = (total_volume / baseline_vol) if baseline_vol > 0 else 1.0

        # High delivery + better than recent baseline = more believable accumulation
        if delivery_pct >= 65 and (relative_pct >= 5 or volume_ratio >= 1.2):
            return "OPERATOR_ACCUMULATION", (
                f"Delivery {delivery_pct:.1f}% with {volume_ratio:.2f}x volume vs recent baseline — strong accumulation"
            )
        elif delivery_pct >= 55 and (relative_pct >= 0 or volume_ratio >= 1.0):
            return "BULLISH", (
                f"Delivery {delivery_pct:.1f}% with {volume_ratio:.2f}x baseline volume — healthy participation"
            )
        elif delivery_pct >= 45:
            return "INFO", f"Delivery {delivery_pct:.1f}% — decent, but not a clear accumulation signal"
        elif delivery_pct >= 35:
            return "NEUTRAL", f"Delivery {delivery_pct:.1f}% — moderate participation"
        else:
            if volume_ratio >= 1.5:
                return "CAUTION", (
                    f"Delivery only {delivery_pct:.1f}% despite {volume_ratio:.2f}x baseline volume — churn is high"
                )
            return "NOISE", f"Delivery only {delivery_pct:.1f}% — mostly intraday speculation"
    except Exception as e:
        logger.error(f"Delivery % check error for {stock_symbol}: {e}")
        return "UNAVAILABLE", "Delivery % check error"


def check_pcr(stock_symbol: str) -> tuple[str, str]:
    """
    Check 18 — Put-Call Ratio (PCR) Reversal Trap.
    PCR < 0.6 = extreme fear = contrarian BUY signal.
    PCR > 1.4 = extreme greed = contrarian SELL signal.
    """
    try:
        nse_symbol = stock_symbol.replace(".NS", "")
        is_fno     = nse_symbol in FNO_STOCKS
        source     = nse_symbol if is_fno else "NIFTY"

        closed_msg = _market_closed_message(stock_symbol)
        if closed_msg:
            return "UNAVAILABLE", closed_msg

        if is_fno:
            oc_data = fetch_option_chain(nse_symbol)
            if not oc_data:
                oc_data = fetch_nifty_option_chain()
                source = "NIFTY"
        else:
            oc_data = fetch_nifty_option_chain()  # Use Nifty PCR for non-F&O

        if not oc_data:
            return "UNAVAILABLE", "Option chain data unavailable for PCR"

        pcr = calculate_pcr(oc_data)
        current_price = get_current_price(stock_symbol)
        context = get_option_chain_context(oc_data, current_price)
        expiry_suffix = _format_expiry_suffix(context)
        atm_pcr = float(context.get("atm_pcr", 1.0) or 1.0)
        total_oi = float(context.get("total_call_oi", 0) or 0) + float(context.get("total_put_oi", 0) or 0)

        if total_oi <= 0:
            return "UNAVAILABLE", f"Nearest-expiry option chain too thin for PCR{expiry_suffix}"

        if pcr < 0.60 and atm_pcr < 0.85:
            return "CONTRARIAN_BUY", (
                f"PCR {pcr:.2f} ({source}{expiry_suffix}) with ATM PCR {atm_pcr:.2f} — crowded calls, setup is washed out enough for a contrarian buy"
            )
        elif pcr < 0.75 and atm_pcr < 0.95:
            return "INFO", f"PCR {pcr:.2f} ({source}{expiry_suffix}) — mild fear, but not a clean capitulation signal"
        elif pcr > 1.60 and atm_pcr > 1.15:
            return "CONTRARIAN_SELL", (
                f"PCR {pcr:.2f} ({source}{expiry_suffix}) with ATM PCR {atm_pcr:.2f} — puts are overcrowded, setup is stretched enough for a contrarian sell"
            )
        elif pcr > 1.30 and atm_pcr > 1.05:
            return "INFO", f"PCR {pcr:.2f} ({source}{expiry_suffix}) — elevated put positioning, but not an extreme reversal by itself"
        elif 0.85 <= pcr <= 1.20:
            return "NEUTRAL", f"PCR {pcr:.2f} ({source}{expiry_suffix}) — balanced sentiment, no extreme"
        elif pcr < 0.85:
            return "INFO", f"PCR {pcr:.2f} ({source}{expiry_suffix}) — mild fear, not an extreme reversal signal"
        else:
            return "INFO", f"PCR {pcr:.2f} ({source}{expiry_suffix}) — mild optimism, not enough for a contrarian call"
    except Exception as e:
        logger.error(f"PCR check error for {stock_symbol}: {e}")
        return "UNAVAILABLE", "PCR check error"


def check_promoter_confidence_drift(stock_symbol: str) -> tuple[str, str]:
    """
    Check 19 — Promoter Confidence Drift using quarterly holding trend.
    """
    try:
        screener = get_screener_snapshot(stock_symbol)
        if not screener.get("source_ok"):
            return "UNAVAILABLE", "Promoter shareholding trend unavailable"

        shareholding = screener.get("shareholding", {})
        promoter_latest = float(shareholding.get("promoter_latest", 0) or 0)
        promoter_prev = float(shareholding.get("promoter_prev", 0) or 0)
        promoter_change = promoter_latest - promoter_prev

        roe = float((screener.get("ratios") or {}).get("roe", 0) or 0)
        fii_latest = float(shareholding.get("fii_latest", 0) or 0)
        fii_prev = float(shareholding.get("fii_prev", 0) or 0)
        fii_change = fii_latest - fii_prev

        if promoter_latest == 0 and promoter_prev == 0:
            return "UNAVAILABLE", "Promoter holding trend unavailable"

        if promoter_change >= 0.1 and roe >= 15:
            return "STRONG_CONFIDENCE", (
                f"Promoter holding improved from {promoter_prev:.2f}% to {promoter_latest:.2f}% with ROE {roe:.1f}% — confidence improving"
            )
        elif promoter_change >= 0 and roe >= 12 and fii_change >= 0:
            return "POSITIVE", (
                f"Promoter holding stable at {promoter_latest:.2f}% and ROE {roe:.1f}% — ownership quality intact"
            )
        elif promoter_change <= -0.5 and roe < 12:
            return "RED_FLAG", (
                f"Promoter holding dropped from {promoter_prev:.2f}% to {promoter_latest:.2f}% and ROE is only {roe:.1f}% — confidence drift is negative"
            )
        elif promoter_change < 0:
            return "CAUTION", (
                f"Promoter holding slipped from {promoter_prev:.2f}% to {promoter_latest:.2f}% — watch ownership drift"
            )
        else:
            return "INFO", (
                f"Promoter holding steady near {promoter_latest:.2f}% — no strong ownership drift signal"
            )
    except Exception as e:
        logger.error(f"Promoter confidence drift check error for {stock_symbol}: {e}")
        return "UNAVAILABLE", "Promoter confidence drift unavailable"


def check_fii_futures(fii_data: Optional[dict] = None) -> tuple[str, str]:
    """
    Check 20 — FII Index Futures Net Position.
    FII net long = market going UP in 2-5 days.
    """
    try:
        status = get_market_status_hint("NATIONALUM")
        if status.get("is_closed"):
            return "UNAVAILABLE", "NSE market appears closed today — fresh FII futures positioning is unavailable"

        if fii_data is None:
            fii_data = fetch_fii_dii_data()

        if not fii_data.get("source_ok", True):
            return "UNAVAILABLE", "FII futures source unavailable from NSE"

        net_pos = float(fii_data.get("fii_futures_net", 0) or 0)
        buy_amt = float(fii_data.get("fii_futures_buy", 0) or 0)
        sell_amt = float(fii_data.get("fii_futures_sell", 0) or 0)
        gross = buy_amt + sell_amt
        conviction = abs(net_pos) / gross if gross > 0 else 0.0

        if net_pos > 3000 and conviction >= 0.08:
            return "STRONGLY_LONG", (
                f"FII index futures net long ₹{net_pos:.0f}Cr on ₹{gross:.0f}Cr gross flow — meaningful bullish market bias"
            )
        elif net_pos > 1000 and conviction >= 0.04:
            return "SLIGHTLY_LONG", (
                f"FII futures modestly long ₹{net_pos:.0f}Cr on ₹{gross:.0f}Cr gross flow — mild bullish market bias"
            )
        elif net_pos > 0:
            return "INFO", f"FII futures marginally long ₹{net_pos:.0f}Cr — weak market-level signal"
        elif net_pos < -3000 and conviction >= 0.08:
            return "STRONGLY_SHORT", (
                f"FII index futures net short ₹{abs(net_pos):.0f}Cr on ₹{gross:.0f}Cr gross flow — meaningful bearish market bias"
            )
        elif net_pos < -1000 and conviction >= 0.04:
            return "SLIGHTLY_SHORT", (
                f"FII futures modestly short ₹{abs(net_pos):.0f}Cr on ₹{gross:.0f}Cr gross flow — mild bearish market bias"
            )
        else:
            return "INFO", f"FII futures near-flat ₹{net_pos:.0f}Cr on ₹{gross:.0f}Cr gross flow — no strong directional bet"
    except Exception as e:
        logger.error(f"FII futures check error: {e}")
        return "UNAVAILABLE", "FII futures data unavailable"


def check_52w_reversal_formula(ticker_info: dict) -> tuple[str, str]:
    """
    Check 21 — 52-Week Low Reversal Formula.
    Contrarian value: Near 52W low + Good fundamentals + Low PE = BUY.
    """
    try:
        current  = float(ticker_info.get("currentPrice") or ticker_info.get("regularMarketPrice") or 0)
        low_52w  = float(ticker_info.get("fiftyTwoWeekLow")  or 0)
        high_52w = float(ticker_info.get("fiftyTwoWeekHigh") or 0)
        pe       = float(ticker_info.get("trailingPE") or 999)
        de       = float(ticker_info.get("debtToEquity") or 999)

        if current == 0 or low_52w == 0 or high_52w == 0:
            return "NEUTRAL", "52W data unavailable for reversal formula"

        pct_from_high = ((high_52w - current) / high_52w) * 100
        pct_from_low  = ((current - low_52w)  / low_52w)  * 100

        # Scoring criteria
        score = 0
        reasons = []

        if pct_from_high > 25:
            score += 1
            reasons.append(f"{pct_from_high:.1f}% below 52W high")
        if pe < 25:
            score += 1
            reasons.append(f"PE {pe:.1f} reasonable")
        if de < 50:
            score += 1
            reasons.append(f"D/E {de:.1f}% low debt")
        if pct_from_low > 5:
            score += 1
            reasons.append(f"Bounced {pct_from_low:.1f}% from 52W low")

        summary = ", ".join(reasons) if reasons else "No criteria met"

        if score >= 4:
            return "STRONG_OPPORTUNITY", (
                f"52W Reversal Score {score}/4 — {summary}. HIGH CONVICTION VALUE! 💎"
            )
        elif score >= 3:
            return "BULLISH", (
                f"52W Reversal Score {score}/4 — {summary}. Good value setup"
            )
        elif score == 2:
            return "MODERATE", f"52W Reversal Score {score}/4 — {summary}. Partial value"
        else:
            return "NEUTRAL", f"52W Reversal Score {score}/4 — {summary}. Not a clear value opportunity"
    except Exception as e:
        logger.error(f"52W reversal formula error: {e}")
        return "NEUTRAL", "52W reversal formula error"


def run_all_secret_checks(
    stock_symbol: str,
    ticker_info: dict,
    fii_data: Optional[dict] = None
) -> list[dict]:
    """
    Run all 6 secret strategy checks and return structured results list.
    """
    if fii_data is None:
        fii_data = fetch_fii_dii_data()

    checks = [
        (16, "Max Pain Theory",         check_max_pain(stock_symbol, ticker_info)),
        (17, "Delivery % (Smart Money)", check_delivery_percentage(stock_symbol)),
        (18, "PCR Reversal Trap",        check_pcr(stock_symbol)),
        (19, "Promoter Confidence Drift", check_promoter_confidence_drift(stock_symbol)),
        (20, "FII Futures Position",     check_fii_futures(fii_data)),
        (21, "52W Reversal Formula",     check_52w_reversal_formula(ticker_info)),
    ]

    return [
        {
            "check_number": num,
            "category":     "Secret Strategy",
            "name":         name,
            "signal":       result[0],
            "detail":       result[1],
        }
        for num, name, result in checks
    ]
