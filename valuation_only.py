
import sys
import os
import logging

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from v4.valuation_runner import run_v4_valuation, print_v4_report

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

        res = run_v4_valuation(clean_sym)
        print_v4_report(res)

if __name__ == "__main__":
    run_valuation_only(sys.argv[1:])
