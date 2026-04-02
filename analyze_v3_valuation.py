
import sys
import os
import logging

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from v3.universe_loader import load_universe
from v3.ranker import run_v3_validation

logging.basicConfig(level=logging.ERROR)

def analyze_valuation_on_universe(universe_name="nifty50"):
    symbols = load_universe(universe_name)
    print(f"Analyzing Valuation for {len(symbols)} stocks in {universe_name}...")
    
    stats = {
        "UNDERVALUED": 0,
        "FAIRLY_VALUED": 0,
        "CAUTION": 0,
        "EXPENSIVE": 0,
        "UNAVAILABLE": 0,
        "TOTAL": 0
    }
    
    details = []
    
    for symbol in symbols:
        try:
            res = run_v3_validation(symbol)
            val_check = next((c for c in res["checks"] if c["name"] == "Valuation"), None)
            if val_check:
                signal = val_check["signal"]
                stats[signal] = stats.get(signal, 0) + 1
                stats["TOTAL"] += 1
                if signal in ["EXPENSIVE", "CAUTION", "UNAVAILABLE"]:
                    details.append(f"{symbol}: {signal} - {val_check['detail']}")
        except Exception as e:
            print(f"Error validating {symbol}: {e}")
            
    print("\nValuation Stats:")
    for k, v in stats.items():
        print(f"{k}: {v} ({v/stats['TOTAL']*100:.1f}%" if stats['TOTAL'] > 0 else f"{k}: {v}")
        
    print("\nSample Failures (EXPENSIVE/CAUTION/UNAVAILABLE):")
    for d in details[:20]:
        print(d)

if __name__ == "__main__":
    analyze_valuation_on_universe("nifty50")
