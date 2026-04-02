"""
prefilter.py — V3 fast screening stage for /stocktips.

This module is designed to cheaply reduce a large stock universe before any
deeper validation or AI ranking is attempted.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from typing import Any

import pandas as pd

from data.fetchers.yfinance_fetcher import get_historical_data, get_ticker_info

logger = logging.getLogger(__name__)


DEFAULT_PREFILTER_RULES = {
    "min_history_days": 220,
    "min_price": 50.0,
    "min_market_cap_cr": 10000.0,
    "min_avg_traded_value_cr": 25.0,
    "min_avg_volume": 100000.0,
    "min_20d_return_pct": 2.0,
    "min_distance_above_200dma_pct": 2.0,
    "require_above_200dma": True,
    "require_above_50dma": True,
    "require_relative_volume": True,
    "min_relative_volume": 1.1,
}


def _calc_prefilter_metrics(df: pd.DataFrame, info: dict) -> dict[str, float]:
    close = df["Close"]
    volume = df["Volume"].fillna(0)

    current_price = float(close.iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else 0.0
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else 0.0
    close_20_ago = float(close.iloc[-21]) if len(close) >= 21 else current_price
    current_volume = float(volume.iloc[-1] or 0)
    avg_volume_20 = float(volume.iloc[:-1].tail(20).mean() or 0)
    relative_volume = (current_volume / avg_volume_20) if avg_volume_20 > 0 else 0.0
    return_20d_pct = ((current_price / close_20_ago) - 1) * 100 if close_20_ago > 0 else 0.0
    distance_above_200dma_pct = ((current_price / sma200) - 1) * 100 if sma200 > 0 else 0.0

    traded_value_series = (close * volume).tail(20)
    avg_traded_value_cr = float(traded_value_series.mean() or 0) / 1e7

    market_cap = (
        info.get("marketCap")
        or info.get("market_cap")
        or 0
    )
    market_cap_cr = float(market_cap or 0) / 1e7 if float(market_cap or 0) > 0 else 0.0

    return {
        "current_price": current_price,
        "sma50": sma50,
        "sma200": sma200,
        "current_volume": current_volume,
        "avg_volume_20": avg_volume_20,
        "relative_volume": relative_volume,
        "return_20d_pct": return_20d_pct,
        "distance_above_200dma_pct": distance_above_200dma_pct,
        "avg_traded_value_cr": avg_traded_value_cr,
        "market_cap_cr": market_cap_cr,
    }


def run_prefilter_for_symbol(symbol: str, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Run the fast V3 pre-filter on one symbol and return a structured result.
    """
    cfg = dict(DEFAULT_PREFILTER_RULES)
    if rules:
        cfg.update(rules)

    try:
        df = get_historical_data(symbol, period="1y", interval="1d")
        if df is None or df.empty or len(df) < cfg["min_history_days"]:
            return {
                "symbol": symbol,
                "passed": False,
                "reason": "Insufficient daily history for pre-filter",
                "metrics": {},
            }

        if "Close" not in df.columns or "Volume" not in df.columns:
            return {
                "symbol": symbol,
                "passed": False,
                "reason": "Missing OHLCV fields for pre-filter",
                "metrics": {},
            }

        info = get_ticker_info(symbol)
        metrics = _calc_prefilter_metrics(df, info)

        failures = []

        if metrics["current_price"] < cfg["min_price"]:
            failures.append(f"price ₹{metrics['current_price']:.2f} below min ₹{cfg['min_price']:.2f}")

        if cfg["min_market_cap_cr"] > 0 and metrics["market_cap_cr"] > 0 and metrics["market_cap_cr"] < cfg["min_market_cap_cr"]:
            failures.append(
                f"market cap ₹{metrics['market_cap_cr']:.0f}Cr below min ₹{cfg['min_market_cap_cr']:.0f}Cr"
            )

        if metrics["avg_traded_value_cr"] < cfg["min_avg_traded_value_cr"]:
            failures.append(
                f"avg traded value ₹{metrics['avg_traded_value_cr']:.1f}Cr below min ₹{cfg['min_avg_traded_value_cr']:.1f}Cr"
            )

        if metrics["avg_volume_20"] < cfg["min_avg_volume"]:
            failures.append(
                f"avg volume {metrics['avg_volume_20']:.0f} below min {cfg['min_avg_volume']:.0f}"
            )

        if cfg["require_above_200dma"] and metrics["sma200"] > 0 and metrics["current_price"] <= metrics["sma200"]:
            failures.append(
                f"price ₹{metrics['current_price']:.2f} not above 200DMA ₹{metrics['sma200']:.2f}"
            )
        elif (
            cfg["require_above_200dma"]
            and metrics["sma200"] > 0
            and metrics["distance_above_200dma_pct"] < cfg["min_distance_above_200dma_pct"]
        ):
            failures.append(
                f"price only {metrics['distance_above_200dma_pct']:.1f}% above 200DMA "
                f"vs min {cfg['min_distance_above_200dma_pct']:.1f}%"
            )

        if cfg["require_above_50dma"] and metrics["sma50"] > 0 and metrics["current_price"] <= metrics["sma50"]:
            failures.append(
                f"price ₹{metrics['current_price']:.2f} not above 50DMA ₹{metrics['sma50']:.2f}"
            )

        if metrics["return_20d_pct"] < cfg["min_20d_return_pct"]:
            failures.append(
                f"20d return {metrics['return_20d_pct']:.1f}% below min {cfg['min_20d_return_pct']:.1f}%"
            )

        if cfg["require_relative_volume"] and metrics["relative_volume"] < cfg["min_relative_volume"]:
            failures.append(
                f"relative volume {metrics['relative_volume']:.2f}x below min {cfg['min_relative_volume']:.2f}x"
            )

        passed = len(failures) == 0
        if passed:
            reason = (
                f"Pass: price ₹{metrics['current_price']:.2f} above 50/200DMA, "
                f"rel vol {metrics['relative_volume']:.2f}x, "
                f"20d return {metrics['return_20d_pct']:.1f}%, "
                f"avg traded value ₹{metrics['avg_traded_value_cr']:.1f}Cr"
            )
        else:
            reason = "; ".join(failures[:3])

        return {
            "symbol": symbol,
            "passed": passed,
            "reason": reason,
            "metrics": metrics,
        }
    except Exception as e:
        logger.error(f"V3 prefilter error for {symbol}: {e}")
        return {
            "symbol": symbol,
            "passed": False,
            "reason": f"Prefilter error: {e}",
            "metrics": {},
        }


def run_prefilter(
    symbols: list[str],
    rules: dict[str, Any] | None = None,
    max_workers: int = 8,
) -> dict[str, Any]:
    """
    Run the V3 pre-filter across a universe and return pass/fail groups.
    """
    universe = [symbol for symbol in symbols if symbol]
    if not universe:
        return {
            "total": 0,
            "passed": [],
            "failed": [],
            "pass_rate": 0.0,
        }

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(run_prefilter_for_symbol, symbol, rules): symbol
            for symbol in universe
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item["symbol"])
    passed = [item for item in results if item["passed"]]
    failed = [item for item in results if not item["passed"]]

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round((len(passed) / len(results)) * 100, 2) if results else 0.0,
        "rules": dict(DEFAULT_PREFILTER_RULES, **(rules or {})),
    }
