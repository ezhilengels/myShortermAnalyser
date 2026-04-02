
import sys
import os
sys.path.append(os.getcwd())
from data.fetchers.screener_fetcher import get_screener_snapshot

def test_screener():
    symbol = "ASIANPAINT.NS"
    data = get_screener_snapshot(symbol)
    if data.get("source_ok"):
        print(f"Ratios for {symbol}:")
        for k, v in data.get("ratios", {}).items():
            print(f"  {k}: {v}")
    else:
        print(f"FAILED to fetch from Screener for {symbol}")

if __name__ == "__main__":
    test_screener()
