"""
validation_runner.py — Batch validation helper for the stock bot.

Runs analysis across the configured watchlist and exports a compact audit
summary to logs/ as both JSON and CSV.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime

import pytz

from bot.telegram_bot import analyse_single_stock
from config import WATCHLIST, STOCK_NAMES

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
BENCHMARK_PATH = "benchmarks/core_expectations.json"
VERDICT_ORDER = {
    "STRONG SELL": 0,
    "SELL": 1,
    "HOLD": 2,
    "BUY": 3,
    "STRONG BUY": 4,
}


def _top_checks(all_checks: list[dict], positive: bool, limit: int = 3) -> list[str]:
    filtered = []
    for check in all_checks:
        signal = check.get("signal", "NEUTRAL")
        if signal in ("UNAVAILABLE", "INFO", "NEUTRAL"):
            continue

        weight = 0
        if signal in (
            "STRONG_BUY", "STRONG", "BULLISH", "UPTREND", "OPPORTUNITY",
            "OVERSOLD_BUY", "UNDERVALUED", "CONTRARIAN_BUY", "OPERATOR_ACCUMULATION",
            "STRONGLY_LONG", "SLIGHTLY_LONG", "STRONG_OPPORTUNITY",
            "STRONG_CONFIDENCE", "POSITIVE", "GOOD", "EXCELLENT",
        ):
            weight = 1
        elif signal in (
            "GREED", "CAUTION", "BEARISH", "DOWNTREND", "EXPENSIVE",
            "OVERBOUGHT", "SLIGHTLY_BEARISH", "FEAR", "HIGH_RISK",
            "STRONG_SELL", "CONTRARIAN_SELL", "STRONGLY_SHORT",
            "SLIGHTLY_SHORT", "RED_FLAG", "WEAK",
        ):
            weight = -1

        if positive and weight > 0:
            filtered.append(check["name"])
        elif not positive and weight < 0:
            filtered.append(check["name"])

    return filtered[:limit]


def run_watchlist_validation() -> dict:
    timestamp = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    json_path = f"logs/validation_{timestamp}.json"
    csv_path = f"logs/validation_{timestamp}.csv"
    review_csv_path = f"logs/validation_review_{timestamp}.csv"

    rows = []
    for symbol in WATCHLIST:
        logger.info(f"Validating {symbol}...")
        result, decision, price = analyse_single_stock(symbol)
        scoring = result["scoring"]
        checks = result["all_checks"]

        row = {
            "symbol": symbol,
            "name": STOCK_NAMES.get(symbol, symbol.replace(".NS", "")),
            "price": round(price, 2),
            "grade": scoring["grade"],
            "score": scoring["score"],
            "core_score": scoring.get("core_score", 0),
            "context_score": scoring.get("context_score", 0),
            "average_confidence": scoring.get("average_confidence", 0),
            "available_checks": scoring.get("available_checks", 0),
            "unavailable_checks": scoring.get("unavailable_checks", 0),
            "critical_unavailable": scoring.get("critical_unavailable", 0),
            "bullish_count": scoring.get("bullish_count", 0),
            "bearish_count": scoring.get("bearish_count", 0),
            "neutral_count": scoring.get("neutral_count", 0),
            "rule_verdict": scoring.get("verdict", "NEUTRAL"),
            "ai_verdict": decision.get("verdict", "HOLD"),
            "ai_confidence": decision.get("confidence", 5),
            "top_positive_checks": _top_checks(checks, positive=True),
            "top_negative_checks": _top_checks(checks, positive=False),
            "all_checks_detail": checks,
        }
        rows.append(row)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(IST).isoformat(),
                "rows": rows,
            },
            f,
            indent=2,
        )

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "symbol", "name", "price", "grade", "score", "core_score",
                "context_score", "average_confidence", "available_checks",
                "unavailable_checks", "critical_unavailable", "bullish_count",
                "bearish_count", "neutral_count", "rule_verdict", "ai_verdict",
                "ai_confidence", "top_positive_checks", "top_negative_checks",
            ],
        )
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["top_positive_checks"] = " | ".join(row["top_positive_checks"])
            csv_row["top_negative_checks"] = " | ".join(row["top_negative_checks"])
            csv_row.pop("all_checks_detail", None)
            writer.writerow(csv_row)

    with open(review_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "symbol",
                "name",
                "price",
                "grade",
                "score",
                "core_score",
                "context_score",
                "average_confidence",
                "available_checks",
                "unavailable_checks",
                "critical_unavailable",
                "bullish_count",
                "bearish_count",
                "neutral_count",
                "rule_verdict",
                "ai_verdict",
                "ai_confidence",
                "top_positive_checks",
                "top_negative_checks",
                "your_verdict",
                "your_confidence",
                "agree_with_bot",
                "reason_tag",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "date": datetime.now(IST).strftime("%Y-%m-%d"),
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "price": row["price"],
                    "grade": row["grade"],
                    "score": row["score"],
                    "core_score": row["core_score"],
                    "context_score": row["context_score"],
                    "average_confidence": row["average_confidence"],
                    "available_checks": row["available_checks"],
                    "unavailable_checks": row["unavailable_checks"],
                    "critical_unavailable": row["critical_unavailable"],
                    "bullish_count": row["bullish_count"],
                    "bearish_count": row["bearish_count"],
                    "neutral_count": row["neutral_count"],
                    "rule_verdict": row["rule_verdict"],
                    "ai_verdict": row["ai_verdict"],
                    "ai_confidence": row["ai_confidence"],
                    "top_positive_checks": " | ".join(row["top_positive_checks"]),
                    "top_negative_checks": " | ".join(row["top_negative_checks"]),
                    "your_verdict": "",
                    "your_confidence": "",
                    "agree_with_bot": "",
                    "reason_tag": "",
                    "notes": "",
                }
            )

    return {
        "json_path": json_path,
        "csv_path": csv_path,
        "review_csv_path": review_csv_path,
        "rows": rows,
    }


def build_validation_review(rows: list[dict]) -> dict:
    """Group rows into review buckets that are easier to scan than raw exports."""
    high_confidence_buys = []
    low_confidence_buys = []
    blocked_by_data = []
    bearish_or_avoid = []

    for row in rows:
        ai_verdict = (row.get("ai_verdict") or "").upper()
        avg_conf = float(row.get("average_confidence", 0) or 0)
        critical_unavailable = int(row.get("critical_unavailable", 0) or 0)
        unavailable_checks = int(row.get("unavailable_checks", 0) or 0)

        if critical_unavailable >= 2 or unavailable_checks >= 6:
            blocked_by_data.append(row)
        elif "BUY" in ai_verdict and avg_conf >= 0.65 and critical_unavailable == 0:
            high_confidence_buys.append(row)
        elif "BUY" in ai_verdict:
            low_confidence_buys.append(row)
        else:
            bearish_or_avoid.append(row)

    return {
        "high_confidence_buys": high_confidence_buys,
        "low_confidence_buys": low_confidence_buys,
        "blocked_by_data": blocked_by_data,
        "bearish_or_avoid": bearish_or_avoid,
    }


def evaluate_priority4_validation(rows: list[dict]) -> dict:
    """
    Evaluate whether the redesigned human-like signal checks have seen enough live
    evidence to count Priority 4 as validated.
    """
    target_checks = {16, 17, 18, 20}
    reviewed_symbols = 0
    symbols_with_live_derivatives = 0
    details = []

    for row in rows:
        checks = row.get("all_checks_detail", [])
        if not checks:
            continue

        reviewed_symbols += 1
        target = [c for c in checks if c.get("check_number") in target_checks]
        available_target = [
            c for c in target
            if c.get("availability") == "available"
        ]

        if len(available_target) >= 2:
            symbols_with_live_derivatives += 1

        details.append(
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "available_priority4_checks": [c["name"] for c in available_target],
                "unavailable_priority4_checks": [
                    c["name"] for c in target if c.get("availability") != "available"
                ],
            }
        )

    passed = symbols_with_live_derivatives >= 2
    status = (
        "PASSED"
        if passed else
        "PENDING_OPEN_MARKET_DATA"
    )

    return {
        "status": status,
        "passed": passed,
        "reviewed_symbols": reviewed_symbols,
        "symbols_with_live_derivatives": symbols_with_live_derivatives,
        "details": details,
    }


def _load_benchmarks(path: str = BENCHMARK_PATH) -> dict:
    if not os.path.exists(path):
        return {"as_of": "", "description": "", "cases": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_verdict(verdict: str) -> str:
    text = (verdict or "HOLD").upper().strip()
    aliases = {
        "WATCHLIST": "HOLD",
        "NEUTRAL": "HOLD",
        "AVOID": "SELL",
        "MODERATE BUY": "BUY",
    }
    return aliases.get(text, text)


def _verdict_distance(actual: str, expected: str) -> int:
    actual_idx = VERDICT_ORDER.get(_normalize_verdict(actual), 2)
    expected_idx = VERDICT_ORDER.get(_normalize_verdict(expected), 2)
    return abs(actual_idx - expected_idx)


def _judge_benchmark_case(case: dict, row: dict) -> dict:
    expected_rule = case.get("expected_rule_verdict", "HOLD")
    expected_ai = case.get("expected_ai_verdict", expected_rule)
    rule_distance = _verdict_distance(row.get("rule_verdict", "HOLD"), expected_rule)
    ai_distance = _verdict_distance(row.get("ai_verdict", "HOLD"), expected_ai)

    checks = []
    if "min_core_score" in case:
        checks.append(float(row.get("core_score", 0) or 0) >= float(case["min_core_score"]))
    if "max_core_score" in case:
        checks.append(float(row.get("core_score", 0) or 0) <= float(case["max_core_score"]))
    if "min_average_confidence" in case:
        checks.append(float(row.get("average_confidence", 0) or 0) >= float(case["min_average_confidence"]))
    if "max_critical_unavailable" in case:
        checks.append(int(row.get("critical_unavailable", 0) or 0) <= int(case["max_critical_unavailable"]))

    metric_pass = all(checks) if checks else True
    exact_match = rule_distance == 0 and ai_distance == 0 and metric_pass
    close_match = rule_distance <= 1 and ai_distance <= 1 and metric_pass

    if exact_match:
        status = "PASS"
    elif close_match:
        status = "CLOSE"
    else:
        status = "MISS"

    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "status": status,
        "expected_rule_verdict": expected_rule,
        "actual_rule_verdict": row.get("rule_verdict", "HOLD"),
        "expected_ai_verdict": expected_ai,
        "actual_ai_verdict": row.get("ai_verdict", "HOLD"),
        "core_score": row.get("core_score", 0),
        "average_confidence": row.get("average_confidence", 0),
        "critical_unavailable": row.get("critical_unavailable", 0),
        "notes": case.get("notes", ""),
    }


def run_benchmark_validation(path: str = BENCHMARK_PATH) -> dict:
    """
    Run analysis against a curated expectation file and report how closely the
    bot agrees with the stored human baseline.
    """
    benchmark = _load_benchmarks(path)
    timestamp = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    json_path = f"logs/benchmark_{timestamp}.json"

    cases = benchmark.get("cases", [])
    if not cases:
        result = {
            "generated_at": datetime.now(IST).isoformat(),
            "status": "NO_CASES",
            "path": path,
            "results": [],
            "summary": {"pass": 0, "close": 0, "miss": 0, "accuracy": 0.0},
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return {"json_path": json_path, **result}

    indexed_rows = {}
    for case in cases:
        symbol = case["symbol"]
        logger.info(f"Benchmarking {symbol}...")
        result, decision, price = analyse_single_stock(symbol)
        scoring = result["scoring"]
        indexed_rows[symbol] = {
            "symbol": symbol,
            "name": case.get("name") or STOCK_NAMES.get(symbol, symbol.replace(".NS", "")),
            "price": round(price, 2),
            "rule_verdict": scoring.get("verdict", "HOLD"),
            "ai_verdict": decision.get("verdict", "HOLD"),
            "core_score": scoring.get("core_score", 0),
            "average_confidence": scoring.get("average_confidence", 0),
            "critical_unavailable": scoring.get("critical_unavailable", 0),
        }

    results = [_judge_benchmark_case(case, indexed_rows[case["symbol"]]) for case in cases]
    pass_count = sum(1 for row in results if row["status"] == "PASS")
    close_count = sum(1 for row in results if row["status"] == "CLOSE")
    miss_count = sum(1 for row in results if row["status"] == "MISS")
    weighted_hits = pass_count + (0.5 * close_count)
    accuracy = round((weighted_hits / len(results)) * 100, 1) if results else 0.0

    payload = {
        "generated_at": datetime.now(IST).isoformat(),
        "status": "OK",
        "benchmark_as_of": benchmark.get("as_of", ""),
        "description": benchmark.get("description", ""),
        "path": path,
        "results": results,
        "summary": {
            "pass": pass_count,
            "close": close_count,
            "miss": miss_count,
            "accuracy": accuracy,
            "total_cases": len(results),
        },
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return {"json_path": json_path, **payload}
