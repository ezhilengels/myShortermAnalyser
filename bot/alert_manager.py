"""
alert_manager.py — Price alert system.
Stores alerts in a JSON file. Checks prices every 15 minutes during market hours.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from data.fetchers.yfinance_fetcher import get_current_price
from config import STOCK_NAMES

logger = logging.getLogger(__name__)

ALERTS_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "price_alerts.json")


def _load_alerts() -> dict:
    try:
        if os.path.exists(ALERTS_FILE):
            with open(ALERTS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Alert load error: {e}")
    return {}


def _save_alerts(alerts: dict) -> None:
    try:
        os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
        with open(ALERTS_FILE, "w") as f:
            json.dump(alerts, f, indent=2)
    except Exception as e:
        logger.error(f"Alert save error: {e}")


def add_alert(symbol: str, target_price: float, direction: str = "above") -> str:
    """
    Add a price alert.
    direction: 'above' (alert when price >= target) or 'below' (alert when price <= target)
    """
    alerts = _load_alerts()
    key    = f"{symbol}_{target_price}_{direction}"

    if key not in alerts:
        alerts[key] = {
            "symbol":       symbol,
            "target_price": target_price,
            "direction":    direction,
            "created_at":   datetime.now().isoformat(),
            "triggered":    False,
        }
        _save_alerts(alerts)
        name = STOCK_NAMES.get(symbol, symbol)
        return f"✅ Alert set: {name} {'above' if direction == 'above' else 'below'} ₹{target_price}"
    return f"⚠️ Alert already exists for {symbol} at ₹{target_price}"


def remove_alert(symbol: str, target_price: Optional[float] = None) -> str:
    """Remove alerts for a stock (all if target_price is None)."""
    alerts = _load_alerts()
    removed = 0
    to_delete = []

    for key, alert in alerts.items():
        if alert["symbol"] == symbol:
            if target_price is None or abs(alert["target_price"] - target_price) < 0.01:
                to_delete.append(key)

    for key in to_delete:
        del alerts[key]
        removed += 1

    _save_alerts(alerts)
    name = STOCK_NAMES.get(symbol, symbol)
    return f"✅ Removed {removed} alert(s) for {name}"


def check_price_alerts() -> list[str]:
    """
    Check all active alerts against current prices.
    Returns list of triggered alert messages.
    """
    alerts   = _load_alerts()
    triggered = []
    updated  = False

    for key, alert in alerts.items():
        if alert.get("triggered"):
            continue
        try:
            symbol       = alert["symbol"]
            target_price = float(alert["target_price"])
            direction    = alert.get("direction", "above")
            current      = get_current_price(symbol)
            name         = STOCK_NAMES.get(symbol, symbol)

            hit = (
                (direction == "above" and current >= target_price) or
                (direction == "below" and current <= target_price)
            )

            if hit:
                msg = (
                    f"🔔 *PRICE ALERT TRIGGERED!*\n"
                    f"• {name} ({symbol})\n"
                    f"• Current: ₹{current:.2f}\n"
                    f"• Alert: {'≥' if direction == 'above' else '≤'} ₹{target_price:.2f}\n"
                    f"• Time: {datetime.now().strftime('%H:%M IST')}"
                )
                triggered.append(msg)
                alerts[key]["triggered"]    = True
                alerts[key]["triggered_at"] = datetime.now().isoformat()
                updated = True
        except Exception as e:
            logger.error(f"Alert check error for {key}: {e}")

    if updated:
        _save_alerts(alerts)

    return triggered


def list_alerts(symbol: Optional[str] = None) -> str:
    """Return formatted list of active alerts."""
    alerts = _load_alerts()
    active = [
        a for a in alerts.values()
        if not a.get("triggered") and (symbol is None or a["symbol"] == symbol)
    ]

    if not active:
        return "📋 No active price alerts."

    lines = ["📋 *Active Price Alerts*\n"]
    for a in active:
        name = STOCK_NAMES.get(a["symbol"], a["symbol"])
        dir_str = "≥" if a["direction"] == "above" else "≤"
        lines.append(f"• {name}: Alert when ₹{dir_str}{a['target_price']:.2f}")

    return "\n".join(lines)


from v4.valuation_runner import run_v4_valuation

def check_v4_smart_alerts(watchlist: list[str]) -> list[str]:
    """
    Check watchlist for V4 Buy/Sell zone triggers.
    Runs every 15 minutes via scheduler.
    """
    triggered = []
    
    for symbol in watchlist:
        try:
            res = run_v4_valuation(symbol)
            if not res.get("success"):
                continue
            
            verdict = res["verdict"]
            cmp = res["cmp"]
            iv = res["intrinsic_value"]
            mos = res["margin_of_safety"]
            ey_verdict = res["yield_verdict"]
            name = STOCK_NAMES.get(symbol, symbol)
            
            # 1. SMART BUY TRIGGER: UNDERVALUED + ATTRACTIVE
            if verdict == "UNDERVALUED" and ey_verdict == "ATTRACTIVE":
                # Only alert if it's deeply undervalued (MoS > 25%)
                if mos >= 25.0:
                    msg = (
                        f"🚀 *V4 BUY ZONE TRIGGERED!*\n"
                        f"💎 *{name}* ({symbol}) is deeply undervalued.\n"
                        f"• Current Price: ₹{cmp:.2f}\n"
                        f"• Intrinsic Value: ₹{iv:.2f}\n"
                        f"• Margin of Safety: {mos:.1f}%\n"
                        f"• Buffett Check: {ey_verdict} ✅\n"
                        f"👉 *Action:* Strong entry opportunity."
                    )
                    triggered.append(msg)
            
            # 2. SMART EXIT TRIGGER: OVERVALUED
            elif verdict == "OVERVALUED" and mos < -15.0:
                msg = (
                    f"⚠️ *V4 EXIT ALERT!*\n"
                    f"🚩 *{name}* ({symbol}) is dangerously expensive.\n"
                    f"• Current Price: ₹{cmp:.2f}\n"
                    f"• Intrinsic Value: ₹{iv:.2f}\n"
                    f"• Premium: {abs(mos):.1f}%\n"
                    f"👉 *Action:* Consider booking profits or reducing exposure."
                )
                triggered.append(msg)
                
        except Exception as e:
            logger.error(f"V4 alert check error for {symbol}: {e}")
            
    return triggered
