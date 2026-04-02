"""
main.py — Entry point for the Stock Analysis Bot.

Modes:
  python main.py           → Run Telegram bot + all scheduled jobs
  python main.py --report  → Send one-time report now and exit
  python main.py --analyze NALCO → Analyse one stock and print result
  python main.py --test    → Run a quick connectivity test
  python main.py --validate → Run watchlist validation and export JSON/CSV
  python main.py --benchmark → Run benchmark validation against stored expectations
  python main.py --stocktips [universe] → Run V3 stocktips pipeline and print top picks
  python main.py --valuation [universe] → Run V4 Intrinsic Valuation scan and rank by MoS
"""

import sys
import logging
import asyncio
from datetime import datetime

import pytz

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────

def mode_bot() -> None:
    """Start Telegram bot in polling mode with all scheduled jobs active."""
    from scheduler.job_runner import build_scheduler
    from bot.telegram_bot    import build_application

    logger.info("🚀 Starting Stock Analysis Bot...")
    logger.info(f"   Time (IST): {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}")

    # Start scheduler in background
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("⏰ Scheduler started — morning 8:30, evening 16:15, alerts 15-min")

    # Start Telegram polling (blocking)
    app = build_application()
    logger.info("📱 Telegram bot polling started")
    app.run_polling(drop_pending_updates=True)

    # Cleanup on exit
    scheduler.shutdown()
    logger.info("Bot stopped cleanly.")


def mode_report() -> None:
    """Send a single full report immediately and exit."""
    from bot.telegram_bot   import run_all_stocks, send_telegram_message
    from bot.report_builder import build_morning_report

    logger.info("📊 Generating one-time report...")
    all_results, all_decisions, prices = run_all_stocks()
    report = build_morning_report(all_results, all_decisions, prices)
    asyncio.run(send_telegram_message(report))
    logger.info("✅ Report sent. Exiting.")


def mode_analyze(symbol: str) -> None:
    """Run analysis for a single stock and print result to console."""
    from bot.telegram_bot    import analyse_single_stock
    from bot.report_builder  import build_single_stock_report

    logger.info(f"🔍 Analysing {symbol}...")
    result, decision, price = analyse_single_stock(symbol)
    report = build_single_stock_report(result, decision, price)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)


def mode_test() -> None:
    """Quick connectivity and import test."""
    logger.info("🧪 Running connectivity test...")

    # Test yfinance
    from data.fetchers.yfinance_fetcher import get_current_price
    price = get_current_price("NATIONALUM.NS")
    logger.info(f"  yfinance: NALCO price = ₹{price:.2f} {'✅' if price > 0 else '❌'}")

    # Test commodity
    from data.fetchers.commodity_fetcher import get_india_vix
    vix = get_india_vix()
    logger.info(f"  India VIX = {vix:.2f} {'✅' if vix > 0 else '❌'}")

    # Test FII
    from data.fetchers.fii_fetcher import fetch_fii_dii_data
    fii = fetch_fii_dii_data()
    logger.info(f"  FII Cash = ₹{fii.get('fii_cash_net', 'N/A')}Cr {'✅' if fii else '❌'}")

    # Test NSE
    try:
        from data.fetchers.nse_fetcher import get_nse_session
        sess = get_nse_session()
        logger.info("  NSE session ✅")
    except Exception as e:
        logger.warning(f"  NSE session ❌ ({e})")

    # Test Groq
    try:
        from groq import Groq
        from config import GROQ_API_KEY
        client = Groq(api_key=GROQ_API_KEY)
        logger.info("  Groq client ✅")
    except Exception as e:
        logger.warning(f"  Groq client ❌ ({e})")

    # Test Telegram
    try:
        from telegram import Bot
        from config import TELEGRAM_BOT_TOKEN
        import asyncio
        async def _check():
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            me = await bot.get_me()
            return me.username
        username = asyncio.run(_check())
        logger.info(f"  Telegram bot @{username} ✅")
    except Exception as e:
        logger.warning(f"  Telegram bot ❌ ({e})")

    logger.info("✅ Test complete.")


def mode_validate() -> None:
    """Run the watchlist validation helper and print a concise summary."""
    from validation_runner import (
        run_watchlist_validation,
        build_validation_review,
        evaluate_priority4_validation,
    )

    logger.info("🧾 Running watchlist validation...")
    result = run_watchlist_validation()
    review = build_validation_review(result["rows"])
    priority4 = evaluate_priority4_validation(result["rows"])

    print("\nValidation summary")
    print("=" * 60)
    for row in result["rows"]:
        print(
            f"{row['name']:<12} grade={row['grade']:<2} "
            f"score={row['score']:<5} core={row['core_score']:<5} "
            f"context={row['context_score']:<5} conf={row['average_confidence']:.2f} "
            f"unavail={row['unavailable_checks']}"
        )
    print("=" * 60)
    print(f"JSON: {result['json_path']}")
    print(f"CSV : {result['csv_path']}")
    print(f"Review CSV: {result['review_csv_path']}")

    print("\nReview buckets")
    print("=" * 60)
    print(
        "High-confidence buys:",
        ", ".join(r["name"] for r in review["high_confidence_buys"]) or "None",
    )
    print(
        "Low-confidence buys:",
        ", ".join(r["name"] for r in review["low_confidence_buys"]) or "None",
    )
    print(
        "Blocked by data:",
        ", ".join(r["name"] for r in review["blocked_by_data"]) or "None",
    )
    print(
        "Bearish/avoid:",
        ", ".join(r["name"] for r in review["bearish_or_avoid"]) or "None",
    )

    print("\nPriority 4 Validation")
    print("=" * 60)
    print(f"Status: {priority4['status']}")
    print(
        f"Symbols with live derivative/delivery validation: "
        f"{priority4['symbols_with_live_derivatives']}/{priority4['reviewed_symbols']}"
    )


def mode_benchmark() -> None:
    """Run benchmark validation against stored human expectations."""
    from validation_runner import run_benchmark_validation

    logger.info("🎯 Running benchmark validation...")
    result = run_benchmark_validation()
    summary = result["summary"]

    print("\nBenchmark summary")
    print("=" * 60)
    print(f"Benchmark file: {result['path']}")
    print(f"As of: {result.get('benchmark_as_of') or 'N/A'}")
    print(f"Accuracy: {summary['accuracy']}%")
    print(
        f"PASS={summary['pass']}  CLOSE={summary['close']}  "
        f"MISS={summary['miss']}  TOTAL={summary['total_cases']}"
    )
    print("=" * 60)
    for row in result["results"]:
        print(
            f"{row['name']:<12} {row['status']:<5} "
            f"rule {row['actual_rule_verdict']:<5}/{row['expected_rule_verdict']:<5} "
            f"ai {row['actual_ai_verdict']:<5}/{row['expected_ai_verdict']:<5} "
            f"core={row['core_score']:<5} conf={row['average_confidence']:.2f}"
        )
    print("=" * 60)
    print(f"JSON: {result['json_path']}")


def mode_stocktips(universe: str = "watchlist") -> None:
    """Run the separate V3 /stocktips pipeline and print the result."""
    from v3.stocktips_pipeline import format_stocktips_console, run_stocktips_pipeline

    logger.info(f"📌 Running V3 /stocktips pipeline for universe: {universe}")
    result = run_stocktips_pipeline(universe=universe)
    print("\n" + format_stocktips_console(result))


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import os
    os.makedirs("logs", exist_ok=True)

    args = sys.argv[1:]

    if "--report" in args:
        mode_report()
    elif "--analyze" in args:
        idx = args.index("--analyze")
        sym = args[idx + 1] if idx + 1 < len(args) else "NATIONALUM.NS"
        mode_analyze(sym)
    elif "--test" in args:
        mode_test()
    elif "--validate" in args:
        mode_validate()
    elif "--benchmark" in args:
        mode_benchmark()
    elif "--stocktips" in args:
        idx = args.index("--stocktips")
        universe = args[idx + 1] if idx + 1 < len(args) and not args[idx + 1].startswith("--") else "watchlist"
        mode_stocktips(universe)
    else:
        mode_bot()
