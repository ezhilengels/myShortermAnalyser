"""
config.py — Central configuration for Stock Analysis Bot
All settings, watchlist, thresholds, and constants live here. Ezhil
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# API KEYS (loaded from .env)
# ─────────────────────────────────────────────
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")
NEWS_API_KEY        = os.getenv("NEWS_API_KEY", "")
REDIS_URL           = os.getenv("REDIS_URL", "redis://localhost:6379")

# ─────────────────────────────────────────────
# WATCHLIST — NSE Yahoo Finance symbols
# ─────────────────────────────────────────────
WATCHLIST = [
    "NATIONALUM.NS",   # NALCO
    "HINDZINC.NS",     # Hindustan Zinc
    "BEL.NS",          # Bharat Electronics Limited
    "NTPC.NS",         # NTPC
    "ICICIBANK.NS",    # ICICI Bank
    "PRECWIRE.NS",     # Precision Wires India
]

# Human-readable names for Telegram display
STOCK_NAMES = {
    "NATIONALUM.NS": "NALCO",
    "HINDZINC.NS":   "HINDZINC",
    "HINDALCO.NS":   "HINDALCO",
    "VEDL.NS":       "VEDANTA",
    "HINDCOPPER.NS": "HINDCOPPER",
    "BEL.NS":        "BEL",
    "NTPC.NS":       "NTPC",
    "ICICIBANK.NS":  "ICICIBANK",
    "PRECWIRE.NS":   "PRECWIRE",
    "COALINDIA.NS":  "COALINDIA",
    "GRANULES.NS":   "GRANULES",
    "AUROPHARMA.NS": "AUROPHARMA",
    "IPCALAB.NS":    "IPCALAB",
    "NCC.NS":        "NCC",
    "ATHERENERG.NS": "ATHERENERG",
}

# Common user-entered aliases that do not match Yahoo NSE symbols directly.
SYMBOL_ALIASES = {
    "NALCO": "NATIONALUM.NS",
    "NATIONAL ALUMINIUM": "NATIONALUM.NS",
    "HCL": "HCLTECH.NS",
    "HCLTECH": "HCLTECH.NS",
    "HDFC": "HDFCBANK.NS",
    "M&M": "M&M.NS",
    "MM": "M&M.NS",
    "BAJAJFIN": "BAJFINANCE.NS",
    "COALINDIA": "COALINDIA.NS",
    "COAL INDIA": "COALINDIA.NS",
    "GRANULES": "GRANULES.NS",
    "GTRANULES": "GRANULES.NS",
    "GRANULES INDIA": "GRANULES.NS",
    "AUROPHARMA": "AUROPHARMA.NS",
    "AURO": "AUROPHARMA.NS",
    "IPCALAB": "IPCALAB.NS",
    "IPCA": "IPCALAB.NS",
    "IPCA LABS": "IPCALAB.NS",
    "NCC": "NCC.NS",
    "NCINDIA": "NCC.NS",
    "N C C": "NCC.NS",
    "ATHERENERG": "ATHERENERG.NS",
    "ATHER": "ATHERENERG.NS",
    "ATHER ENERGY": "ATHERENERG.NS",
    "VEDANTA": "VEDL.NS",
    "VEDANRA": "VEDL.NS",
    "VEDL": "VEDL.NS",
    "HINDZINC": "HINDZINC.NS",
    "HINDALCO": "HINDALCO.NS",
    "HIDALCO": "HINDALCO.NS",
    "HINDCOPPER": "HINDCOPPER.NS",
    "HIND COPPER": "HINDCOPPER.NS",
}

# ─────────────────────────────────────────────
# COMMODITY MAP — which commodity affects which stock
# ─────────────────────────────────────────────
STOCK_COMMODITY_MAP = {
    "NATIONALUM.NS": ["ALI=F"],           # Aluminium futures
    "HINDZINC.NS":   ["ZNC=F", "SI=F"],   # Zinc + Silver
    "HINDALCO.NS":   ["ALI=F"],
    "PRECWIRE.NS":   ["HG=F"],            # Copper (input cost)
    "BEL.NS":        [],                  # Defence — no direct commodity
    "NTPC.NS":       ["BZ=F"],            # Brent Crude (power cost)
    "ICICIBANK.NS":  [],                  # Banking — no commodity link
}

# Yahoo symbols for sector benchmarks used in relative-strength checks.
STOCK_SECTOR_BENCHMARKS = {
    "NATIONALUM.NS": "^CNXMETAL",
    "HINDZINC.NS":   "^CNXMETAL",
    "PRECWIRE.NS":   "^CNXMETAL",
    "ICICIBANK.NS":  "^NSEBANK",
    "NTPC.NS":       "^CNXENERGY",
    "BEL.NS":        "^CNXINFRA",
}

# Official NSDL fortnightly FPI sector labels used for the enhanced sector-rotation signal.
SECTOR_FLOW_LABELS = {
    "^CNXMETAL": "Metals & Mining",
    "^NSEBANK": "Financial Services",
    "^CNXENERGY": "Power",
    "^CNXINFRA": "Capital Goods",
}

# Peer groups used to build a richer live valuation benchmark than a static sector PE.
VALUATION_PEERS = {
    "NATIONALUM.NS": ["HINDALCO.NS", "VEDL.NS", "HINDZINC.NS"],
    "HINDZINC.NS":   ["VEDL.NS", "NATIONALUM.NS", "HINDALCO.NS"],
    "BEL.NS":        ["HAL.NS", "BDL.NS", "COCHINSHIP.NS"],
    "NTPC.NS":       ["POWERGRID.NS", "NHPC.NS", "TATAPOWER.NS"],
    "ICICIBANK.NS":  ["HDFCBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS", "SBIN.NS"],
    "PRECWIRE.NS":   ["FINCABLES.NS", "POLYCAB.NS", "KEI.NS"],
}

# Screener company codes. For most NSE tickers the stripped symbol works;
# this map exists for exceptions and explicit control.
SCREENER_COMPANY_CODES = {
    "NATIONALUM": "NATIONALUM",
    "HINDZINC": "HINDZINC",
    "BEL": "BEL",
    "NTPC": "NTPC",
    "ICICIBANK": "ICICIBANK",
    "PRECWIRE": "PRECWIRE",
    "HINDALCO": "HINDALCO",
    "VEDL": "VEDL",
    "HAL": "HAL",
    "BDL": "BDL",
    "COCHINSHIP": "COCHINSHIP",
    "POWERGRID": "POWERGRID",
    "NHPC": "NHPC",
    "TATAPOWER": "TATAPOWER",
    "HDFCBANK": "HDFCBANK",
    "AXISBANK": "AXISBANK",
    "KOTAKBANK": "KOTAKBANK",
    "SBIN": "SBIN",
    "FINCABLES": "FINCABLES",
    "POLYCAB": "POLYCAB",
    "KEI": "KEI",
}

# ─────────────────────────────────────────────
# INDUSTRY PE BENCHMARKS
# ─────────────────────────────────────────────
INDUSTRY_PE = {
    "Basic Materials":      25,  # Raised from 12 (Specialty chemicals/Metals in India)
    "Industrials":          35,  # Raised from 28 (Defence/CapGoods are 40-60+)
    "Financial Services":   22,  # Raised from 18
    "Utilities":            25,  # Raised from 20
    "Technology":           35,
    "Consumer Cyclical":    40,  # Raised from 25 (Auto/Retail)
    "Consumer Defensive":   45,  # Raised from 30 (FMCG commands high PE in India)
    "Healthcare":           35,  # Raised from 30
    "Energy":               18,  # Raised from 14
    "Real Estate":          35,  # Raised from 22
    "Communication Services": 30, # Raised from 25
    "Unknown":              25,
}

# ─────────────────────────────────────────────
# F&O ELIGIBLE STOCKS (for Option Chain / Max Pain / PCR)
# ─────────────────────────────────────────────
FNO_STOCKS = [
    "NATIONALUM", "HINDZINC", "BEL", "NTPC", "ICICIBANK"
    # PRECWIRE is not F&O eligible
]

# ─────────────────────────────────────────────
# SCHEDULER TIMES (IST)
# ─────────────────────────────────────────────
REPORT_TIMES = {
    "morning": {"hour": 8,  "minute": 30},
    "evening": {"hour": 16, "minute": 15},
    "fii_refresh": {"hour": 17, "minute": 30},
}

# ─────────────────────────────────────────────
# SCORING WEIGHTS
# ─────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "STRONG_BUY":             2,
    "STRONG":                 2,
    "BULLISH":                1,
    "UPTREND":                1,
    "OPPORTUNITY":            1,
    "OVERSOLD_BUY":           1,
    "UNDERVALUED":            1,
    "CONTRARIAN_BUY":         1,
    "OPERATOR_ACCUMULATION":  2,
    "STRONGLY_LONG":          2,
    "SLIGHTLY_LONG":          1,
    "STRONG_OPPORTUNITY":     2,
    "STRONG_CONFIDENCE":      2,
    "POSITIVE":               1,
    "MODERATE":               0,
    "NEUTRAL":                0,
    "INFO":                   0,
    "UNAVAILABLE":            0,
    "SIDEWAYS":               0,
    "FAIRLY_VALUED":          0,
    "MIXED":                  0,
    "GOOD":                   1,
    "EXCELLENT":              1,
    "GREED":                 -1,
    "NOISE":                  0,
    "CAUTION":               -1,
    "BEARISH":               -1,
    "DOWNTREND":             -1,
    "EXPENSIVE":             -1,
    "OVERBOUGHT":            -1,
    "SLIGHTLY_BEARISH":      -1,
    "FEAR":                  -2,
    "HIGH_RISK":             -2,
    "BEARISH":               -2,
    "STRONG_SELL":           -2,
    "CONTRARIAN_SELL":       -1,
    "STRONGLY_SHORT":        -2,
    "SLIGHTLY_SHORT":        -1,
    "RED_FLAG":              -2,
    "WEAK":                  -1,
}

# Lower trust checks should contribute less to the final score.
CHECK_WEIGHTS = {
    11: 0.75,  # Stock-specific FII exit pressure is useful, but still secondary to core price/fundamentals
    15: 0.0,   # News summary is context for AI, not a standalone scored signal
    19: 0.75,  # Promoter holding drift is useful context, but not a primary conviction signal
    20: 0.5,   # FII index futures is market-level context, not stock-specific conviction
    27: 0.75,  # DXY is broad macro context, not stock-specific
    28: 0.75,  # US 10Y yield is broad macro context, not stock-specific
    # V2 Group 2 additions
    31: 0.80,  # Block/Bulk deals: good signal but may not fire every day
    32: 0.75,  # FII sector rotation is sector-level, not stock-specific
    33: 0.65,  # China PMI proxy is indirect and sector-specific
}

CHECK_BUCKETS = {
    1: "core", 2: "core", 3: "core", 4: "core", 5: "core", 6: "core",
    7: "core", 8: "core", 9: "core", 10: "core",
    11: "context", 12: "context", 13: "context", 14: "core", 15: "context",
    16: "context", 17: "context", 18: "context", 19: "context", 20: "context",
    21: "core",
    # V2 Group 1 additions
    22: "core", 23: "core", 24: "core", 25: "core", 26: "core",
    27: "context", 28: "context",
    # V2 Group 2 additions
    29: "core", 30: "core", 31: "context", 32: "context", 33: "context",
}

CHECK_SOURCES = {
    1: "Yahoo price history",
    2: "Yahoo price history",
    3: "Yahoo price history",
    4: "Yahoo price history",
    5: "Yahoo ticker info",
    6: "Yahoo daily price history",
    7: "Screener + Yahoo fundamentals",
    8: "Screener + Yahoo fundamentals",
    9: "Screener + Yahoo fundamentals",
    10: "Screener + Yahoo fundamentals + peer benchmark",
    11: "Screener shareholding + Yahoo sector trend",
    12: "Yahoo Nifty + sector benchmark + stock trend",
    13: "India VIX + US VIX feeds",
    14: "Commodity feeds",
    15: "NewsAPI headlines",
    16: "NSE option chain",
    17: "NSE trade info",
    18: "NSE option chain",
    19: "Screener shareholding trend",
    20: "NSE FII futures feed",
    21: "Yahoo fundamentals + 52W range",
    # V2 Group 1 additions
    22: "Yahoo price history (ATR Supertrend)",
    23: "Yahoo price history (Bollinger + Keltner)",
    24: "Yahoo price history (swing pivot zones)",
    25: "Yahoo price history vs Nifty 20-day return",
    26: "Yahoo price history + volume vs 52W high",
    27: "Yahoo Finance DXY (DX-Y.NYB)",
    28: "Yahoo Finance US 10-Year yield (^TNX)",
    # V2 Group 2 additions
    29: "Yahoo price history (VPT volume-price trend)",
    30: "Screener DII shareholding quarterly trend",
    31: "NSE bulk/block deal API",
    32: "Yahoo sector indices 3-week rotation vs Nifty",
    33: "Yahoo Shanghai Composite + commodity proxy",
}

CHECK_BASE_CONFIDENCE = {
    1: 0.90, 2: 0.80, 3: 0.85, 4: 0.90, 5: 0.75, 6: 0.72,
    7: 0.65, 8: 0.60, 9: 0.75, 10: 0.70,
    11: 0.60, 12: 0.78, 13: 0.70, 14: 0.85, 15: 0.30,
    16: 0.55, 17: 0.60, 18: 0.55, 19: 0.58, 20: 0.40, 21: 0.75,
    # V2 Group 1 additions
    22: 0.82, 23: 0.75, 24: 0.78, 25: 0.82, 26: 0.80,
    27: 0.70, 28: 0.72,
    # V2 Group 2 additions
    29: 0.78, 30: 0.65, 31: 0.72, 32: 0.70, 33: 0.62,
}

CRITICAL_CHECKS = {1, 2, 3, 4, 7, 8, 9, 10, 14, 21, 22, 25, 26, 29, 30}

GRADE_SCALE = [
    (12, 60, "A+", "STRONG BUY"),   # upper cap raised for 28-check scoring
    (8, 11.99, "A",  "BUY"),
    (4, 7.99, "B+", "MODERATE BUY"),
    (1, 3.99, "B",  "WATCHLIST"),
    (-2, 0.99, "C",  "NEUTRAL"),
    (-99, -2.01, "D",  "AVOID"),
]

# ─────────────────────────────────────────────
# NSE HEADERS (required for session cookies)
# ─────────────────────────────────────────────
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com",
    "Connection":      "keep-alive",
}

# ─────────────────────────────────────────────
# REDIS CACHE TTL (seconds)
# ─────────────────────────────────────────────
CACHE_TTL = {
    "fii_dii":      1800,   # 30 minutes
    "option_chain": 1800,   # 30 minutes
    "vix":          600,    # 10 minutes
    "commodity":    300,    # 5 minutes
    "stock_price":  180,    # 3 minutes
}

# ─────────────────────────────────────────────
# GROQ MODEL
# ─────────────────────────────────────────────
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS = 800
GROQ_TEMPERATURE = 0.3

# ─────────────────────────────────────────────
# V3 PRE-FILTER CONFIGURATION
# ─────────────────────────────────────────────
V3_MIN_PRICE        = float(os.getenv("V3_MIN_PRICE", "50.0"))
V3_MIN_MARKET_CAP   = float(os.getenv("V3_MIN_MARKET_CAP_CR", "10000.0"))
V3_MIN_TRADED_VALUE = float(os.getenv("V3_MIN_AVG_TRADED_VALUE_CR", "25.0"))
V3_MIN_REL_VOLUME   = float(os.getenv("V3_MIN_RELATIVE_VOLUME", "1.1"))
V3_REQUIRE_SMA200   = os.getenv("V3_REQUIRE_ABOVE_200DMA", "True").lower() == "true"
V3_REQUIRE_SMA50    = os.getenv("V3_REQUIRE_ABOVE_50DMA", "True").lower() == "true"

# ─────────────────────────────────────────────
# VALUATION THRESHOLDS
# ─────────────────────────────────────────────
VALUATION_PE_DISCOUNT    = float(os.getenv("VALUATION_PE_DISCOUNT", "0.75"))
VALUATION_PB_UNDERVALUED = float(os.getenv("VALUATION_PB_UNDERVALUED", "4.5"))
VALUATION_PE_FAIR        = float(os.getenv("VALUATION_PE_FAIR", "1.10"))
VALUATION_PE_CAUTION     = float(os.getenv("VALUATION_PE_CAUTION", "1.35"))
VALUATION_PB_CAUTION     = float(os.getenv("VALUATION_PB_CAUTION", "6.0"))

# ─────────────────────────────────────────────
# DISCLAIMER
# ─────────────────────────────────────────────
DISCLAIMER = (
    "\n\n⚠️ *DISCLAIMER:* This analysis is generated by an automated bot "
    "for educational purposes only. This is NOT SEBI registered investment advice. "
    "Always do your own research. Past performance ≠ future returns."
)
