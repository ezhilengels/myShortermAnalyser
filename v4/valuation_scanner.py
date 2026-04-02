
import sys
import os
import logging
import time
import random
from typing import List, Dict, Any

# Ensure we can import from the root
sys.path.append(os.getcwd())

from v4.valuation_runner import run_v4_valuation
from v3.universe_loader import load_universe
from data.fetchers.yfinance_fetcher import get_historical_data, get_current_price
from config import STOCK_NAMES, V4_SKIP_PREFILTER

logger = logging.getLogger(__name__)

# Configure logging for terminal visibility
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def calculate_rsi(series, period=14):
    """Manual RSI calculation to avoid pandas_ta dependency."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (100 + rs))

def is_technically_strong(symbol: str) -> bool:
    """
    Technical Pre-Filter: Check if a stock is worth valuing (not crashing).
    Rules: Price > 200DMA AND RSI(14) > 40.
    """
    try:
        df = get_historical_data(symbol, period="1y", interval="1d")
        if df is None or df.empty or len(df) < 200:
            return True # Not enough data, allow valuation anyway

        # Calculate Indicators manually
        df["SMA200"] = df["Close"].rolling(window=200).mean()
        df["RSI"] = calculate_rsi(df["Close"], period=14)

        current_price = df["Close"].iloc[-1]
        sma200 = df["SMA200"].iloc[-1]
        rsi = df["RSI"].iloc[-1]

        # Criteria
        above_200dma = current_price > (sma200 * 0.98) # 2% buffer
        healthy_rsi = rsi > 38 # Slightly more lenient than 40

        if above_200dma and healthy_rsi:
            return True
        
        reason = []
        if not above_200dma: reason.append(f"below 200DMA ({current_price:.2f} < {sma200:.2f})")
        if not healthy_rsi: reason.append(f"weak RSI ({rsi:.1f})")
        logger.info(f"⏭️ Skipping {symbol}: {' & '.join(reason)}")
        return False

    except Exception as e:
        logger.error(f"Error in technical pre-filter for {symbol}: {e}")
        return True # Default to True if filter fails, don't block valuation

def run_valuation_scan(universe_name: str = "watchlist"):
    """
    Run V4 Intrinsic Valuation on an entire universe and rank by MoS.
    Implements technical pre-filtering and sequential jitter to avoid 429 errors.
    """
    print(f"🚀 --- V4 VALUE SCANNER: {universe_name.upper()} --- 🚀")
    symbols = load_universe(universe_name)
    total_count = len(symbols)
    print(f"Universe size: {total_count} stocks\n")
    
    passed_filter = []
    skipped_count = 0

    # Phase 1: Technical Pre-Filter
    if V4_SKIP_PREFILTER:
        logger.info("ℹ️ V4_SKIP_PREFILTER is ON: Bypassing Phase 1 and valuing all stocks.")
        passed_filter = symbols
    else:
        print("⏳ Phase 1: Running Technical Pre-Filter (Trend & RSI)...")
        for sym in symbols:
            if is_technically_strong(sym):
                passed_filter.append(sym)
            else:
                skipped_count += 1
        print(f"✅ Filter complete: {len(passed_filter)} passed, {skipped_count} skipped (Technically Weak).\n")

    # Phase 2: Sequential Throttled Valuation
    print("⏳ Phase 2: Running Sequential V4 Valuation (with Jitter to avoid 429)...")
    results = []
    count = 0
    total_passed = len(passed_filter)

    for sym in passed_filter:
        count += 1
        try:
            # Human-mimicry delay: 3 to 6 seconds between stocks
            if count > 1:
                delay = random.uniform(3.0, 6.0)
                logger.info(f"⏳ Waiting {delay:.1f}s jitter...")
                time.sleep(delay)

            logger.info(f"🔍 [{count}/{total_passed}] Valuing {sym}...")
            res = run_v4_valuation(sym)
            
            if res.get("success"):
                results.append(res)
            else:
                print(f"\n❌ {sym} failed: {res.get('reason')}")
                
        except Exception as e:
            print(f"\n❌ {sym} error: {e}")
            logger.error(f"Error scanning {sym}: {e}")

    print("\n\n📊 --- FINAL V4 SCAN RESULTS --- 📊")
    # Sort by Margin of Safety (Highest to Lowest)
    ranked = sorted(results, key=lambda x: x["margin_of_safety"], reverse=True)
    
    print(f"{'SYMBOL':<15} | {'PRICE':<10} | {'IV':<10} | {'MoS %':<10} | {'VERDICT':<15} | {'MODEL USED'}")
    print("-" * 110)
    
    for r in ranked:
        name = STOCK_NAMES.get(r['symbol'], r['symbol'].replace(".NS", ""))
        mos_str = f"{r['margin_of_safety']:+.1f}%"
        print(f"{name:<15} | {r['cmp']:>10.2f} | {r['iv']:>10.2f} | {mos_str:>10} | {r['verdict']:<15} | {r['model_used']}")

    print(f"\n✅ Scan complete. (Total: {total_count} | Skipped: {skipped_count} | Success: {len(results)})")
    return ranked

if __name__ == "__main__":
    uni = sys.argv[1] if len(sys.argv) > 1 else "watchlist"
    run_valuation_scan(uni)
