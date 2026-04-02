"""
scorer.py — Combines all 21 check results into a final score, grade and summary.
"""

import logging
from config import (
    SIGNAL_WEIGHTS, GRADE_SCALE, CHECK_WEIGHTS,
    CHECK_BUCKETS, CHECK_SOURCES, CHECK_BASE_CONFIDENCE, CRITICAL_CHECKS,
)

logger = logging.getLogger(__name__)
MARKET_SENSITIVE_CONTEXT_CHECKS = {16, 17, 18, 19, 20}


def _normalize_verdict(verdict: str) -> str:
    text = (verdict or "HOLD").upper().strip()
    mapping = {
        "A+": "STRONG BUY",
        "A": "BUY",
        "B+": "BUY",
        "B": "HOLD",
        "C": "HOLD",
        "D": "SELL",
        "MODERATE BUY": "BUY",
        "WATCHLIST": "HOLD",
        "NEUTRAL": "HOLD",
        "AVOID": "SELL",
    }
    return mapping.get(text, text if text in {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"} else "HOLD")


def _grade_from_verdict(verdict: str, score: float, average_confidence: float) -> str:
    if verdict == "STRONG BUY":
        return "A+"
    if verdict == "BUY":
        return "A" if average_confidence >= 0.68 and score >= 8 else "B+"
    if verdict == "HOLD":
        return "B" if score >= 1 else "C"
    return "D"


def apply_verdict_guardrails(verdict: str, scoring: dict) -> tuple[str, str]:
    """
    Clamp verdict strength so strong calls require strong core evidence,
    usable confidence, and low critical data loss.
    """
    normalized = _normalize_verdict(verdict)
    average_confidence = float(scoring.get("average_confidence", 0) or 0)
    core_score = float(scoring.get("core_score", 0) or 0)
    context_score = float(scoring.get("context_score", 0) or 0)
    critical_unavailable = int(scoring.get("critical_unavailable", 0) or 0)
    unavailable_checks = int(scoring.get("unavailable_checks", 0) or 0)
    bullish_count = int(scoring.get("bullish_count", 0) or 0)
    bearish_count = int(scoring.get("bearish_count", 0) or 0)

    reason = "Verdict aligned with core evidence"

    if normalized in {"BUY", "STRONG BUY"}:
        if average_confidence < 0.58 or critical_unavailable > 0 or core_score < 4:
            normalized = "HOLD"
            reason = "Downgraded because confidence/core evidence is not strong enough for a buy call"
        elif unavailable_checks >= 6:
            normalized = "HOLD"
            reason = "Downgraded because too many checks are unavailable"
        elif context_score <= -4 and average_confidence < 0.68:
            normalized = "HOLD"
            reason = "Downgraded because macro/context headwinds are too strong for a confident buy"
        elif normalized == "STRONG BUY" and (
            average_confidence < 0.72 or core_score < 8 or bullish_count < bearish_count + 4
        ):
            normalized = "BUY"
            reason = "Downgraded because the setup is positive but not strong enough for a strong buy"
        elif normalized == "BUY" and (average_confidence < 0.62 or core_score < 5):
            normalized = "HOLD"
            reason = "Downgraded because the setup is watchable but not buy-grade yet"

    elif normalized in {"SELL", "STRONG SELL"}:
        if core_score >= 4 and bullish_count >= bearish_count:
            normalized = "HOLD"
            reason = "Downgraded because core stock evidence is not bearish enough for a sell call"
        elif normalized == "STRONG SELL" and (average_confidence < 0.68 or bearish_count < bullish_count + 4):
            normalized = "SELL"
            reason = "Downgraded because the setup is negative but not strong enough for a strong sell"
        elif average_confidence < 0.5 and critical_unavailable > 0:
            normalized = "HOLD"
            reason = "Downgraded because weak confidence and missing critical checks make the sell call unreliable"

    return normalized, reason


def _signal_availability(signal: str) -> str:
    if signal == "UNAVAILABLE":
        return "unavailable"
    if signal == "INFO":
        return "context_only"
    return "available"


def _check_confidence(check_number: int, signal: str) -> float:
    base = CHECK_BASE_CONFIDENCE.get(check_number, 0.5)
    if signal == "UNAVAILABLE":
        return 0.0
    if signal == "INFO":
        return round(min(base, 0.35), 2)
    return round(base, 2)


def enrich_checks(all_checks: list[dict]) -> list[dict]:
    """Attach source, bucket, availability, and confidence metadata to each check."""
    enriched = []
    for check in all_checks:
        check_number = check.get("check_number")
        signal = check.get("signal", "NEUTRAL")
        item = dict(check)
        item["bucket"] = CHECK_BUCKETS.get(check_number, "core")
        item["source"] = CHECK_SOURCES.get(check_number, "Unknown")
        item["availability"] = _signal_availability(signal)
        item["confidence"] = _check_confidence(check_number, signal)
        item["is_critical"] = check_number in CRITICAL_CHECKS
        item["is_suppressed_context"] = (
            check_number in MARKET_SENSITIVE_CONTEXT_CHECKS and signal in {"UNAVAILABLE", "INFO"}
        )
        enriched.append(item)
    return enriched


def score_results(all_checks: list[dict]) -> dict:
    """
    Score all 21 check results and return a summary dict.
    Returns:
        {
            score: int,
            grade: str,
            verdict: str,
            bullish_count: int,
            bearish_count: int,
            neutral_count: int,
            max_possible: int,
        }
    """
    score         = 0
    core_score    = 0
    context_score = 0
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    available_checks = 0
    unavailable_checks = 0
    confidence_total = 0.0
    critical_unavailable = 0

    for check in all_checks:
        check_number = check.get("check_number")
        signal = check.get("signal", "NEUTRAL")
        base_weight = SIGNAL_WEIGHTS.get(signal, 0)
        check_weight = CHECK_WEIGHTS.get(check_number, 1.0)
        weight = base_weight * check_weight
        bucket = check.get("bucket", CHECK_BUCKETS.get(check_number, "core"))
        confidence = float(check.get("confidence", _check_confidence(check_number, signal)))
        availability = check.get("availability", _signal_availability(signal))
        score += weight

        if bucket == "core":
            core_score += weight
        else:
            context_score += weight

        confidence_total += confidence
        if availability == "unavailable":
            unavailable_checks += 1
            if check_number in CRITICAL_CHECKS:
                critical_unavailable += 1
        else:
            available_checks += 1

        if weight > 0:
            bullish_count += 1
        elif weight < 0:
            bearish_count += 1
        else:
            neutral_count += 1

    # Determine grade and verdict
    raw_grade   = "D"
    raw_verdict = "AVOID"
    for lo, hi, g, v in GRADE_SCALE:
        if lo <= score <= hi:
            raw_grade   = g
            raw_verdict = v
            break

    provisional = {
        "score": round(score, 2),
        "core_score": round(core_score, 2),
        "context_score": round(context_score, 2),
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "available_checks": available_checks,
        "unavailable_checks": unavailable_checks,
        "critical_unavailable": critical_unavailable,
        "average_confidence": round(confidence_total / len(all_checks), 2) if all_checks else 0.0,
    }
    verdict, verdict_reason = apply_verdict_guardrails(raw_verdict, provisional)
    grade = _grade_from_verdict(verdict, provisional["score"], provisional["average_confidence"])

    return {
        "score":          provisional["score"],
        "core_score":     provisional["core_score"],
        "context_score":  provisional["context_score"],
        "grade":          grade,
        "verdict":        verdict,
        "raw_grade":      raw_grade,
        "raw_verdict":    raw_verdict,
        "verdict_reason": verdict_reason,
        "bullish_count":  bullish_count,
        "bearish_count":  bearish_count,
        "neutral_count":  neutral_count,
        "available_checks": available_checks,
        "unavailable_checks": unavailable_checks,
        "critical_unavailable": critical_unavailable,
        "average_confidence": provisional["average_confidence"],
        "total_checks":   len(all_checks),
    }


def format_conditions_for_ai(all_checks: list[dict]) -> str:
    """
    Format the scored core checks into a readable text block for the Groq AI prompt.
    """
    lines = []
    current_category = None

    for check in sorted(all_checks, key=lambda x: x["check_number"]):
        cat = check["category"]
        if cat != current_category:
            current_category = cat
            lines.append(f"\n── {cat} ──")

        suffix = " [suppressed context]" if check.get("is_suppressed_context") else ""
        lines.append(
            f"  [{check['check_number']:2d}] {check['name']:<28} "
            f"| {check['signal']:<25} | conf {check.get('confidence', 0):.2f}{suffix} | {check['detail']}"
        )

    return "\n".join(lines)


def run_full_analysis(
    stock_symbol: str,
    df,
    df_1h,
    ticker_info: dict,
    financials,
    balance_sheet,
    fii_data: dict,
) -> dict:
    """
    Orchestrate the scored 21-check core plus separate non-scoring additional signals.
    Returns full analysis dict with all results and score.
    """
    from analysis.technical        import run_all_technical_checks, run_additional_technical_signals
    from analysis.fundamental      import run_all_fundamental_checks
    from analysis.macro            import run_all_macro_checks, run_additional_macro_signals
    from analysis.secret_strategies import run_all_secret_checks

    tech_results    = run_all_technical_checks(df, df_1h, ticker_info)
    additional_signals = (
        run_additional_technical_signals(df, ticker_info, stock_symbol)
        + run_additional_macro_signals(stock_symbol)
    )
    fund_results    = run_all_fundamental_checks(stock_symbol, ticker_info, financials, balance_sheet)
    macro_results   = run_all_macro_checks(stock_symbol, fii_data)
    secret_results  = run_all_secret_checks(stock_symbol, ticker_info, fii_data)

    all_checks = enrich_checks(tech_results + fund_results + macro_results + secret_results)
    scoring    = score_results(all_checks)

    return {
        "symbol":             stock_symbol,
        "all_checks":         all_checks,
        "additional_signals": additional_signals,
        "scoring":            scoring,
    }
