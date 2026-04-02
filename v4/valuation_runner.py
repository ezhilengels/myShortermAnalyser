"""
v4/valuation_runner.py — Entry point to run Strategy V4 intrinsic valuations.
Combines engine logic and gathered data to produce a valuation report.
"""

import sys
import os
import logging
from typing import Dict, Any

# Ensure we can import from the root
sys.path.append(os.getcwd())

from v4.valuation_engine import (
    calculate_graham_iv, calculate_dcf_iv, calculate_lynch_iv,
    calculate_buffett_iv, calculate_epv_iv, calculate_ddm_iv,
    get_buffett_sanity_check, select_best_model
)
from v4.valuation_data import gather_valuation_data

def run_v4_valuation(symbol: str) -> Dict[str, Any]:
    """
    Run the full Strategy V4 multi-model valuation on a single stock.
    """
    data = gather_valuation_data(symbol)
    
    if not data["valid"]:
        return {
            "symbol": symbol,
            "success": False,
            "reason": f"Insufficient data for valuation: {', '.join(data.get('missing_fields', []))}",
            "errors": data.get("errors", [])
        }

    # Calculate all models
    graham_iv = calculate_graham_iv(data["eps_ttm"], data["growth_5y"])
    dcf_iv = calculate_dcf_iv(data["fcf"], data["growth_5y"])
    lynch_iv = calculate_lynch_iv(data["eps_ttm"], data["growth_5y"])
    buffett_iv = calculate_buffett_iv(data["eps_ttm"], data["growth_5y"]) # Simplified for test
    ddm_iv = calculate_ddm_iv(data["dividend_rate"], data["growth_5y"])
    
    # Selection and verdict
    best_model_name = select_best_model(data["sector"], data["industry"])
    iv_map = {
        "GRAHAM": graham_iv,
        "DCF": dcf_iv,
        "LYNCH": lynch_iv,
        "BUFFETT": buffett_iv,
        "DDM": ddm_iv
    }
    
    final_iv = iv_map.get(best_model_name, 0.0)
    cmp = data["price"]
    
    mos = ((final_iv - cmp) / final_iv * 100) if final_iv > 0 else 0.0
    
    if final_iv <= 0:
        verdict = "UNAVAILABLE"
    elif mos >= 30:
        verdict = "UNDERVALUED"
    elif mos >= 0:
        verdict = "FAIRLY_VALUED"
    else:
        verdict = "OVERVALUED"
        
    ey_yield, ey_verdict = get_buffett_sanity_check(data["eps_ttm"], cmp)
    
    return {
        "symbol": symbol,
        "success": True,
        "cmp": cmp,
        "intrinsic_value": final_iv,
        "verdict": verdict,
        "margin_of_safety": mos,
        "model_used": best_model_name,
        "sector": data["sector"],
        "earnings_yield": ey_yield,
        "yield_verdict": ey_verdict,
        "models": {
            "Graham": graham_iv,
            "DCF": dcf_iv,
            "Lynch": lynch_iv,
            "Buffett": buffett_iv,
            "DDM": ddm_iv
        }
    }

def print_v4_report(result: Dict[str, Any]):
    if not result.get("success"):
        print(f"❌ {result.get('symbol')}: {result.get('reason')}")
        return

    print(f"\n--- Strategy V4 Intrinsic Valuation: {result['symbol']} ---")
    print(f"Sector: {result['sector']}")
    print(f"Current Market Price: ₹{result['cmp']:.2f}")
    print(f"Estimated Intrinsic Value: ₹{result['intrinsic_value']:.2f} ({result['model_used']} model)")
    
    mos = result['margin_of_safety']
    print(f"Verdict: {result['verdict']} | Margin of Safety: {mos:+.1f}%")
    
    print(f"Buffett Check: Earnings Yield {result['earnings_yield']:.2f}% | Bond Yield (7.05%) → {result['yield_verdict']}")
    
    print("\nModel Comparisons:")
    for m, val in result['models'].items():
        if val > 0:
            status = "✅" if val > result['cmp'] else "⚠️"
            print(f"  {status} {m:<10}: ₹{val:.2f}")
        else:
            print(f"  ❌ {m:<10}: DATA NOT VALID OR MISSING")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 v4/valuation_runner.py SYMBOL1 SYMBOL2 ...")
    else:
        for sym in sys.argv[1:]:
            res = run_v4_valuation(sym)
            print_v4_report(res)
