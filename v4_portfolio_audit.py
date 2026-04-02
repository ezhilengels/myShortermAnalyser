
import sys
import os
import logging
from typing import Dict, Any

# Ensure we can import from the root
sys.path.append(os.getcwd())

from v4.valuation_runner import run_v4_valuation
from config import MY_PORTFOLIO, STOCK_NAMES

def run_portfolio_audit():
    print("💼 --- STRATEGY V4 PORTFOLIO AUDIT --- 💼")
    print(f"Auditing {len(MY_PORTFOLIO)} holdings...\n")
    
    total_value = 0.0
    
    for symbol in MY_PORTFOLIO:
        res = run_v4_valuation(symbol)
        name = STOCK_NAMES.get(symbol, symbol)
        
        if not res.get("success"):
            print(f"❌ {name}: Valuation unavailable ({res.get('reason')})")
            continue
            
        cmp = res["cmp"]
        iv = res["iv"]
        mos = res["margin_of_safety"]
        verdict = res["verdict"]
        ey_verdict = res["yield_verdict"]
        
        # Recommendation Logic
        if verdict == "UNDERVALUED" and ey_verdict == "ATTRACTIVE":
            action = "✅ HOLD / ACCUMULATE (Strong Fundamentals)"
            status = "🟢"
        elif verdict == "OVERVALUED" and mos < -15:
            action = "⚠️ EXIT / REDUCE (Dangerously Expensive)"
            status = "🔴"
        elif verdict == "OVERVALUED":
            action = "🟡 HOLD / MONITOR (Trading at Premium)"
            status = "🟡"
        else:
            action = "🔵 HOLD (Fair Value)"
            status = "🔵"
            
        print(f"{status} {name:<12} | CMP: ₹{cmp:>8.2f} | IV: ₹{iv:>8.2f} | MoS: {mos:>+6.1f}% | {action}")

if __name__ == "__main__":
    run_portfolio_audit()
