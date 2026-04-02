
import sys
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

# Ensure we can import from the root
sys.path.append(os.getcwd())

from v4.valuation_runner import run_v4_valuation
from v3.universe_loader import load_universe
from config import STOCK_NAMES

logger = logging.getLogger(__name__)

def run_valuation_scan(universe_name: str = "watchlist", max_workers: int = 5):
    """
    Run V4 Intrinsic Valuation on an entire universe and rank by MoS.
    """
    print(f"🚀 --- V4 VALUE SCANNER: {universe_name.upper()} --- 🚀")
    symbols = load_universe(universe_name)
    print(f"Scanning {len(symbols)} stocks...\n")
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(run_v4_valuation, sym): sym for sym in symbols}
        for future in as_completed(futures):
            try:
                res = future.result()
                if res.get("success"):
                    results.append(res)
                else:
                    # Optional: print(f"❌ {futures[future]}: {res.get('reason')}")
                    pass
            except Exception as e:
                logger.error(f"Error scanning {futures[future]}: {e}")

    # Sort by Margin of Safety (Highest to Lowest)
    ranked = sorted(results, key=lambda x: x["margin_of_safety"], reverse=True)
    
    print(f"{'SYMBOL':<15} | {'PRICE':<10} | {'IV':<10} | {'MoS %':<10} | {'VERDICT':<15} | {'MODEL USED'}")
    print("-" * 100)
    
    for r in ranked:
        name = STOCK_NAMES.get(r['symbol'], r['symbol'].replace(".NS", ""))
        mos_str = f"{r['margin_of_safety']:+.1f}%"
        print(f"{name:<15} | {r['cmp']:>10.2f} | {r['intrinsic_value']:>10.2f} | {mos_str:>10} | {r['verdict']:<15} | {r['model_used']}")

    print("\n✅ Scan complete.")
    return ranked

if __name__ == "__main__":
    uni = sys.argv[1] if len(sys.argv) > 1 else "watchlist"
    run_valuation_scan(uni)
