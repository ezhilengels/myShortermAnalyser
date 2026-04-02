"""
groq_engine.py — Groq AI Decision Engine.
Feeds all 21 condition results to llama3-70b-8192 and parses structured output:
  - Verdict (STRONG BUY / BUY / HOLD / SELL / STRONG SELL)
  - Short-term trade: Entry, Target, Stop Loss
  - Medium-term trade: Entry, Target, Stop Loss
  - Confidence score (1–10)
  - Key Risks
  - Key Catalysts
  - Plain English summary
"""

import json
import logging
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE
from analysis.scorer import format_conditions_for_ai, apply_verdict_guardrails

logger = logging.getLogger(__name__)

_groq_client = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def get_groq_decision(
    stock_symbol: str,
    stock_name: str,
    all_checks: list[dict],
    scoring: dict,
    current_price: float,
    market_context: dict,
    additional_signals: list[dict] = None,
) -> dict:
    """
    Send all core and additional signals to Groq AI and return a structured decision.
    """
    try:
        client = get_groq_client()
        conditions_text = format_conditions_for_ai(all_checks)
        
        additional_text = ""
        if additional_signals:
            additional_text = "\nADDITIONAL SIGNALS (Non-Scoring):\n"
            for s in additional_signals:
                additional_text += f"- {s['name']}: {s['signal']} | {s['detail']}\n"

        india_mood  = market_context.get("india_market_mood", "Unknown")
        fii_summary = market_context.get("fii_summary", "Unknown")
        vix         = market_context.get("vix", 0)
        
        total_checks = scoring.get("total_checks", 21)

        prompt = f"""You are an expert Indian stock market analyst with 20 years experience trading NSE/BSE markets. You use both technical analysis and fundamental analysis, as well as understanding of FII/DII behaviour, option chain signals, and macro trends.

STOCK: {stock_name} ({stock_symbol})
CURRENT PRICE: ₹{current_price:.2f}
{total_checks}-CONDITION SCORECARD (Score: {scoring['score']} | Grade: {scoring['grade']}):
{conditions_text}
{additional_text}

MARKET CONTEXT:
- India Market: {india_mood}
- FII Activity: {fii_summary}
- India VIX: {vix:.1f}
- Core score: {scoring.get('core_score', 0)}
- Context score: {scoring.get('context_score', 0)}
- Average check confidence: {scoring.get('average_confidence', 0):.2f}
- Bullish signals: {scoring['bullish_count']}/{total_checks}
- Bearish signals: {scoring['bearish_count']}/{total_checks}
- Neutral signals: {scoring['neutral_count']}/{total_checks}
- Unavailable checks: {scoring.get('unavailable_checks', 0)}/{total_checks}

Based on this complete multi-factor analysis, provide your decision in the following JSON format ONLY:
...

Based on this complete 21-condition analysis, provide your decision in the following JSON format ONLY (no other text outside JSON):

Important guardrails:
- Only core checks should drive BUY/SELL conviction.
- Checks marked as "[suppressed context]" must not upgrade or downgrade the verdict.
- If context signals are unavailable, stale, or weak, keep the verdict conservative.

{{
  "verdict": "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
  "short_term": {{
    "duration": "1-3 days",
    "entry": "₹XXX-XXX",
    "target": "₹XXX",
    "stop_loss": "₹XXX",
    "risk_reward": "1:X"
  }},
  "medium_term": {{
    "duration": "1-3 months",
    "entry": "₹XXX-XXX",
    "target": "₹XXX",
    "stop_loss": "₹XXX",
    "risk_reward": "1:X"
  }},
  "confidence": 7,
  "key_risks": ["Risk 1 in one line", "Risk 2 in one line"],
  "key_catalysts": ["Catalyst 1 in one line", "Catalyst 2 in one line"],
  "summary": "2-3 line plain English summary for a retail trader. Be honest and actionable."
}}"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=GROQ_TEMPERATURE,
            max_tokens=GROQ_MAX_TOKENS,
        )

        raw_content = response.choices[0].message.content
        return _parse_groq_response(raw_content, current_price, scoring)

    except Exception as e:
        logger.error(f"Groq AI error for {stock_symbol}: {e}")
        return _fallback_decision(scoring, current_price)


def _parse_groq_response(raw: str, current_price: float, scoring: dict) -> dict:
    """Extract and parse JSON from Groq's response."""
    try:
        # Find JSON block in response
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        json_str = raw[start:end]
        decision = json.loads(json_str)

        # Ensure required fields exist
        decision.setdefault("verdict",      "HOLD")
        decision.setdefault("confidence",   5)
        decision.setdefault("key_risks",    ["Data insufficient"])
        decision.setdefault("key_catalysts", ["Monitor closely"])
        decision.setdefault("summary",      "Analysis complete. Review conditions carefully.")

        # Ensure short/medium term dicts exist
        for term in ["short_term", "medium_term"]:
            if term not in decision:
                decision[term] = {
                    "duration":   "N/A",
                    "entry":      f"₹{current_price:.2f}",
                    "target":     "N/A",
                    "stop_loss":  "N/A",
                    "risk_reward": "N/A",
                }

        decision["verdict"], verdict_reason = apply_verdict_guardrails(decision.get("verdict", "HOLD"), scoring)
        summary = decision.get("summary", "")
        if verdict_reason and "aligned with core evidence" not in verdict_reason.lower():
            decision["summary"] = f"{summary} Guardrail: {verdict_reason}.".strip()

        return decision

    except Exception as e:
        logger.error(f"Groq response parse error: {e}. Raw: {raw[:200]}")
        return _fallback_decision_from_raw(raw, current_price, scoring)


def _fallback_decision(scoring: dict, current_price: float) -> dict:
    """Return a basic decision based on score when Groq AI is unavailable."""
    verdict = scoring.get("verdict", "HOLD")
    score   = scoring.get("core_score", scoring.get("score", 0))
    critical_unavailable = scoring.get("critical_unavailable", 0)
    verdict, verdict_reason = apply_verdict_guardrails(verdict, scoring)

    # Rough entry/target/SL based on score
    if score > 10:
        target_pct = 0.07
        sl_pct     = 0.04
    elif score > 5:
        target_pct = 0.05
        sl_pct     = 0.03
    else:
        target_pct = 0.03
        sl_pct     = 0.05

    target = current_price * (1 + target_pct)
    sl     = current_price * (1 - sl_pct)

    return {
        "verdict":    verdict,
        "short_term": {
            "duration":   "1-3 days",
            "entry":      f"₹{current_price:.2f}",
            "target":     f"₹{target:.2f}",
            "stop_loss":  f"₹{sl:.2f}",
            "risk_reward": f"1:{round(target_pct/sl_pct, 1)}",
        },
        "medium_term": {
            "duration":   "1-3 months",
            "entry":      f"₹{current_price:.2f}",
            "target":     f"₹{current_price * 1.15:.2f}",
            "stop_loss":  f"₹{current_price * 0.90:.2f}",
            "risk_reward": "1:1.5",
        },
        "confidence":     5,
        "key_risks":      ["Groq AI unavailable — AI analysis not available"],
        "key_catalysts":  ["Check manually for catalysts"],
        "summary":        f"Score-based decision: {verdict}. {verdict_reason}. Groq AI was unavailable. "
                          "Review 21 conditions manually.",
    }


def _fallback_decision_from_raw(raw: str, current_price: float, scoring: dict) -> dict:
    """Minimal fallback when JSON parsing fails."""
    verdict = "HOLD"
    for v in ["STRONG BUY", "BUY", "STRONG SELL", "SELL", "HOLD"]:
        if v in raw.upper():
            verdict = v
            break
    verdict, verdict_reason = apply_verdict_guardrails(verdict, scoring)

    return {
        "verdict":    verdict,
        "short_term": {"duration": "1-3 days", "entry": f"₹{current_price:.2f}",
                       "target": "N/A", "stop_loss": "N/A", "risk_reward": "N/A"},
        "medium_term": {"duration": "1-3 months", "entry": f"₹{current_price:.2f}",
                        "target": "N/A", "stop_loss": "N/A", "risk_reward": "N/A"},
        "confidence":     5,
        "key_risks":      ["Could not parse AI response"],
        "key_catalysts":  ["Manual review required"],
        "summary":        f"AI response parsing failed. {verdict_reason}. Please check logs.",
    }
