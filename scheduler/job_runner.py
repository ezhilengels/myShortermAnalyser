"""
job_runner.py — APScheduler job definitions.
Schedules:
  - Morning report   @ 8:30 AM IST (Mon–Fri)
  - Evening report   @ 4:15 PM IST (Mon–Fri)
  - Intraday alerts  @ every 15 min (9:00–15:45 IST, Mon–Fri)
  - FII data refresh @ 5:30 PM IST (Mon–Fri)
"""

import logging
import asyncio
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────
# JOB FUNCTIONS
# ─────────────────────────────────────────────

def job_morning_report() -> None:
    """Full 21-condition analysis + morning Telegram report."""
    logger.info(f"🌅 Morning report started at {datetime.now(IST).strftime('%H:%M IST')}")
    try:
        from bot.telegram_bot   import run_all_stocks, send_telegram_message
        from bot.report_builder import build_morning_report

        all_results, all_decisions, prices = run_all_stocks()
        report = build_morning_report(all_results, all_decisions, prices)
        asyncio.run(send_telegram_message(report))
        logger.info("✅ Morning report sent")
    except Exception as e:
        logger.error(f"❌ Morning report failed: {e}")


def job_evening_report() -> None:
    """Post-market analysis + evening Telegram report."""
    logger.info(f"🌆 Evening report started at {datetime.now(IST).strftime('%H:%M IST')}")
    try:
        from bot.telegram_bot   import run_all_stocks, send_telegram_message
        from bot.report_builder import build_evening_report

        all_results, all_decisions, prices = run_all_stocks()
        report = build_evening_report(all_results, all_decisions, prices)
        asyncio.run(send_telegram_message(report))
        logger.info("✅ Evening report sent")
    except Exception as e:
        logger.error(f"❌ Evening report failed: {e}")


def job_price_alerts() -> None:
    """Check all price alerts against current prices and send triggered ones."""
    try:
        from bot.alert_manager  import check_price_alerts
        from bot.telegram_bot   import send_telegram_message

        triggered = check_price_alerts()
        for msg in triggered:
            asyncio.run(send_telegram_message(msg))
            logger.info(f"🔔 Price alert sent: {msg[:80]}")
    except Exception as e:
        logger.error(f"Price alert check failed: {e}")


def job_refresh_fii() -> None:
    """Refresh FII/DII data cache after NSE publishes final data (5:30 PM)."""
    try:
        from data.cache.redis_cache    import cache_delete
        from data.fetchers.fii_fetcher import fetch_fii_dii_data

        cache_delete("fii_dii_data")
        data = fetch_fii_dii_data()
        logger.info(
            f"🔄 FII data refreshed — "
            f"FII: ₹{data.get('fii_cash_net', 0):.0f}Cr | "
            f"DII: ₹{data.get('dii_cash_net', 0):.0f}Cr"
        )
    except Exception as e:
        logger.error(f"FII refresh failed: {e}")


def job_v4_smart_alerts() -> None:
    """Check watchlist for V4 Buy/Exit zones and send alerts."""
    try:
        from bot.alert_manager import check_v4_smart_alerts
        from bot.telegram_bot import send_telegram_message
        from config import WATCHLIST

        triggered = check_v4_smart_alerts(WATCHLIST)
        for msg in triggered:
            asyncio.run(send_telegram_message(msg))
            logger.info(f"💎 V4 Smart Alert sent: {msg[:80]}")
    except Exception as e:
        logger.error(f"V4 Smart alert check failed: {e}")


# ─────────────────────────────────────────────
# SCHEDULER FACTORY
# ─────────────────────────────────────────────

def build_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler with all jobs."""
    scheduler = BackgroundScheduler(timezone=IST)

    # Morning report — 8:30 AM IST, weekdays only
    scheduler.add_job(
        job_morning_report,
        trigger="cron",
        hour=8, minute=30,
        day_of_week="mon-fri",
        id="morning_report",
        name="Morning Report",
        replace_existing=True,
    )

    # Evening report — 4:15 PM IST, weekdays only
    scheduler.add_job(
        job_evening_report,
        trigger="cron",
        hour=16, minute=15,
        day_of_week="mon-fri",
        id="evening_report",
        name="Evening Report",
        replace_existing=True,
    )

    # Intraday price alerts — every 15 min from 9:00–15:45 IST, weekdays
    scheduler.add_job(
        job_price_alerts,
        trigger="cron",
        hour="9-15",
        minute="0,15,30,45",
        day_of_week="mon-fri",
        id="price_alerts",
        name="Price Alert Checker",
        replace_existing=True,
    )

    # V4 Smart Alert checker — every 15 min from 10:00–15:30 IST, weekdays
    scheduler.add_job(
        job_v4_smart_alerts,
        trigger="cron",
        hour="10-15",
        minute="5,20,35,50",
        day_of_week="mon-fri",
        id="v4_smart_alerts",
        name="V4 Smart Alert Checker",
        replace_existing=True,
    )

    # FII data refresh — 5:30 PM IST, weekdays
    scheduler.add_job(
        job_refresh_fii,
        trigger="cron",
        hour=17, minute=30,
        day_of_week="mon-fri",
        id="fii_refresh",
        name="FII Data Refresh",
        replace_existing=True,
    )

    return scheduler
