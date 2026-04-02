"""
report_builder.py — Builds formatted Morning and Evening Telegram report messages.
Output is Markdown-compatible for Telegram (MarkdownV2 parse mode).
"""

import logging
from datetime import datetime
import pytz

from config import DISCLAIMER, STOCK_NAMES
from data.fetchers.commodity_fetcher import get_all_commodities, get_india_vix
from data.fetchers.fii_fetcher       import fetch_fii_dii_data

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────
# EMOJI HELPERS
# ─────────────────────────────────────────────

def _verdict_emoji(verdict: str) -> str:
    mapping = {
        "STRONG BUY":  "🚀",
        "BUY":         "✅",
        "HOLD":        "⏳",
        "SELL":        "⚠️",
        "STRONG SELL": "🔴",
    }
    return mapping.get(verdict.upper(), "📊")


def _grade_emoji(grade: str) -> str:
    mapping = {
        "A+": "🏆",
        "A":  "🥇",
        "B+": "🥈",
        "B":  "📊",
        "C":  "⚠️",
        "D":  "🔴",
    }
    return mapping.get(grade, "📊")


def _signal_dot(signal: str) -> str:
    if signal == "UNAVAILABLE":
        return "⚪"
    if signal == "INFO":
        return "🔵"

    weights = {
        2: "🟢🟢", 1: "🟢", 0: "🟡", -1: "🔴", -2: "🔴🔴"
    }
    from config import SIGNAL_WEIGHTS
    w = SIGNAL_WEIGHTS.get(signal, 0)
    return weights.get(w, "🟡")


def _escape_md(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


# ─────────────────────────────────────────────
# GLOBAL SNAPSHOT SECTION
# ─────────────────────────────────────────────

def _build_global_snapshot(fii_data: dict, commodities: dict) -> str:
    vix = get_india_vix()
    fii = fii_data.get("fii_cash_net", 0)
    dii = fii_data.get("dii_cash_net", 0)
    fut = fii_data.get("fii_futures_net", 0)

    crude  = commodities.get("BZ=F",  {}).get("price", "N/A")
    silver = commodities.get("SI=F",  {}).get("price", "N/A")
    alum   = commodities.get("ALI=F", {}).get("price", "N/A")
    zinc   = commodities.get("ZNC=F", {}).get("price", "N/A")

    fii_arrow = "🟢" if fii > 0 else "🔴"
    dii_arrow = "🟢" if dii > 0 else "🔴"
    fut_arrow = "🟢" if fut > 0 else "🔴"

    return (
        "🌍 *GLOBAL SNAPSHOT*\n"
        f"• India VIX: {vix:.1f} {'⚠️ HIGH FEAR' if vix > 20 else '✅ Normal'}\n"
        f"• Brent Crude: ${crude}\n"
        f"• COMEX Silver: ${silver}\n"
        f"• LME Aluminium: ${alum}\n"
        f"• LME Zinc: ${zinc}\n"
        "\n💰 *FII/DII ACTIVITY*\n"
        f"• FII Cash: {'▲' if fii > 0 else '▼'} ₹{abs(fii):.0f}Cr {fii_arrow}\n"
        f"• DII Cash: {'▲' if dii > 0 else '▼'} ₹{abs(dii):.0f}Cr {dii_arrow}\n"
        f"• FII Futures: NET {'LONG' if fut > 0 else 'SHORT'} ₹{abs(fut):.0f}Cr {fut_arrow}\n"
    )


# ─────────────────────────────────────────────
# SINGLE STOCK SECTION
# ─────────────────────────────────────────────

def _build_stock_section(
    index: int,
    stock_result: dict,
    ai_decision: dict,
    current_price: float,
) -> str:
    symbol   = stock_result["symbol"]
    name     = STOCK_NAMES.get(symbol, symbol.replace(".NS", ""))
    scoring  = stock_result["scoring"]
    score    = scoring["score"]
    grade    = scoring["grade"]
    verdict  = ai_decision.get("verdict", scoring["verdict"])
    conf     = ai_decision.get("confidence", 5)

    st = ai_decision.get("short_term", {})
    mt = ai_decision.get("medium_term", {})

    risks     = ai_decision.get("key_risks",     [])
    catalysts = ai_decision.get("key_catalysts", [])
    summary   = ai_decision.get("summary", "")

    b_cnt = scoring["bullish_count"]
    n_cnt = scoring["neutral_count"]
    r_cnt = scoring["bearish_count"]

    section = (
        f"{index}️⃣ *{name}* — ₹{current_price:.2f}\n"
        f"   Score: 🟢{b_cnt} 🟡{n_cnt} 🔴{r_cnt} | Grade: {_grade_emoji(grade)}{grade}\n"
        f"   Core/Context: {scoring.get('core_score', 0)}/{scoring.get('context_score', 0)}"
        f" | Avg conf: {scoring.get('average_confidence', 0):.2f}\n"
        f"   {_verdict_emoji(verdict)} Verdict: *{verdict}* | Confidence: {conf}/10\n"
    )

    # Short term
    if st.get("entry") and st["entry"] != "N/A":
        section += (
            f"   📈 Short\\-term: Entry {st.get('entry','N/A')} | "
            f"Target {st.get('target','N/A')} | SL {st.get('stop_loss','N/A')}\n"
        )

    # Medium term
    if mt.get("entry") and mt["entry"] != "N/A":
        section += (
            f"   📅 Mid\\-term: Entry {mt.get('entry','N/A')} | "
            f"Target {mt.get('target','N/A')} | SL {mt.get('stop_loss','N/A')}\n"
        )

    # Catalysts
    if catalysts:
        section += f"   🔑 Catalyst: {catalysts[0]}\n"

    # Risks
    if risks:
        section += f"   ⚠️ Risk: {risks[0]}\n"

    # Summary
    if summary:
        section += f"   💬 {summary[:150]}\n"

    return section


# ─────────────────────────────────────────────
# SECRET SIGNALS SUMMARY
# ─────────────────────────────────────────────

def _build_secret_signals(all_stock_results: list[dict]) -> str:
    lines = ["🔐 *SECRET SIGNALS TODAY*"]
    for res in all_stock_results:
        name   = STOCK_NAMES.get(res["symbol"], res["symbol"].replace(".NS", ""))
        checks = res.get("all_checks", [])
        for c in checks:
            cname  = c.get("name", "")
            signal = c.get("signal", "")
            detail = c.get("detail", "")
            # Highlight only notable secret signals
            if c["check_number"] >= 16 and signal not in ("NEUTRAL", "UNAVAILABLE", "INFO"):
                dot = _signal_dot(signal)
                lines.append(f"• {name} {cname}: {dot} {detail[:60]}")

    if len(lines) == 1:
        lines.append("• No notable secret signals today")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# ACTION PLAN
# ─────────────────────────────────────────────

def _build_action_plan(all_stock_results: list[dict], all_ai_decisions: dict) -> str:
    lines = ["⚡ *TODAY'S ACTION PLAN*"]
    for res in all_stock_results:
        sym    = res["symbol"]
        name   = STOCK_NAMES.get(sym, sym.replace(".NS", ""))
        dec    = all_ai_decisions.get(sym, {})
        verdict = dec.get("verdict", res["scoring"]["verdict"])
        st     = dec.get("short_term", {})

        if "BUY" in verdict.upper():
            entry = st.get("entry", "CMP")
            lines.append(f"✅ {name}: Open above {entry} → ENTER")
        elif "SELL" in verdict.upper():
            lines.append(f"❌ {name}: SELL / AVOID — bearish signals")
        else:
            lines.append(f"⏳ {name}: HOLD / WAIT — monitor for entry")

    lines.append("❌ Don't trade if India VIX > 25")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# FULL REPORT BUILDERS
# ─────────────────────────────────────────────

def build_morning_report(
    all_stock_results: list[dict],
    all_ai_decisions: dict,
    current_prices: dict,
) -> str:
    """Build full morning report (8:30 AM)."""
    fii_data    = fetch_fii_dii_data()
    commodities = get_all_commodities()
    now         = datetime.now(IST)
    date_str    = now.strftime("%d\\-%b\\-%Y")
    time_str    = now.strftime("%I:%M %p IST")

    header = (
        "📊 *MORNING MARKET REPORT*\n"
        f"⏰ {time_str} | {date_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    global_section = _build_global_snapshot(fii_data, commodities)

    stocks_section = "\n━━━━━━━━━━━━━━━━━━━━━━\n📈 *STOCK ANALYSIS*\n\n"
    for i, res in enumerate(all_stock_results, 1):
        sym   = res["symbol"]
        price = current_prices.get(sym, 0)
        dec   = all_ai_decisions.get(sym, {})
        stocks_section += _build_stock_section(i, res, dec, price) + "\n"

    secret_section = (
        "\n━━━━━━━━━━━━━━━━━━━━━━\n" +
        _build_secret_signals(all_stock_results)
    )

    action_section = (
        "\n━━━━━━━━━━━━━━━━━━━━━━\n" +
        _build_action_plan(all_stock_results, all_ai_decisions)
    )

    disclaimer_text = "\n\n" + DISCLAIMER

    return header + global_section + stocks_section + secret_section + action_section + disclaimer_text


def build_evening_report(
    all_stock_results: list[dict],
    all_ai_decisions: dict,
    current_prices: dict,
) -> str:
    """Build evening post-market report (4:15 PM)."""
    fii_data    = fetch_fii_dii_data()
    commodities = get_all_commodities()
    now         = datetime.now(IST)
    date_str    = now.strftime("%d\\-%b\\-%Y")

    header = (
        "📊 *EVENING MARKET WRAP*\n"
        f"🔔 End of Day | {date_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    global_section = _build_global_snapshot(fii_data, commodities)

    stocks_section = "\n━━━━━━━━━━━━━━━━━━━━━━\n📉 *EOD ANALYSIS*\n\n"
    for i, res in enumerate(all_stock_results, 1):
        sym   = res["symbol"]
        price = current_prices.get(sym, 0)
        dec   = all_ai_decisions.get(sym, {})
        stocks_section += _build_stock_section(i, res, dec, price) + "\n"

    delivery_section = "\n━━━━━━━━━━━━━━━━━━━━━━\n📦 *DELIVERY & SMART MONEY*\n"
    for res in all_stock_results:
        name   = STOCK_NAMES.get(res["symbol"], res["symbol"].replace(".NS", ""))
        checks = res.get("all_checks", [])
        for c in checks:
            if c.get("name") == "Delivery % (Smart Money)":
                delivery_section += f"• {name}: {c['detail'][:80]}\n"

    disclaimer_text = "\n\n" + DISCLAIMER

    return header + global_section + stocks_section + delivery_section + disclaimer_text


def build_single_stock_report(
    stock_result: dict,
    ai_decision: dict,
    current_price: float,
) -> str:
    """Build a compact single-stock analysis for /analyze command."""
    sym     = stock_result["symbol"]
    name    = STOCK_NAMES.get(sym, sym.replace(".NS", ""))
    scoring = stock_result["scoring"]
    checks  = stock_result.get("all_checks", [])
    additional_signals = stock_result.get("additional_signals", [])
    now     = datetime.now(IST).strftime("%d-%b-%Y %I:%M %p IST")

    header = (
        f"📊 *{name} Analysis*\n"
        f"🕐 {now}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    stock_section = _build_stock_section(1, stock_result, ai_decision, current_price)

    conditions = "\n━━━━━━━━━━━━━━━━━━━━━━\n*21\\-CONDITION SCORECARD*\n"
    current_cat = None
    for c in sorted(checks, key=lambda x: x["check_number"]):
        cat = c["category"]
        if cat != current_cat:
            current_cat = cat
            conditions += f"\n_{cat}_\n"
        dot  = _signal_dot(c["signal"])
        detail_short = c["detail"][:60]
        conf = c.get("confidence", 0)
        src  = c.get("source", "Unknown")[:22]
        conditions += (
            f"{dot} {c['check_number']:2d}\\. {c['name']}: {detail_short} "
            f"\\(conf {conf:.2f}, {src}\\)\n"
        )

    additional = ""
    if additional_signals:
        additional = "\n━━━━━━━━━━━━━━━━━━━━━━\n*ADDITIONAL SIGNALS \\(non\\-scoring\\)*\n"
        for sig in additional_signals:
            dot = _signal_dot(sig["signal"])
            detail_short = sig["detail"][:70]
            additional += f"{dot} {sig['name']}: {detail_short}\n"

    return header + stock_section + conditions + additional + "\n" + DISCLAIMER


def build_stocktips_report(result: dict) -> str:
    """Build a detailed plain-text Telegram report for the separate V3 /stocktips flow."""
    universe = result.get("universe", {})
    prefilter = result.get("prefilter", {})
    ranking = result.get("ranking", {})
    selection = result.get("ai_selection", {})
    now = datetime.now(IST).strftime("%d-%b-%Y %I:%M %p IST")

    header = (
        "📊 *STOCKTIPS V3 REPORT*\n"
        f"🕐 {now}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    overview = (
        f"🌐 *Universe:* {universe.get('name', 'unknown')} ({universe.get('count', 0)} stocks)\n"
        f"🔍 *Pre-filter:* {len(prefilter.get('passed', []))}/{prefilter.get('total', 0)} passed "
        f"({prefilter.get('pass_rate', 0)}%)\n"
        f"🏆 *Shortlist ranked:* {len(ranking.get('ranked', []))}\n"
    )

    picks = selection.get("top_3", [])
    picks_section = "\n🚀 *TOP PICKS*\n"
    if not picks:
        picks_section += "No high-conviction picks today.\n"
    else:
        for pick in picks:
            picks_section += (
                f"\n*{pick['rank']}. {pick['name']}* ({pick['symbol']})\n"
                f"✨ Why: {pick['why']}\n"
                f"⚠️ Risk: {pick['risk']}\n"
            )

    shortlist = ranking.get("ranked", [])[:10]
    shortlist_section = "\n📋 *SHORTLIST SNAPSHOT*\n"
    if not shortlist:
        shortlist_section += "No ranked shortlist available.\n"
    else:
        for row in shortlist:
            name = STOCK_NAMES.get(row["symbol"], row["symbol"].replace(".NS", ""))
            score_text = f"{row['score']:+.2f}"
            adj_score = f"{row.get('adjusted_score', 0):+.2f}"
            conf_text = f"{row['confidence']:.2f}"
            
            # Extract passed/failed checks
            checks = row.get("checks", [])
            passed = [c["name"] for c in checks if c["score"] > 0]
            failed = [c["name"] for c in checks if c["score"] < 0]
            
            shortlist_section += (
                f"\n🔹 *{name}* ({row['symbol']})\n"
                f"   Score: {score_text} (Adj: {adj_score}) | Conf: {conf_text}\n"
            )
            if passed:
                shortlist_section += f"   ✅ Passed: {', '.join(passed[:5])}\n"
            if failed:
                shortlist_section += f"   ❌ Failed: {', '.join(failed[:5])}\n"

    watchouts = selection.get("watchouts", [])
    watchout_section = ""
    if watchouts:
        watchout_section = "\n⚠️ *WATCHOUTS*\n"
        for note in watchouts[:3]:
            watchout_section += f"• {note}\n"

    market_note = selection.get("market_note", "")
    note_section = ""
    if market_note:
        note_section = f"\n📝 *MARKET NOTE*\n{market_note}\n"

    return header + overview + picks_section + shortlist_section + watchout_section + note_section + "\n" + DISCLAIMER
