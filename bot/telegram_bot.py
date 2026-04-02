"""
telegram_bot.py — Telegram Bot handlers for all commands.

Commands:
  /analyze SYMBOL   — Full 21-condition analysis of any stock
  /stocktips [universe] — V3 top stock ideas from the separate pipeline
  /report           — Get latest full report now
  /watchlist        — Show all watched stocks
  /add SYMBOL       — Add stock to watchlist
  /remove SYMBOL    — Remove stock from watchlist
  /fii              — Show today's FII/DII data
  /vix              — Show India VIX and fear level
  /commodity        — Show all commodity prices
  /alert SYMBOL PRICE [above|below] — Set price alert
  /alerts           — List all active alerts
  /removealert SYMBOL — Remove alert for a stock
  /help             — Show all commands
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WATCHLIST, STOCK_NAMES, SYMBOL_ALIASES
from data.fetchers.yfinance_fetcher  import (
    get_ticker_info, get_historical_data, get_1h_data,
    get_financials, get_balance_sheet, get_current_price,
)
from data.fetchers.fii_fetcher       import fetch_fii_dii_data
from data.fetchers.commodity_fetcher import get_all_commodities, get_india_vix, get_us_vix
from analysis.scorer                 import run_full_analysis
from ai.groq_engine                  import get_groq_decision
from bot.report_builder              import (
    build_morning_report, build_evening_report, build_single_stock_report, build_stocktips_report
)
from bot.alert_manager               import add_alert, remove_alert, check_price_alerts, list_alerts

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# SYMBOL NORMALIZATION
# ─────────────────────────────────────────────

def normalize_symbol_input(symbol_input: str) -> str:
    """Resolve user input like NALCO into the Yahoo Finance symbol used internally."""
    raw = (symbol_input or "").strip().upper()
    if not raw:
        return raw

    if raw in WATCHLIST:
        return raw

    if raw.endswith(".NS") or raw.endswith(".BO"):
        return raw

    if raw in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[raw]

    # Allow human-friendly watchlist names like NALCO -> NATIONALUM.NS
    for ticker, display_name in STOCK_NAMES.items():
        if raw == display_name.upper():
            return ticker

    return raw + ".NS"


# ─────────────────────────────────────────────
# HELPER — Run analysis for a single stock
# ─────────────────────────────────────────────

def analyse_single_stock(symbol: str) -> tuple[dict, dict, float]:
    """
    Run full 21-condition analysis + Groq decision for one stock.
    Returns (stock_result, ai_decision, current_price)
    """
    symbol = normalize_symbol_input(symbol)

    df          = get_historical_data(symbol, period="1y", interval="1d")
    df_1h       = get_1h_data(symbol)
    ticker_info = get_ticker_info(symbol)
    financials  = get_financials(symbol)
    balance_sheet = get_balance_sheet(symbol)
    fii_data    = fetch_fii_dii_data()
    price       = get_current_price(symbol)

    from data.fetchers.commodity_fetcher import get_india_vix
    from analysis.macro import check_sector_tailwind_alignment, check_fii_exit_pressure

    india_mood_result = check_sector_tailwind_alignment(symbol)
    fii_result        = check_fii_exit_pressure(symbol)

    market_context = {
        "india_market_mood": india_mood_result[1],
        "fii_summary":       fii_result[1],
        "vix":               get_india_vix(),
    }

    stock_result = run_full_analysis(
        symbol, df, df_1h, ticker_info, financials, balance_sheet, fii_data
    )
    ai_decision  = get_groq_decision(
        symbol,
        STOCK_NAMES.get(symbol, symbol.replace(".NS", "")),
        stock_result["all_checks"],
        stock_result["scoring"],
        price,
        market_context,
    )

    return stock_result, ai_decision, price


def run_all_stocks() -> tuple[list, dict, dict]:
    """
    Run analysis for all WATCHLIST stocks.
    Returns (all_results, all_decisions, current_prices)
    """
    all_results   = []
    all_decisions = {}
    prices        = {}

    for sym in WATCHLIST:
        try:
            result, decision, price = analyse_single_stock(sym)
            all_results.append(result)
            all_decisions[sym] = decision
            prices[sym]        = price
            logger.info(f"✅ {sym} analysed — {result['scoring']['grade']}")
        except Exception as e:
            logger.error(f"Analysis failed for {sym}: {e}")

    return all_results, all_decisions, prices


# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Stock Analysis Bot Active!*\n\n"
        "Use /help to see all commands.\n"
        "Use /report to get the latest full analysis now.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📖 *Available Commands*\n\n"
        "/analyze NALCO — Full 21-condition analysis\n"
        "/stocktips [universe] — V3 top stock ideas\n"
        "/report — Get today's full report now\n"
        "/watchlist — Show all tracked stocks\n"
        "/add SYMBOL — Add stock to watchlist\n"
        "/remove SYMBOL — Remove stock from watchlist\n"
        "/fii — Today's FII/DII data\n"
        "/vix — India VIX & fear level\n"
        "/commodity — All commodity prices\n"
        "/alert NALCO 395 above — Set price alert\n"
        "/alerts — List all active alerts\n"
        "/removealert NALCO — Remove NALCO alerts\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /analyze NALCO  or  /analyze HINDZINC")
        return

    symbol_input = args[0].upper()
    resolved_symbol = normalize_symbol_input(symbol_input)
    await update.message.reply_text(f"⏳ Analysing {resolved_symbol} across all 21 conditions...")

    try:
        result, decision, price = analyse_single_stock(resolved_symbol)
        report = build_single_stock_report(result, decision, price)
        # Telegram messages have 4096 char limit; split if needed
        for chunk in _split_message(report):
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"/analyze error: {e}")
        await update.message.reply_text(f"❌ Analysis failed for {resolved_symbol}: {e}")


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Running full analysis for all stocks... (30–60 sec)")
    try:
        all_results, all_decisions, prices = run_all_stocks()
        report = build_morning_report(all_results, all_decisions, prices)
        for chunk in _split_message(report):
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"/report error: {e}")
        await update.message.reply_text(f"❌ Report generation failed: {e}")


async def cmd_stocktips(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    universe = ctx.args[0].strip() if ctx.args else "watchlist"
    await update.message.reply_text(f"⏳ Running V3 /stocktips for {universe}...")
    try:
        from pathlib import Path
        from v3.stocktips_pipeline import run_stocktips_pipeline
        from v3.universe_loader import BUILTIN_UNIVERSES

        builtin_names = set(BUILTIN_UNIVERSES.keys())
        looks_like_path = any(token in universe for token in ("/", "\\", ".txt", ".csv", ".json"))
        if universe.lower() not in builtin_names and not looks_like_path:
            valid = ", ".join(sorted(builtin_names))
            await update.message.reply_text(
                f"⚠️ Unknown universe '{universe}'. Use one of: {valid}"
            )
            return

        if looks_like_path and not Path(universe).expanduser().exists():
            await update.message.reply_text(f"⚠️ Universe file not found: {universe}")
            return

        result = run_stocktips_pipeline(universe=universe)
        report = build_stocktips_report(result)
        for chunk in _split_message(report):
            await update.message.reply_text(chunk)
    except Exception as e:
        logger.error(f"/stocktips error: {e}")
        await update.message.reply_text(f"❌ /stocktips failed for {universe}: {e}")


async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["📋 *Current Watchlist*\n"]
    for sym in WATCHLIST:
        name  = STOCK_NAMES.get(sym, sym)
        price = get_current_price(sym)
        lines.append(f"• {name} ({sym}) — ₹{price:.2f}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_fii(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = fetch_fii_dii_data()
        fii  = data.get("fii_cash_net", 0)
        dii  = data.get("dii_cash_net", 0)
        fut  = data.get("fii_futures_net", 0)

        msg = (
            "💰 *FII/DII Activity*\n\n"
            f"• FII Cash: {'▲' if fii > 0 else '▼'} ₹{abs(fii):.0f}Cr {'🟢 BUYING' if fii > 0 else '🔴 SELLING'}\n"
            f"• DII Cash: {'▲' if dii > 0 else '▼'} ₹{abs(dii):.0f}Cr {'🟢 BUYING' if dii > 0 else '🔴 SELLING'}\n"
            f"• FII Futures: NET {'🟢 LONG' if fut > 0 else '🔴 SHORT'} ₹{abs(fut):.0f}Cr\n\n"
            f"Market implication: {'🚀 Bullish — institutions buying!' if fii > 0 and dii > 0 else '⚠️ Caution — FII selling'}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ FII data fetch failed: {e}")


async def cmd_vix(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        india_vix = get_india_vix()
        us_vix    = get_us_vix()

        if india_vix > 25:
            sentiment = "🔴 HIGH FEAR — reduce position size!"
        elif india_vix > 18:
            sentiment = "⚠️ ELEVATED FEAR — be cautious"
        elif india_vix < 12:
            sentiment = "😐 COMPLACENCY — markets may correct"
        else:
            sentiment = "✅ NORMAL — good trading environment"

        msg = (
            "📊 *Volatility Index*\n\n"
            f"• India VIX: {india_vix:.2f}\n"
            f"• US VIX: {us_vix:.2f}\n"
            f"• Sentiment: {sentiment}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ VIX fetch failed: {e}")


async def cmd_commodity(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        commodities = get_all_commodities()
        lines = ["🏭 *Commodity Prices*\n"]
        for ticker, data in commodities.items():
            name   = data.get("name", ticker)
            price  = data.get("price", 0)
            change = data.get("change_pct", 0)
            arrow  = "▲" if change >= 0 else "▼"
            dot    = "🟢" if change >= 0 else "🔴"
            lines.append(f"{dot} {name}: ${price} ({arrow}{abs(change):.2f}%)")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Commodity fetch failed: {e}")


async def cmd_alert(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /alert NALCO 395 above  OR  /alert NALCO 380 below"""
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Usage: /alert NALCO 395 above\n"
            "Direction: 'above' (default) or 'below'"
        )
        return

    symbol    = args[0].upper()
    if not symbol.endswith(".NS"):
        symbol += ".NS"

    try:
        target    = float(args[1])
        direction = args[2].lower() if len(args) > 2 else "above"
        if direction not in ("above", "below"):
            direction = "above"
        msg = add_alert(symbol, target, direction)
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Usage: /alert NALCO 395 above")


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = list_alerts()
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_removealert(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /removealert NALCO")
        return
    symbol = args[0].upper()
    if not symbol.endswith(".NS"):
        symbol += ".NS"
    msg = remove_alert(symbol)
    await update.message.reply_text(msg)


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def _split_message(text: str, limit: int = 4000) -> list[str]:
    """Split long messages into chunks for Telegram's 4096 char limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunk = text[:limit]
        last_newline = chunk.rfind("\n")
        if last_newline > 0:
            chunk = chunk[:last_newline]
        chunks.append(chunk)
        text = text[len(chunk):]
    return chunks


# ─────────────────────────────────────────────
# BOT FACTORY
# ─────────────────────────────────────────────

def build_application() -> Application:
    """Create and configure the Telegram Application with all command handlers."""
    # We use APScheduler separately for all timed jobs, so disable PTB's
    # optional JobQueue to avoid starting a second scheduler instance.
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).job_queue(None).build()

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("analyze",     cmd_analyze))
    app.add_handler(CommandHandler("stocktips",   cmd_stocktips))
    app.add_handler(CommandHandler("report",      cmd_report))
    app.add_handler(CommandHandler("watchlist",   cmd_watchlist))
    app.add_handler(CommandHandler("fii",         cmd_fii))
    app.add_handler(CommandHandler("vix",         cmd_vix))
    app.add_handler(CommandHandler("commodity",   cmd_commodity))
    app.add_handler(CommandHandler("alert",       cmd_alert))
    app.add_handler(CommandHandler("alerts",      cmd_alerts))
    app.add_handler(CommandHandler("removealert", cmd_removealert))

    return app


async def send_telegram_message(text: str, parse_mode: str = ParseMode.MARKDOWN) -> None:
    """Send a message to the configured chat. Used by the scheduler."""
    app = build_application()
    async with app:
        for chunk in _split_message(text):
            try:
                await app.bot.send_message(
                    chat_id    = TELEGRAM_CHAT_ID,
                    text       = chunk,
                    parse_mode = parse_mode,
                )
            except Exception as e:
                logger.error(f"Telegram send error: {e}")
