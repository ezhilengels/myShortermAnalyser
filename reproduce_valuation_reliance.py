
import logging
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from analysis.fundamental import check_valuation
from data.fetchers.yfinance_fetcher import get_ticker_info

logging.basicConfig(level=logging.INFO)

def test_valuation_reliance():
    symbol = "RELIANCE.NS"
    print(f"\nTesting Valuation for: {symbol}")
    info = get_ticker_info(symbol)
    if not info:
        print(f"FAILED to get info for {symbol}")
        return
        
    signal, detail = check_valuation(info, symbol)
    print(f"Signal: {signal}")
    print(f"Detail: {detail}")
    
    # Also print raw values for debugging
    pe = info.get("trailingPE")
    fwd_pe = info.get("forwardPE")
    sector = info.get("sector")
    pb = info.get("priceToBook")
    print(f"Raw: PE={pe}, FwdPE={fwd_pe}, Sector={sector}, PB={pb}")

if __name__ == "__main__":
    test_valuation_reliance()
