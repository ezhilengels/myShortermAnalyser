
import sys
import os
import logging

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from analysis.fundamental import check_valuation
from data.fetchers.yfinance_fetcher import get_ticker_info
from data.fetchers.screener_fetcher import get_screener_snapshot

# Mute noisy logs
logging.basicConfig(level=logging.ERROR)

def run_valuation_only(symbols):
    if not symbols:
        print("Usage: python3 valuation_only.py SYMBOL1 SYMBOL2 ...")
        return

    for sym in symbols:
        # Handle aliases
        from config import SYMBOL_ALIASES
        clean_sym = SYMBOL_ALIASES.get(sym.upper(), sym.upper())
        if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO") and "^" not in clean_sym:
            clean_sym += ".NS"

        print(f"\n--- Valuation Check: {clean_sym} ---")
        
        info = get_ticker_info(clean_sym)
        if not info:
            print(f"❌ Error: Could not fetch Yahoo info for {clean_sym}")
            continue
            
        screener = get_screener_snapshot(clean_sym)
        
        signal, detail = check_valuation(info, clean_sym, screener)
        
        print(f"RESULT: {signal}")
        print(f"DETAIL: {detail}")
        
        # Print the data points used
        pe = info.get("trailingPE") or info.get("forwardPE")
        pb = info.get("priceToBook") or (screener.get("ratios", {}).get("price_to_book") if screener else None)
        sector = info.get("sector", "Unknown")
        print(f"DATA  : PE={pe}, PB={pb}, Sector={sector}")

if __name__ == "__main__":
    run_valuation_only(sys.argv[1:])
