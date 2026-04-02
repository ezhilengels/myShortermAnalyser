"""
macro.py — Macro & Global Market Checks 11 through 15.

Check 11: FII Exit Pressure Strategy
Check 12: Sector Tailwind Alignment
Check 13: Global Sentiment (India VIX + US VIX)
Check 14: Commodity Price Tailwind/Headwind
Check 15: Geopolitical / News Trigger (via Groq AI context)
"""

import logging
from typing import Optional

from data.fetchers.fii_fetcher     import fetch_fii_dii_data
from data.fetchers.commodity_fetcher import get_commodity_price, get_india_vix, get_us_vix
from data.fetchers.news_fetcher    import fetch_geopolitical_news_summary, fetch_stock_news
from data.fetchers.nse_fetcher     import fetch_bulk_deals, fetch_block_deals, fetch_delivery_data
from data.fetchers.global_macro_fetcher import get_china_manufacturing_pmi, get_latest_fpi_sector_flow
from data.fetchers.trends_fetcher import get_google_trends_snapshot
from data.fetchers.yfinance_fetcher import get_market_history
from data.fetchers.screener_fetcher import get_screener_snapshot
from config import STOCK_COMMODITY_MAP, STOCK_SECTOR_BENCHMARKS, STOCK_NAMES, FNO_STOCKS, SECTOR_FLOW_LABELS

logger = logging.getLogger(__name__)


def _percent_return(hist) -> float:
    if hist is None or hist.empty or len(hist) < 5:
        return 0.0
    start = float(hist["Close"].iloc[0])
    end = float(hist["Close"].iloc[-1])
    if start == 0:
        return 0.0
    return ((end - start) / start) * 100


def check_fii_exit_pressure(stock_symbol: str) -> tuple[str, str]:
    """
    Check 11 — FII Exit Pressure Strategy.
    Returns (signal, detail_message)
    """
    try:
        screener = get_screener_snapshot(stock_symbol)
        if not screener.get("source_ok"):
            return "UNAVAILABLE", "FII shareholding trend unavailable"

        shareholding = screener.get("shareholding", {})
        fii_latest = float(shareholding.get("fii_latest", 0) or 0)
        fii_prev = float(shareholding.get("fii_prev", 0) or 0)
        fii_change = fii_latest - fii_prev

        stock_hist = get_market_history(stock_symbol, period="3mo", interval="1d")
        benchmark_symbol = STOCK_SECTOR_BENCHMARKS.get(stock_symbol)
        sector_hist = get_market_history(benchmark_symbol, period="3mo", interval="1d") if benchmark_symbol else None

        if stock_hist.empty:
            return "UNAVAILABLE", "Stock trend unavailable for FII exit-pressure check"

        stock_return = _percent_return(stock_hist)
        if benchmark_symbol and (sector_hist is None or sector_hist.empty):
            return "UNAVAILABLE", "Sector benchmark unavailable for FII exit-pressure check"

        sector_return = _percent_return(sector_hist) if sector_hist is not None and not sector_hist.empty else 0.0
        relative = stock_return - sector_return if benchmark_symbol else stock_return
        current = float(stock_hist["Close"].iloc[-1])
        sma50 = float(stock_hist["Close"].rolling(50).mean().iloc[-1]) if len(stock_hist) >= 50 else current
        below_sma50 = current < sma50

        if fii_change <= -1.0 and relative <= -5 and below_sma50:
            return "BEARISH", (
                f"FII holding fell from {fii_prev:.2f}% to {fii_latest:.2f}%, stock underperformed sector by {abs(relative):.1f}% "
                "and trades below 50DMA — institutional exit pressure"
            )
        elif fii_change <= -0.4 and relative < -2:
            return "CAUTION", (
                f"FII holding slipped from {fii_prev:.2f}% to {fii_latest:.2f}% and stock is lagging its sector"
            )
        elif fii_change >= 0.5 and benchmark_symbol and sector_return > -2 and relative > 3 and current >= sma50:
            return "BULLISH", (
                f"FII holding improved from {fii_prev:.2f}% to {fii_latest:.2f}% with stock outperforming sector by {relative:.1f}%"
            )
        else:
            return "INFO", (
                f"FII holding {fii_prev:.2f}% -> {fii_latest:.2f}% — no decisive institutional exit pattern"
            )
    except Exception as e:
        logger.error(f"FII exit-pressure check error: {e}")
        return "UNAVAILABLE", "FII exit-pressure data unavailable"


def check_sector_tailwind_alignment(stock_symbol: str) -> tuple[str, str]:
    """
    Check 12 — Sector Tailwind Alignment.
    Returns (signal, detail_message)
    """
    try:
        hist = get_market_history("^NSEI", period="1mo", interval="1d")

        if hist.empty or len(hist) < 5:
            return "UNAVAILABLE", "Nifty market-trend data unavailable"

        monthly_return = _percent_return(hist)
        current = hist["Close"].iloc[-1]
        stock_hist = get_market_history(stock_symbol, period="1mo", interval="1d")
        if stock_hist.empty or len(stock_hist) < 5:
            return "UNAVAILABLE", "Stock trend unavailable for sector-alignment check"
        stock_return = _percent_return(stock_hist)

        benchmark_symbol = STOCK_SECTOR_BENCHMARKS.get(stock_symbol)
        sector_return = None
        if benchmark_symbol:
            sector_hist = get_market_history(benchmark_symbol, period="1mo", interval="1d")
            if not sector_hist.empty and len(sector_hist) >= 5:
                sector_return = _percent_return(sector_hist)

        if sector_return is None:
            return "UNAVAILABLE", "Sector benchmark unavailable for alignment check"

        relative_vs_nifty = stock_return - monthly_return
        relative_vs_sector = stock_return - sector_return
        sma50 = float(stock_hist["Close"].rolling(50).mean().iloc[-1]) if len(stock_hist) >= 50 else float(stock_hist["Close"].mean())
        above_sma50 = float(stock_hist["Close"].iloc[-1]) >= sma50

        if sector_return > monthly_return + 2 and relative_vs_sector > 2 and above_sma50:
            return "BULLISH", (
                f"Sector {benchmark_symbol} {sector_return:+.1f}% is leading Nifty {monthly_return:+.1f}% and "
                f"stock outperformed sector by {relative_vs_sector:+.1f}% above 50DMA"
            )
        elif sector_return < monthly_return - 2 and relative_vs_sector < -2 and not above_sma50:
            return "BEARISH", (
                f"Sector {benchmark_symbol} {sector_return:+.1f}% is lagging Nifty {monthly_return:+.1f}% and "
                f"stock underperformed sector by {abs(relative_vs_sector):.1f}% below 50DMA"
            )
        elif sector_return >= monthly_return and relative_vs_nifty > 4 and above_sma50:
            return "BULLISH", (
                f"Stock +{stock_return:.1f}% vs Nifty {monthly_return:+.1f}% — strong standalone leadership"
            )
        else:
            return "NEUTRAL", (
                f"Sector {benchmark_symbol} {sector_return:+.1f}%, stock {stock_return:+.1f}%, "
                f"Nifty {monthly_return:+.1f} — alignment is mixed"
            )
    except Exception as e:
        logger.error(f"Sector alignment check error: {e}")
        return "UNAVAILABLE", "Sector alignment data unavailable"


def check_global_sentiment() -> tuple[str, str]:
    """
    Check 13 — Global Sentiment (India VIX + US VIX).
    Returns (signal, detail_message)
    """
    try:
        india_vix = get_india_vix()
        us_vix    = get_us_vix()

        if india_vix == 0 and us_vix == 0:
            return "UNAVAILABLE", "VIX data unavailable"

        if india_vix > 25 or us_vix > 30:
            return "FEAR", (
                f"India VIX {india_vix:.1f}, US VIX {us_vix:.1f} — HIGH FEAR. "
                "Markets volatile, reduce position size!"
            )
        elif india_vix > 20 or us_vix > 22:
            return "CAUTION", (
                f"India VIX {india_vix:.1f}, US VIX {us_vix:.1f} — elevated fear, be cautious"
            )
        elif india_vix < 12 and us_vix < 15:
            return "GREED", (
                f"India VIX {india_vix:.1f} — very low fear (complacency). "
                "Contrarian caution: market may correct"
            )
        else:
            return "NEUTRAL", (
                f"India VIX {india_vix:.1f}, US VIX {us_vix:.1f} — normal sentiment"
            )
    except Exception as e:
        logger.error(f"Global sentiment check error: {e}")
        return "UNAVAILABLE", "VIX data unavailable"


def check_commodity(stock_symbol: str) -> tuple[str, str]:
    """
    Check 14 — Commodity Tailwind/Headwind specific to the stock.
    Returns (signal, detail_message)
    """
    try:
        commodities = STOCK_COMMODITY_MAP.get(stock_symbol, [])
        if not commodities:
            return "NEUTRAL", "No direct commodity link for this stock"

        changes = []
        descriptions = []
        commodity_data = []
        for comm_ticker in commodities:
            data = get_commodity_price(comm_ticker)
            commodity_data.append(data)
            change = data.get("change_pct", 0)
            name   = data.get("name", comm_ticker)
            price  = data.get("price", 0)
            changes.append(change)
            descriptions.append(f"{name} {change:+.1f}% (${price})")

        if all(data.get("price", 0) == 0 for data in commodity_data):
            return "UNAVAILABLE", "Commodity data unavailable for this stock"

        avg_change = sum(changes) / len(changes)
        desc_str   = ", ".join(descriptions)

        if avg_change > 2.5:
            return "BULLISH", f"Commodity TAILWIND: {desc_str} — strong boost to stock!"
        elif avg_change > 1.0:
            return "BULLISH", f"Commodity positive: {desc_str}"
        elif avg_change < -2.5:
            return "BEARISH", f"Commodity HEADWIND: {desc_str} — margin pressure!"
        elif avg_change < -1.0:
            return "BEARISH", f"Commodity soft: {desc_str}"
        else:
            return "NEUTRAL", f"Commodity flat: {desc_str}"
    except Exception as e:
        logger.error(f"Commodity check error for {stock_symbol}: {e}")
        return "UNAVAILABLE", "Commodity data unavailable"


def check_geopolitical() -> tuple[str, str]:
    """
    Check 15 — Geopolitical / News Trigger.
    Returns news summary string that feeds into the Groq AI prompt.
    Signal is always NEUTRAL here — Groq interprets the news.
    """
    try:
        summary = fetch_geopolitical_news_summary()
        if summary == "No recent geopolitical news available.":
            return "UNAVAILABLE", summary
        return "INFO", summary
    except Exception as e:
        logger.error(f"Geopolitical check error: {e}")
        return "UNAVAILABLE", "No geopolitical data available"


# ─────────────────────────────────────────────
# V2 GROUP 1 MACRO CHECKS (27–28)
# ─────────────────────────────────────────────

# Sectors where DXY / US yield impact is most direct (FII-sensitive, dollar-linked)
_DXY_SENSITIVE_SECTORS = {"^CNXMETAL", "^NSEBANK", "^CNXENERGY"}


def check_dxy_impact(stock_symbol: str) -> tuple[str, str]:
    """
    Check 27 — Dollar Index (DXY) Impact.
    Rising DXY → FII outflows from India → headwind for equities.
    Particularly relevant for FII-heavy, dollar-linked sectors.
    Returns (signal, detail_message)
    """
    try:
        dxy_hist = get_market_history("DX-Y.NYB", period="1mo", interval="1d")
        if dxy_hist.empty or len(dxy_hist) < 10:
            return "UNAVAILABLE", "DXY data unavailable"

        cur_dxy  = float(dxy_hist["Close"].iloc[-1])
        prev_dxy = float(dxy_hist["Close"].iloc[-10])  # ~2-week compare
        dxy_ret  = (cur_dxy - prev_dxy) / prev_dxy * 100 if prev_dxy != 0 else 0.0

        benchmark = STOCK_SECTOR_BENCHMARKS.get(stock_symbol, "")
        is_sensitive = benchmark in _DXY_SENSITIVE_SECTORS
        sensitivity_note = " (sector highly FII-sensitive)" if is_sensitive else ""

        if dxy_ret >= 2.0:
            # Rising dollar — FII outflow pressure
            return "BEARISH", (
                f"DXY rose {dxy_ret:+.1f}% over 2 weeks to {cur_dxy:.2f} — "
                f"rising dollar increases FII exit risk{sensitivity_note}"
            )
        elif dxy_ret >= 1.0:
            return "CAUTION", (
                f"DXY up {dxy_ret:+.1f}% to {cur_dxy:.2f} — mild dollar strength, "
                f"watch FII flows{sensitivity_note}"
            )
        elif dxy_ret <= -2.0:
            # Falling dollar — typically supports EM inflows
            return "BULLISH", (
                f"DXY fell {dxy_ret:+.1f}% over 2 weeks to {cur_dxy:.2f} — "
                f"weaker dollar supports FII inflows to India{sensitivity_note}"
            )
        elif dxy_ret <= -1.0:
            return "BULLISH", (
                f"DXY down {dxy_ret:+.1f}% to {cur_dxy:.2f} — modest dollar softness, "
                f"mild tailwind for FII flows{sensitivity_note}"
            )
        else:
            return "NEUTRAL", (
                f"DXY stable at {cur_dxy:.2f} ({dxy_ret:+.1f}% over 2 weeks) — "
                "no significant dollar pressure on FII flows"
            )

    except Exception as e:
        logger.error(f"DXY impact check error: {e}")
        return "UNAVAILABLE", "DXY data unavailable"


def check_us10y_yield() -> tuple[str, str]:
    """
    Check 28 — US 10-Year Bond Yield.
    Rising US yields pull capital away from EM risk assets including India.
    Returns (signal, detail_message)
    """
    try:
        tnx_hist = get_market_history("^TNX", period="1mo", interval="1d")
        if tnx_hist.empty or len(tnx_hist) < 10:
            return "UNAVAILABLE", "US 10Y yield data unavailable"

        cur_yield  = float(tnx_hist["Close"].iloc[-1])
        prev_yield = float(tnx_hist["Close"].iloc[-10])  # ~2-week compare
        chg_bps    = (cur_yield - prev_yield) * 10  # Convert to basis points (^TNX in % units)

        # US 10Y levels and direction thresholds
        if cur_yield >= 5.0 and chg_bps > 0:
            return "BEARISH", (
                f"US 10Y yield at {cur_yield:.2f}% (+{chg_bps:.0f}bps in 2 weeks) — "
                "elevated and rising: strong EM risk-off signal, FII outflow risk"
            )
        elif cur_yield >= 4.5 and chg_bps >= 15:
            return "BEARISH", (
                f"US 10Y yield {cur_yield:.2f}% (+{chg_bps:.0f}bps) — "
                "rising yields pulling capital from EM equities"
            )
        elif chg_bps >= 20:
            return "CAUTION", (
                f"US 10Y yield jumped +{chg_bps:.0f}bps to {cur_yield:.2f}% in 2 weeks — "
                "sharp move, watch for FII risk-off"
            )
        elif chg_bps <= -15:
            return "BULLISH", (
                f"US 10Y yield fell {chg_bps:.0f}bps to {cur_yield:.2f}% in 2 weeks — "
                "falling yields reduce EM risk-off pressure, supportive for FII flows"
            )
        elif cur_yield < 4.0 and chg_bps < 0:
            return "BULLISH", (
                f"US 10Y yield low at {cur_yield:.2f}% and declining — "
                "benign rate environment supports EM risk appetite"
            )
        else:
            return "NEUTRAL", (
                f"US 10Y yield at {cur_yield:.2f}% ({chg_bps:+.0f}bps over 2 weeks) — "
                "no significant EM risk signal"
            )

    except Exception as e:
        logger.error(f"US 10Y yield check error: {e}")
        return "UNAVAILABLE", "US 10-Year yield data unavailable"


def check_mutual_fund_holding_change(stock_symbol: str) -> tuple[str, str]:
    """
    Additional Signal — Mutual Fund Holding Change.
    Uses Screener shareholding rows when mutual fund ownership is exposed separately.
    """
    try:
        screener = get_screener_snapshot(stock_symbol)
        if not screener.get("source_ok"):
            return "UNAVAILABLE", "Mutual fund holding trend unavailable"

        shareholding = screener.get("shareholding", {})
        mf_latest = float(shareholding.get("mf_latest", 0) or 0)
        mf_prev = float(shareholding.get("mf_prev", 0) or 0)
        mf_yoy = float(shareholding.get("mf_yoy", 0) or 0)
        change = mf_latest - mf_prev
        dii_latest = float(shareholding.get("dii_latest", 0) or 0)
        dii_prev = float(shareholding.get("dii_prev", 0) or 0)
        dii_change = dii_latest - dii_prev

        if mf_latest == 0 and mf_prev == 0:
            if dii_latest == 0 and dii_prev == 0:
                return "UNAVAILABLE", "Mutual fund ownership not exposed separately in source data"
            if dii_change >= 0.4:
                return "POSITIVE", (
                    f"Mutual fund row unavailable; DII holding proxy rose from {dii_prev:.2f}% to {dii_latest:.2f}% "
                    f"({dii_change:+.2f} pts)"
                )
            if dii_change <= -0.4:
                return "CAUTION", (
                    f"Mutual fund row unavailable; DII holding proxy fell from {dii_prev:.2f}% to {dii_latest:.2f}% "
                    f"({dii_change:+.2f} pts)"
                )
            return "INFO", (
                f"Mutual fund row unavailable; DII holding proxy is stable near {dii_latest:.2f}%"
            )

        if change >= 0.35:
            return "BULLISH", (
                f"Mutual fund holding rose from {mf_prev:.2f}% to {mf_latest:.2f}% "
                f"({change:+.2f} pts) — smart-money accumulation signal"
            )
        if change >= 0.10:
            return "POSITIVE", (
                f"Mutual fund holding improved from {mf_prev:.2f}% to {mf_latest:.2f}% "
                f"({change:+.2f} pts)"
            )
        if change <= -0.35:
            return "BEARISH", (
                f"Mutual fund holding dropped from {mf_prev:.2f}% to {mf_latest:.2f}% "
                f"({change:+.2f} pts) — institutional trimming"
            )
        if change < 0:
            return "CAUTION", (
                f"Mutual fund holding slipped from {mf_prev:.2f}% to {mf_latest:.2f}% "
                f"({change:+.2f} pts)"
            )
        return "INFO", (
            f"Mutual fund holding stable near {mf_latest:.2f}% (quarterly drift {mf_yoy:+.2f}%)"
        )
    except Exception as e:
        logger.error(f"Mutual fund holding check error: {e}")
        return "UNAVAILABLE", "Mutual fund holding data unavailable"


def check_block_bulk_deals(stock_symbol: str) -> tuple[str, str]:
    """
    Additional Signal — NSE block / bulk deal scanner.
    Uses same-day NSE deal feeds; returns INFO unless a meaningful stock-specific deal appears.
    """
    try:
        nse_symbol = (stock_symbol or "").replace(".NS", "").replace(".BO", "").upper()
        screener = get_screener_snapshot(stock_symbol)
        market_cap_cr = float(((screener.get("ratios") or {}).get("market_cap_cr")) or 0)
        block_deals = fetch_block_deals()
        bulk_deals = fetch_bulk_deals()

        if block_deals is None and bulk_deals is None:
            return "UNAVAILABLE", "NSE block/bulk deal source unavailable"

        matches = []
        for deal_type, deals in (("block", block_deals or []), ("bulk", bulk_deals or [])):
            for deal in deals or []:
                symbol = str(deal.get("symbol") or deal.get("symbolName") or "").upper()
                if symbol != nse_symbol:
                    continue
                qty = float(deal.get("quantityTraded") or deal.get("quantity") or 0)
                price = float(deal.get("tradePrice") or deal.get("price") or 0)
                side = str(deal.get("buySell") or deal.get("buyOrSell") or "").upper()
                client = str(deal.get("clientName") or deal.get("client") or "Institution").strip()
                value_cr = (qty * price) / 1e7 if qty > 0 and price > 0 else 0.0
                matches.append({
                    "type": deal_type,
                    "side": side,
                    "client": client,
                    "value_cr": value_cr,
                })

        if not matches:
            if block_deals is None or bulk_deals is None:
                return "UNAVAILABLE", "NSE block/bulk deal feed partially unavailable"
            return "INFO", "No NSE block/bulk deals detected for this stock today"

        buy_value = sum(item["value_cr"] for item in matches if item["side"] == "BUY")
        sell_value = sum(item["value_cr"] for item in matches if item["side"] == "SELL")
        largest = max(matches, key=lambda item: item["value_cr"])
        pct_mcap = (largest["value_cr"] / market_cap_cr * 100) if market_cap_cr > 0 else 0.0

        if largest["side"] == "BUY" and pct_mcap >= 1.0:
            return "BULLISH", (
                f"Largest {largest['type']} deal is a BUY worth ~₹{largest['value_cr']:.1f}Cr "
                f"({pct_mcap:.2f}% of market cap) by {largest['client']}"
            )
        if largest["side"] == "SELL" and pct_mcap >= 1.0:
            return "BEARISH", (
                f"Largest {largest['type']} deal is a SELL worth ~₹{largest['value_cr']:.1f}Cr "
                f"({pct_mcap:.2f}% of market cap) by {largest['client']}"
            )
        net = buy_value - sell_value
        direction = "buy-side" if net > 0 else "sell-side" if net < 0 else "balanced"
        return "INFO", (
            f"NSE deals seen today: {len(matches)} entries, {direction} flow "
            f"(buy ₹{buy_value:.1f}Cr vs sell ₹{sell_value:.1f}Cr)"
        )
    except Exception as e:
        logger.error(f"Block/bulk deal check error: {e}")
        return "UNAVAILABLE", "Block/bulk deal data unavailable"


def check_fii_sector_rotation(stock_symbol: str, fii_data: Optional[dict] = None) -> tuple[str, str]:
    """
    Additional Signal — FII Sector Rotation.
    Uses official NSDL fortnightly sector-wise FPI flow when available,
    then blends it with sector relative performance for stock-level context.
    """
    try:
        benchmark_symbol = STOCK_SECTOR_BENCHMARKS.get(stock_symbol)
        if not benchmark_symbol:
            return "UNAVAILABLE", "Sector benchmark unavailable for sector rotation"

        nifty_hist = get_market_history("^NSEI", period="1mo", interval="1d")
        sector_hist = get_market_history(benchmark_symbol, period="1mo", interval="1d")
        stock_hist = get_market_history(stock_symbol, period="1mo", interval="1d")
        if nifty_hist.empty or sector_hist.empty or stock_hist.empty:
            return "UNAVAILABLE", "Market/sector trend unavailable for sector rotation"

        nifty_ret = _percent_return(nifty_hist.tail(15))
        sector_ret = _percent_return(sector_hist.tail(15))
        stock_ret = _percent_return(stock_hist.tail(15))
        sector_vs_nifty = sector_ret - nifty_ret
        stock_vs_sector = stock_ret - sector_ret

        if fii_data is None:
            fii_data = fetch_fii_dii_data()
        fii_cash = float((fii_data or {}).get("fii_cash_net", 0) or 0)
        sector_label = SECTOR_FLOW_LABELS.get(benchmark_symbol)
        flow_data = get_latest_fpi_sector_flow()

        if sector_label and flow_data.get("source_ok"):
            row = (flow_data.get("rows") or {}).get(sector_label)
            if row:
                current_flow = float(row.get("current_equity_inr_cr", 0) or 0)
                previous_flow = float(row.get("previous_equity_inr_cr", 0) or 0)
                current_period = flow_data.get("current_period", "latest fortnight")
                previous_period = flow_data.get("previous_period", "previous fortnight")

                if current_flow > 0 and previous_flow > 0 and sector_vs_nifty >= 0:
                    signal = "BULLISH" if stock_vs_sector >= -1 else "POSITIVE"
                    return signal, (
                        f"Official sector flow: {sector_label} FPI equity flow stayed positive "
                        f"(₹{previous_flow:.0f}Cr in {previous_period}; ₹{current_flow:.0f}Cr in {current_period}) "
                        f"and sector beat Nifty by {sector_vs_nifty:+.1f}%"
                    )
                if current_flow < 0 and previous_flow < 0 and sector_vs_nifty <= 0:
                    signal = "BEARISH" if stock_vs_sector <= 1 else "CAUTION"
                    return signal, (
                        f"Official sector flow: {sector_label} FPI equity flow stayed negative "
                        f"(₹{previous_flow:.0f}Cr in {previous_period}; ₹{current_flow:.0f}Cr in {current_period}) "
                        f"and sector lagged Nifty by {abs(sector_vs_nifty):.1f}%"
                    )
                return "INFO", (
                    f"Official sector flow mixed for {sector_label}: ₹{previous_flow:.0f}Cr then ₹{current_flow:.0f}Cr; "
                    f"sector vs Nifty {sector_vs_nifty:+.1f}%"
                )

        if sector_vs_nifty >= 3 and fii_cash > 0:
            signal = "BULLISH" if stock_vs_sector >= -1 else "POSITIVE"
            return signal, (
                f"Rotation proxy: sector {benchmark_symbol} outperformed Nifty by {sector_vs_nifty:+.1f}% "
                f"over ~3 weeks with FII cash flow positive at ₹{fii_cash:.0f}Cr"
            )
        if sector_vs_nifty <= -3 and fii_cash < 0:
            signal = "BEARISH" if stock_vs_sector <= 1 else "CAUTION"
            return signal, (
                f"Rotation proxy: sector {benchmark_symbol} lagged Nifty by {abs(sector_vs_nifty):.1f}% "
                f"with FII cash flow negative at ₹{abs(fii_cash):.0f}Cr"
            )
        return "INFO", (
            f"Sector rotation mixed: sector {benchmark_symbol} {sector_vs_nifty:+.1f}% vs Nifty, "
            f"FII cash ₹{fii_cash:.0f}Cr"
        )
    except Exception as e:
        logger.error(f"FII sector rotation check error: {e}")
        return "UNAVAILABLE", "FII sector rotation unavailable"


def check_china_pmi_signal(stock_symbol: str) -> tuple[str, str]:
    """
    Additional Signal — China PMI.
    """
    benchmark_symbol = STOCK_SECTOR_BENCHMARKS.get(stock_symbol, "")
    if benchmark_symbol != "^CNXMETAL":
        return "INFO", "China PMI is mainly relevant for metal-linked stocks"
    try:
        pmi = get_china_manufacturing_pmi()
        if not pmi.get("source_ok"):
            return "UNAVAILABLE", pmi.get("detail", "China PMI source unavailable")

        value = float(pmi.get("value", 0) or 0)
        previous = float(pmi.get("previous", 0) or 0)
        delta = value - previous
        detail = pmi.get("detail", f"China manufacturing PMI {value:.1f}")

        if value >= 52:
            return "BULLISH", f"{detail} — strong expansion, supportive for industrial metal demand"
        if value >= 50:
            return "POSITIVE", f"{detail} — expansionary reading, mild tailwind for metals"
        if value >= 48:
            return "CAUTION", f"{detail} — still below 50, demand backdrop remains soft for metals"
        if value > 0:
            return "BEARISH", f"{detail} — contractionary PMI, headwind for metal-demand expectations"
        return "UNAVAILABLE", "China PMI value unavailable"
    except Exception as e:
        logger.error(f"China PMI signal error: {e}")
        return "UNAVAILABLE", "China PMI signal unavailable"


def check_news_sentiment_score(stock_symbol: str) -> tuple[str, str]:
    """
    Additional Signal — stock-news sentiment from recent headlines.
    Uses a simple rule-based title score so it stays independent of Groq limits.
    """
    try:
        articles = fetch_stock_news(stock_symbol, max_articles=8)
        if not articles:
            return "UNAVAILABLE", "No recent stock-specific headlines available"

        positive_words = {
            "surge", "gain", "rally", "beats", "upgrade", "buy", "strong", "record",
            "growth", "expands", "wins", "approval", "outperform", "bullish",
            "jumps", "orders", "contract", "profit rises", "margin expands", "acquires",
        }
        negative_words = {
            "fall", "drops", "slump", "miss", "downgrade", "sell", "weak", "probe",
            "penalty", "loss", "decline", "cuts", "bearish", "lawsuit",
            "raid", "default", "fraud", "margin pressure", "stake sale", "demand weakens",
        }

        score = 0.0
        counted = 0
        for article in articles:
            title = str(article.get("title") or "").lower()
            description = str(article.get("description") or "").lower()
            text = f"{title} {description}".strip()
            if not text:
                continue
            counted += 1
            title_hits = sum(1 for word in positive_words if word in title) - sum(1 for word in negative_words if word in title)
            desc_hits = sum(1 for word in positive_words if word in description) - sum(1 for word in negative_words if word in description)
            score += title_hits + (0.5 * desc_hits)

        if counted == 0:
            return "UNAVAILABLE", "Headline sentiment unavailable"

        avg_score = score / counted
        if avg_score >= 0.75:
            return "BULLISH", f"Headline sentiment positive across {counted} recent articles (avg score {avg_score:+.1f})"
        if avg_score >= 0.25:
            return "POSITIVE", f"Headline sentiment mildly positive across {counted} recent articles (avg score {avg_score:+.1f})"
        if avg_score <= -0.75:
            return "BEARISH", f"Headline sentiment negative across {counted} recent articles (avg score {avg_score:+.1f})"
        if avg_score <= -0.25:
            return "CAUTION", f"Headline sentiment mildly negative across {counted} recent articles (avg score {avg_score:+.1f})"
        return "INFO", f"Headline sentiment mixed across {counted} recent articles (avg score {avg_score:+.1f})"
    except Exception as e:
        logger.error(f"News sentiment check error: {e}")
        return "UNAVAILABLE", "News sentiment unavailable"


def check_google_trends_signal(stock_symbol: str) -> tuple[str, str]:
    """
    Additional Signal — Google Trends.
    Uses India Google Trends interest as a retail-attention context signal.
    This remains non-scoring because attention spikes can be late-cycle noise.
    """
    try:
        snapshot = get_google_trends_snapshot(stock_symbol)
        if not snapshot.get("source_ok"):
            return "UNAVAILABLE", "Google Trends data unavailable"

        term = snapshot.get("term", stock_symbol)
        latest_week = float(snapshot.get("latest_week", 0) or 0)
        baseline = float(snapshot.get("baseline", 0) or 0)
        ratio = float(snapshot.get("ratio", 0) or 0)
        peak = float(snapshot.get("peak", 0) or 0)

        if baseline <= 0 and latest_week <= 0:
            return "UNAVAILABLE", "Google Trends interest unavailable"
        if ratio >= 2.5 and latest_week >= 25:
            return "CAUTION", (
                f"Google Trends spike for '{term}' is {ratio:.1f}x recent baseline "
                f"({latest_week:.0f} vs {baseline:.0f}) — retail attention/FOMO is rising"
            )
        if ratio >= 1.5 and latest_week >= 15:
            return "POSITIVE", (
                f"Google Trends interest for '{term}' is rising to {latest_week:.0f} "
                f"vs baseline {baseline:.0f} ({ratio:.1f}x)"
            )
        if ratio <= 0.7 and baseline >= 10:
            return "INFO", (
                f"Google Trends interest for '{term}' cooled to {latest_week:.0f} "
                f"vs baseline {baseline:.0f} — attention is fading"
            )
        return "INFO", (
            f"Google Trends steady for '{term}': {latest_week:.0f} vs baseline {baseline:.0f}, peak {peak:.0f}"
        )
    except Exception as e:
        logger.error(f"Google Trends signal error: {e}")
        return "UNAVAILABLE", "Google Trends signal unavailable"


def check_short_squeeze_signal(stock_symbol: str) -> tuple[str, str]:
    """
    Additional Signal — Short Squeeze Potential.
    India-friendly proxy using strong price expansion, abnormal volume,
    and optional delivery confirmation for F&O names.
    """
    try:
        nse_symbol = stock_symbol.replace(".NS", "").replace(".BO", "").upper()
        hist = get_market_history(stock_symbol, period="3mo", interval="1d")
        if hist.empty or len(hist) < 25 or "Volume" not in hist.columns:
            return "UNAVAILABLE", "Insufficient price/volume data for short-squeeze proxy"

        close = hist["Close"]
        volume = hist["Volume"].fillna(0)
        current_price = float(close.iloc[-1])
        sma20 = float(close.tail(20).mean())
        ret_5d = ((float(close.iloc[-1]) - float(close.iloc[-6])) / float(close.iloc[-6])) * 100 if len(close) >= 6 else 0.0
        ret_20d = ((float(close.iloc[-1]) - float(close.iloc[-21])) / float(close.iloc[-21])) * 100 if len(close) >= 21 else 0.0
        current_volume = float(volume.iloc[-1] or 0)
        avg_volume = float(volume.iloc[:-1].tail(20).mean() or 0)
        volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1.0
        near_high_20d = current_price >= float(close.tail(20).max()) * 0.98
        is_fno = nse_symbol in FNO_STOCKS

        delivery_pct = 0.0
        try:
            delivery = fetch_delivery_data(nse_symbol)
            delivery_pct = float((delivery or {}).get("delivery_pct", 0) or 0)
        except Exception:
            delivery_pct = 0.0

        if is_fno and ret_5d >= 8 and ret_20d >= 10 and volume_ratio >= 1.8 and current_price >= sma20 and near_high_20d:
            if delivery_pct >= 50:
                return "BULLISH", (
                    f"Short-squeeze proxy active: {ret_5d:+.1f}% in 5d, {volume_ratio:.1f}x volume, "
                    f"delivery {delivery_pct:.1f}%, price above 20DMA"
                )
            return "POSITIVE", (
                f"Short-squeeze proxy strong: {ret_5d:+.1f}% in 5d on {volume_ratio:.1f}x volume near 20-day highs"
            )

        if is_fno and ret_5d >= 5 and volume_ratio >= 1.4 and current_price >= sma20:
            return "INFO", (
                f"Possible squeeze setup: {ret_5d:+.1f}% in 5d on {volume_ratio:.1f}x volume; "
                f"watch for continuation above recent highs"
            )

        if not is_fno:
            return "INFO", "Short-squeeze proxy is less reliable for non-F&O stocks"

        return "NEUTRAL", (
            f"No clean squeeze proxy: 5d move {ret_5d:+.1f}%, volume {volume_ratio:.1f}x, "
            f"20d move {ret_20d:+.1f}%"
        )
    except Exception as e:
        logger.error(f"Short squeeze signal error: {e}")
        return "UNAVAILABLE", "Short-squeeze proxy unavailable"


def check_dow_premarket_signal() -> tuple[str, str]:
    """
    Additional Signal — US overnight / pre-market global signal.
    Uses Dow and S&P latest daily move as a simple pre-open context indicator.
    """
    try:
        dji = get_market_history("^DJI", period="5d", interval="1d")
        spx = get_market_history("^GSPC", period="5d", interval="1d")
        if dji.empty or spx.empty or len(dji) < 2 or len(spx) < 2:
            return "UNAVAILABLE", "US market data unavailable for pre-market signal"

        dji_ret = ((float(dji["Close"].iloc[-1]) - float(dji["Close"].iloc[-2])) / float(dji["Close"].iloc[-2])) * 100
        spx_ret = ((float(spx["Close"].iloc[-1]) - float(spx["Close"].iloc[-2])) / float(spx["Close"].iloc[-2])) * 100
        avg_ret = (dji_ret + spx_ret) / 2

        if avg_ret >= 0.75:
            return "BULLISH", f"US overnight tone strong: Dow {dji_ret:+.1f}%, S&P {spx_ret:+.1f}%"
        if avg_ret >= 0.25:
            return "POSITIVE", f"US overnight tone mildly positive: Dow {dji_ret:+.1f}%, S&P {spx_ret:+.1f}%"
        if avg_ret <= -0.75:
            return "BEARISH", f"US overnight tone weak: Dow {dji_ret:+.1f}%, S&P {spx_ret:+.1f}%"
        if avg_ret <= -0.25:
            return "CAUTION", f"US overnight tone mildly weak: Dow {dji_ret:+.1f}%, S&P {spx_ret:+.1f}%"
        return "INFO", f"US overnight tone mixed: Dow {dji_ret:+.1f}%, S&P {spx_ret:+.1f}%"
    except Exception as e:
        logger.error(f"Dow pre-market signal error: {e}")
        return "UNAVAILABLE", "US pre-market global signal unavailable"


def run_additional_macro_signals(stock_symbol: str) -> list[dict]:
    """
    Run optional non-scoring macro signals for informational context only.
    These signals must not affect the core 21-check score.
    """
    fii_data = fetch_fii_dii_data()
    signals = [
        ("Mutual Fund Holding Change", check_mutual_fund_holding_change(stock_symbol)),
        ("Block/Bulk Deal Scanner", check_block_bulk_deals(stock_symbol)),
        ("FII Sector Rotation", check_fii_sector_rotation(stock_symbol, fii_data)),
        ("China PMI", check_china_pmi_signal(stock_symbol)),
        ("News Sentiment Score", check_news_sentiment_score(stock_symbol)),
        ("Google Trends", check_google_trends_signal(stock_symbol)),
        ("Short Squeeze Potential", check_short_squeeze_signal(stock_symbol)),
        ("Dow / Pre-market Global Signal", check_dow_premarket_signal()),
        ("DXY Impact", check_dxy_impact(stock_symbol)),
        ("US 10Y Yield", check_us10y_yield()),
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


def run_all_macro_checks(stock_symbol: str, fii_data: Optional[dict] = None) -> list[dict]:
    """
    Run all 5 macro checks and return structured results list.
    """
    if fii_data is None:
        fii_data = fetch_fii_dii_data()

    checks = [
        (11, "FII Exit Pressure",   check_fii_exit_pressure(stock_symbol)),
        (12, "Sector Alignment",    check_sector_tailwind_alignment(stock_symbol)),
        (13, "Global Sentiment",    check_global_sentiment()),
        (14, "Commodity Prices",    check_commodity(stock_symbol)),
        (15, "Geopolitical News",   check_geopolitical()),
    ]

    return [
        {
            "check_number": num,
            "category":     "Macro",
            "name":         name,
            "signal":       result[0],
            "detail":       result[1],
        }
        for num, name, result in checks
    ]
