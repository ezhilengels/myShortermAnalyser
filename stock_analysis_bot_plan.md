# 📊 Stock Analysis Bot — Complete Planning Document
### Python + Groq AI + Telegram | 21-Condition Master Strategy

---

## 📋 TABLE OF CONTENTS

1. Project Overview
2. System Architecture
3. Data Sources & APIs
4. 21-Condition Strategy Implementation
5. Groq AI Decision Engine
6. Telegram Bot Integration
7. Morning & Evening Report Format
8. Scheduler & Automation
9. Project Folder Structure
10. Phase-wise Implementation Plan
11. Environment Setup
12. Risk & Disclaimer Logic

---

## 1. 🎯 PROJECT OVERVIEW

### Goal
Build a fully automated Indian stock analysis bot that:
- Fetches **real live data** every morning and evening
- Applies all **21 conditions** (Technical + Fundamental + Macro + Secret Strategies)
- Uses **Groq AI** to generate natural language decisions
- Sends **formatted reports via Telegram** every morning (8:30 AM) and evening (4:15 PM)
- Runs on **Hetzner VPS via Coolify** using Docker

### Stocks Covered (Configurable)
- NALCO, HINDZINC, BEL, NTPC, ICICI Bank, PRECWIRE
- Easily expandable to any NSE/BSE listed stock

---

## 2. 🏗️ SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                    SCHEDULER (APScheduler)               │
│         8:30 AM Morning Run | 4:15 PM Evening Run        │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────▼────────────┐
         │   DATA FETCHER MODULE   │
         │  (Real-time + Live)     │
         └────────────┬────────────┘
                      │
        ┌─────────────▼──────────────┐
        │  21-CONDITION ANALYSER     │
        │  (4 Categories)            │
        │  ├── Technical (6)         │
        │  ├── Fundamental (4)       │
        │  ├── Macro/Global (5)      │
        │  └── Secret Strategies (6) │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   GROQ AI DECISION ENGINE  │
        │   (llama3-70b-8192)        │
        │   - Score Summary          │
        │   - Trade Recommendation   │
        │   - Entry/Target/SL        │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   TELEGRAM BOT REPORTER    │
        │   - Morning Report 8:30 AM │
        │   - Evening Report 4:15 PM │
        │   - Alert on high signals  │
        └────────────────────────────┘
```

---

## 3. 📡 DATA SOURCES & APIs (ALL REAL DATA)

### 3.1 Stock Price & Technical Data

| Data | Source | Library/API | Free? |
|------|---------|-------------|-------|
| Live Stock Price | Yahoo Finance | `yfinance` | ✅ Free |
| NSE OHLCV + Volume | NSE India | `jugaad-trader` or `nsetools` | ✅ Free |
| Historical OHLC | Yahoo Finance | `yfinance` | ✅ Free |
| EMA / MACD / RSI | Calculated | `pandas-ta` | ✅ Free |
| 52W High / Low | Yahoo Finance | `yfinance` | ✅ Free |
| Delivery % | NSE Bhav Copy | NSE direct URL scraper | ✅ Free |

### 3.2 Fundamental Data

| Data | Source | Method |
|------|---------|--------|
| PE Ratio, PB Ratio | Yahoo Finance | `yfinance` `.info` |
| Revenue, PAT, ROE | Screener.in | Web scraper (BeautifulSoup) |
| Dividend Yield | Yahoo Finance | `yfinance` `.info` |
| Debt to Equity | Yahoo Finance | `yfinance` `.info` |
| Earnings Date | Yahoo Finance | `yfinance` `.calendar` |
| Promoter Holding % | BSE India | Web scraper |

### 3.3 FII/DII Data (Secret Strategy #5)

```
Source: NSE India Official
URL: https://www.nseindia.com/api/fiidiiTradeReact
Method: Requests with NSE headers (session cookie handling)
Data: FII Net Buy/Sell in Cash + Derivatives
```

### 3.4 Commodity Data (Zinc, Aluminium, Silver, Crude)

| Commodity | Source | API |
|-----------|--------|-----|
| LME Zinc | investing.com scraper | BeautifulSoup |
| LME Aluminium | investing.com scraper | BeautifulSoup |
| COMEX Silver | Yahoo Finance | `yfinance` (SI=F) |
| Brent Crude | Yahoo Finance | `yfinance` (BZ=F) |
| MCX Zinc | NSE/MCX | `yfinance` |

### 3.5 PCR Data (Secret Strategy #3)

```
Source: NSE India F&O Section
URL: https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY
Method: Requests with session headers
Extract: Total Put OI / Total Call OI = PCR ratio
```

### 3.6 Global Sentiment

| Data | Source | Method |
|------|---------|--------|
| India VIX | NSE India | `yfinance` (^INDIAVIX) |
| Fear & Greed Index | CNN Money | Web scraper |
| SGX Nifty (Nifty Futures) | Yahoo Finance | `yfinance` |
| GIFT Nifty | NSE Data | API |

### 3.7 Promoter / Insider Data (Secret Strategy #4)

```
Source: BSE India Insider Trading
URL: https://www.bseindia.com/corporates/Insider_Trading_new.html
Method: BeautifulSoup scraper, filter by stock name, last 30 days
Check: Promoter Buy vs Sell in past 30 days
```

---

## 4. 🔬 21-CONDITION IMPLEMENTATION DETAILS

### CATEGORY 1: TECHNICAL CONDITIONS (6 Checks)

#### Check 1 — DMA Position
```python
def check_dma_position(df):
    """
    df: pandas DataFrame with OHLCV data from yfinance
    Returns: BULLISH / BEARISH / NEUTRAL
    """
    current_price = df['Close'].iloc[-1]
    sma_50 = df['Close'].rolling(50).mean().iloc[-1]
    sma_200 = df['Close'].rolling(200).mean().iloc[-1]
    
    if current_price > sma_50 and current_price > sma_200:
        return "BULLISH", f"Price ₹{current_price:.2f} above 50DMA ₹{sma_50:.2f} and 200DMA ₹{sma_200:.2f}"
    elif current_price < sma_50:
        return "BEARISH", f"Price ₹{current_price:.2f} below 50DMA ₹{sma_50:.2f}"
    else:
        return "NEUTRAL", f"Mixed DMA signals"
```

#### Check 2 — MACD
```python
def check_macd(df):
    """
    Uses pandas-ta library for accurate MACD calculation
    """
    import pandas_ta as ta
    macd = ta.macd(df['Close'])
    macd_line = macd['MACD_12_26_9'].iloc[-1]
    signal_line = macd['MACDs_12_26_9'].iloc[-1]
    histogram = macd['MACDh_12_26_9'].iloc[-1]
    
    if macd_line > signal_line and histogram > 0:
        return "BULLISH", f"MACD {macd_line:.3f} above signal {signal_line:.3f}"
    elif macd_line < signal_line:
        return "BEARISH", f"MACD below signal — sell pressure"
    else:
        return "NEUTRAL", "MACD crossing — watch"
```

#### Check 3 — RSI
```python
def check_rsi(df):
    import pandas_ta as ta
    rsi = ta.rsi(df['Close'], length=14).iloc[-1]
    
    if rsi > 70:
        return "OVERBOUGHT", f"RSI {rsi:.1f} — overbought, avoid entry"
    elif rsi < 30:
        return "OVERSOLD_BUY", f"RSI {rsi:.1f} — oversold, contrarian buy zone"
    elif 45 <= rsi <= 60:
        return "BULLISH", f"RSI {rsi:.1f} — healthy uptrend zone"
    else:
        return "NEUTRAL", f"RSI {rsi:.1f} — neutral"
```

#### Check 4 — Moving Averages Multi-Timeframe
```python
def check_moving_averages(df):
    """
    Check 5 DMA, 20 DMA, 50 DMA, 200 DMA alignment
    """
    price = df['Close'].iloc[-1]
    sma5   = df['Close'].rolling(5).mean().iloc[-1]
    sma20  = df['Close'].rolling(20).mean().iloc[-1]
    sma50  = df['Close'].rolling(50).mean().iloc[-1]
    sma200 = df['Close'].rolling(200).mean().iloc[-1]
    
    bullish_count = sum([price > sma5, price > sma20, price > sma50, price > sma200])
    
    if bullish_count == 4:
        return "STRONG_BUY", "Price above all 4 moving averages"
    elif bullish_count >= 3:
        return "BULLISH", f"Price above {bullish_count}/4 moving averages"
    elif bullish_count <= 1:
        return "BEARISH", f"Price below {4-bullish_count}/4 moving averages"
    else:
        return "NEUTRAL", "Mixed moving average signals"
```

#### Check 5 — 52-Week Range Position
```python
def check_52w_range(ticker_info):
    current = ticker_info.get('currentPrice', 0)
    high_52w = ticker_info.get('fiftyTwoWeekHigh', 0)
    low_52w  = ticker_info.get('fiftyTwoWeekLow', 0)
    
    range_pct = ((current - low_52w) / (high_52w - low_52w)) * 100 if high_52w != low_52w else 50
    pct_from_high = ((high_52w - current) / high_52w) * 100
    
    if range_pct < 30:
        return "OPPORTUNITY", f"Near 52W low — value zone. {pct_from_high:.1f}% below 52W high"
    elif range_pct > 85:
        return "CAUTION", f"Near 52W high ₹{high_52w} — resistance zone"
    else:
        return "NEUTRAL", f"Mid-range. {pct_from_high:.1f}% below 52W high ₹{high_52w}"
```

#### Check 6 — Intraday Trend (Short-term momentum)
```python
def check_intraday_trend(df_1h):
    """
    Uses 1-hour data — last 5 candles trend
    """
    closes = df_1h['Close'].tail(5).values
    if closes[-1] > closes[-3] > closes[-5]:
        return "UPTREND", "Consistent higher closes in last 5 hours"
    elif closes[-1] < closes[-3] < closes[-5]:
        return "DOWNTREND", "Consistent lower closes — caution"
    else:
        return "SIDEWAYS", "Choppy price action — wait"
```

---

### CATEGORY 2: FUNDAMENTAL CONDITIONS (4 Checks)

#### Check 7 — Earnings Growth
```python
def check_earnings_growth(ticker_info, financials_df):
    """
    Compares last 2 quarters revenue and PAT
    """
    revenue_growth = calculate_yoy_growth(financials_df, 'Total Revenue')
    net_income_growth = calculate_yoy_growth(financials_df, 'Net Income')
    
    if revenue_growth > 15 and net_income_growth > 20:
        return "STRONG", f"Revenue +{revenue_growth:.1f}% YoY, PAT +{net_income_growth:.1f}% YoY"
    elif revenue_growth > 0 and net_income_growth > 0:
        return "MODERATE", f"Revenue +{revenue_growth:.1f}%, PAT +{net_income_growth:.1f}%"
    else:
        return "WEAK", f"Revenue {revenue_growth:.1f}%, PAT {net_income_growth:.1f}%"
```

#### Check 8 — Profit Margin & ROE
```python
def check_margins(ticker_info):
    roe = ticker_info.get('returnOnEquity', 0) * 100
    profit_margin = ticker_info.get('profitMargins', 0) * 100
    
    if roe > 20 and profit_margin > 15:
        return "STRONG", f"ROE {roe:.1f}%, Margin {profit_margin:.1f}%"
    elif roe > 12 and profit_margin > 8:
        return "MODERATE", f"ROE {roe:.1f}%, Margin {profit_margin:.1f}%"
    else:
        return "WEAK", f"ROE {roe:.1f}%, Margin {profit_margin:.1f}% — thin"
```

#### Check 9 — Debt Level
```python
def check_debt(ticker_info):
    debt_to_equity = ticker_info.get('debtToEquity', 0)
    
    if debt_to_equity == 0 or debt_to_equity < 10:
        return "EXCELLENT", f"Debt/Equity {debt_to_equity:.1f}% — nearly debt free"
    elif debt_to_equity < 50:
        return "GOOD", f"Debt/Equity {debt_to_equity:.1f}% — manageable"
    elif debt_to_equity < 100:
        return "MODERATE", f"Debt/Equity {debt_to_equity:.1f}% — watch"
    else:
        return "HIGH_RISK", f"Debt/Equity {debt_to_equity:.1f}% — high leverage"
```

#### Check 10 — Valuation (PE vs Industry)
```python
def check_valuation(ticker_info, industry_pe_map):
    """
    industry_pe_map: dict of sector -> average PE
    e.g. {"Metals": 15, "Banking": 18, "Defence": 35}
    """
    pe = ticker_info.get('trailingPE', 0)
    sector = ticker_info.get('sector', 'Unknown')
    industry_pe = industry_pe_map.get(sector, 20)
    
    if pe == 0:
        return "NEUTRAL", "PE data unavailable"
    elif pe < industry_pe * 0.8:
        return "UNDERVALUED", f"PE {pe:.1f} vs industry {industry_pe} — undervalued!"
    elif pe < industry_pe * 1.2:
        return "FAIRLY_VALUED", f"PE {pe:.1f} vs industry {industry_pe} — fair value"
    else:
        return "EXPENSIVE", f"PE {pe:.1f} vs industry {industry_pe} — expensive"
```

---

### CATEGORY 3: MACRO CONDITIONS (5 Checks)

#### Check 11 — FII/DII Cash Market Activity
```python
def fetch_fii_dii_data():
    """
    Fetches real FII/DII data from NSE India
    Returns net buy/sell figures
    """
    import requests
    
    session = requests.Session()
    # First hit NSE homepage to get cookies
    session.get("https://www.nseindia.com", headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    response = session.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.nseindia.com'
    })
    
    data = response.json()
    # Extract FII and DII net values
    fii_net = float(data[0]['netVal'])   # FII net (Cash market)
    dii_net = float(data[1]['netVal'])   # DII net (Cash market)
    
    if fii_net > 0 and dii_net > 0:
        return "BULLISH", f"FII +₹{fii_net:.0f}Cr, DII +₹{dii_net:.0f}Cr — both buying!"
    elif fii_net < 0 and dii_net > 0:
        return "MIXED", f"FII -₹{abs(fii_net):.0f}Cr selling, DII +₹{dii_net:.0f}Cr buying"
    elif fii_net < 0:
        return "BEARISH", f"FII -₹{abs(fii_net):.0f}Cr net sell — caution"
    else:
        return "NEUTRAL", "FII/DII activity minimal"
```

#### Check 12 — India Market Trend (Sensex/Nifty)
```python
def check_india_market():
    import yfinance as yf
    nifty = yf.Ticker("^NSEI")
    hist = nifty.history(period="1mo")
    
    monthly_return = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
    current = hist['Close'].iloc[-1]
    
    if monthly_return > 2:
        return "BULLISH", f"Nifty up {monthly_return:.1f}% this month — positive environment"
    elif monthly_return < -3:
        return "BEARISH", f"Nifty down {abs(monthly_return):.1f}% this month — headwind"
    else:
        return "NEUTRAL", f"Nifty flat {monthly_return:.1f}% — mixed environment"
```

#### Check 13 — Global Sentiment (VIX + Fear Index)
```python
def check_global_sentiment():
    import yfinance as yf
    
    # India VIX
    vix = yf.Ticker("^INDIAVIX")
    vix_value = vix.history(period="2d")['Close'].iloc[-1]
    
    # US VIX for global reference
    us_vix = yf.Ticker("^VIX")
    us_vix_value = us_vix.history(period="2d")['Close'].iloc[-1]
    
    if vix_value > 25 or us_vix_value > 30:
        return "FEAR", f"India VIX {vix_value:.1f}, US VIX {us_vix_value:.1f} — high fear"
    elif vix_value < 14 and us_vix_value < 18:
        return "GREED", f"India VIX {vix_value:.1f} — low fear, complacency risk"
    else:
        return "NEUTRAL", f"India VIX {vix_value:.1f}, US VIX {us_vix_value:.1f} — normal"
```

#### Check 14 — Commodity Prices (Stock-specific)
```python
STOCK_COMMODITY_MAP = {
    "NALCO.NS":     ["ALI=F"],        # Aluminium futures
    "HINDZINC.NS":  ["ZNC=F", "SI=F"], # Zinc + Silver
    "HINDALCO.NS":  ["ALI=F"],
    "PRECWIRE.NS":  ["HG=F"],         # Copper (input cost)
    "BEL.NS":       [],               # Defence — no direct commodity
    "NTPC.NS":      ["BZ=F"],         # Crude Oil (power cost)
    "ICICIBANK.NS": [],               # Banking — no commodity link
}

def check_commodity(stock_symbol):
    commodities = STOCK_COMMODITY_MAP.get(stock_symbol, [])
    if not commodities:
        return "NEUTRAL", "No direct commodity link for this stock"
    
    results = []
    for comm in commodities:
        ticker = yf.Ticker(comm)
        hist = ticker.history(period="5d")
        change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-3]) / hist['Close'].iloc[-3]) * 100
        results.append((comm, change))
    
    avg_change = sum(c for _, c in results) / len(results)
    
    if avg_change > 1.5:
        return "BULLISH", f"Commodity up {avg_change:.1f}% in 2 days — tailwind"
    elif avg_change < -1.5:
        return "BEARISH", f"Commodity down {abs(avg_change):.1f}% — headwind"
    else:
        return "NEUTRAL", f"Commodity flat {avg_change:.1f}%"
```

#### Check 15 — Geopolitical / De-escalation Trigger
```python
def check_geopolitical_trigger():
    """
    Uses Groq AI to summarize latest geopolitical news impact
    Searches for: Iran war, US tariffs, Middle East news
    """
    # This feeds into the Groq AI prompt for interpretation
    # Real news fetched via NewsAPI or RSS
    return fetch_geopolitical_news_summary()
```

---

### CATEGORY 4: SECRET STRATEGIES (6 Checks)

#### Secret #1 — Max Pain Theory
```python
def check_max_pain(stock_symbol):
    """
    Fetches option chain from NSE and calculates max pain
    """
    nse_symbol = stock_symbol.replace(".NS", "")
    
    session = get_nse_session()
    url = f"https://www.nseindia.com/api/option-chain-equities?symbol={nse_symbol}"
    response = session.get(url)
    data = response.json()
    
    records = data['records']['data']
    
    pain_data = {}
    for record in records:
        strike = record['strikePrice']
        ce_oi = record.get('CE', {}).get('openInterest', 0)
        pe_oi = record.get('PE', {}).get('openInterest', 0)
        pain_data[strike] = {'CE_OI': ce_oi, 'PE_OI': pe_oi}
    
    # Max pain = strike where total $ loss of all option holders is maximum
    max_pain_strike = calculate_max_pain_strike(pain_data)
    current_price = get_current_price(nse_symbol)
    
    diff_pct = ((max_pain_strike - current_price) / current_price) * 100
    
    if diff_pct > 2:
        return "BULLISH", f"Max pain ₹{max_pain_strike} is {diff_pct:.1f}% above CMP — drift UP expected"
    elif diff_pct < -2:
        return "BEARISH", f"Max pain ₹{max_pain_strike} is {abs(diff_pct):.1f}% below CMP — drift DOWN expected"
    else:
        return "NEUTRAL", f"Max pain ₹{max_pain_strike} near current price — no strong directional pull"
```

#### Secret #2 — Delivery Percentage (Operator Detection)
```python
def check_delivery_percentage(stock_symbol):
    """
    NSE Bhav Copy — delivery % vs volume vs average
    High delivery % + price up = real institutional buying
    """
    nse_symbol = stock_symbol.replace(".NS", "")
    
    # Fetch today's bhav copy from NSE
    today = datetime.now().strftime("%d%b%Y").upper()
    url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol}&section=trade_info"
    
    session = get_nse_session()
    response = session.get(url)
    data = response.json()
    
    delivery_pct = data['marketDeptOrderBook']['tradeInfo']['totalBuyQuantity']  # Adjust per API
    total_volume = data['marketDeptOrderBook']['tradeInfo']['totalTradedVolume']
    
    # Compare with 10-day average delivery
    avg_delivery = get_10day_avg_delivery(nse_symbol)
    
    if delivery_pct > 60 and total_volume > avg_volume * 1.5:
        return "OPERATOR_ACCUMULATION", f"Delivery {delivery_pct:.1f}% with {total_volume/avg_volume:.1f}x volume — smart money buying!"
    elif delivery_pct > 50:
        return "BULLISH", f"Delivery {delivery_pct:.1f}% — real buying, not just intraday"
    elif delivery_pct < 25:
        return "NOISE", f"Delivery only {delivery_pct:.1f}% — mostly intraday, don't trust move"
    else:
        return "NEUTRAL", f"Delivery {delivery_pct:.1f}% — moderate institutional interest"
```

#### Secret #3 — PCR (Put-Call Ratio) Reversal Trap
```python
def check_pcr(stock_symbol=None):
    """
    For individual stocks: stock option PCR
    For market: Nifty PCR
    PCR < 0.6 = extreme fear = contrarian BUY
    PCR > 1.4 = extreme greed = contrarian SELL
    """
    nse_symbol = stock_symbol.replace(".NS", "") if stock_symbol else "NIFTY"
    
    session = get_nse_session()
    
    if nse_symbol == "NIFTY":
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    else:
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={nse_symbol}"
    
    response = session.get(url)
    data = response.json()
    
    total_ce_oi = data['filtered']['CE']['totOI']
    total_pe_oi = data['filtered']['PE']['totOI']
    pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1
    
    if pcr < 0.6:
        return "CONTRARIAN_BUY", f"PCR {pcr:.2f} — extreme bearishness! Contrarian BUY signal"
    elif pcr > 1.4:
        return "CONTRARIAN_SELL", f"PCR {pcr:.2f} — extreme bullishness = sell signal"
    elif 0.8 <= pcr <= 1.2:
        return "NEUTRAL", f"PCR {pcr:.2f} — balanced sentiment"
    else:
        return "SLIGHTLY_BEARISH" if pcr < 0.8 else "SLIGHTLY_BULLISH", f"PCR {pcr:.2f}"
```

#### Secret #4 — Promoter / Insider Activity
```python
def check_promoter_activity(stock_symbol):
    """
    Scrapes BSE insider trading data for last 30 days
    Promoter buying = strong confidence
    Promoter OFS/selling = red flag
    """
    nse_symbol = stock_symbol.replace(".NS", "")
    
    # BSE Insider Trading API
    url = "https://www.bseindia.com/corporates/Insider_Trading_new.html"
    
    # Use requests + BeautifulSoup to scrape promoter transactions
    # Filter: last 30 days, match stock name
    
    buys, sells = scrape_insider_transactions(nse_symbol, days=30)
    
    if buys > 0 and sells == 0:
        return "STRONG_CONFIDENCE", f"Promoter bought {buys} transactions — insider confidence high!"
    elif sells > 0 and buys == 0:
        return "RED_FLAG", f"Promoter sold in {sells} transactions — insider selling is red flag!"
    elif buys > sells:
        return "POSITIVE", f"Net promoter buying — more buys ({buys}) than sells ({sells})"
    elif sells > buys:
        return "CAUTION", f"Net promoter selling — watch carefully"
    else:
        return "NEUTRAL", "No promoter transactions in last 30 days — stable"
```

#### Secret #5 — FII Index Futures Position
```python
def check_fii_futures():
    """
    FII long/short in index futures = directional bet
    FII net long = market going UP in 2-5 days
    FII net short = market going DOWN
    """
    session = get_nse_session()
    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    response = session.get(url)
    data = response.json()
    
    # FII Derivatives data
    fii_index_futures_long  = float(data[2].get('buyAmount', 0))
    fii_index_futures_short = float(data[2].get('sellAmount', 0))
    net_position = fii_index_futures_long - fii_index_futures_short
    
    if net_position > 2000:
        return "STRONGLY_LONG", f"FII Index Futures NET LONG ₹{net_position:.0f}Cr — market will GO UP!"
    elif net_position > 0:
        return "SLIGHTLY_LONG", f"FII Index Futures slightly long ₹{net_position:.0f}Cr"
    elif net_position < -2000:
        return "STRONGLY_SHORT", f"FII Index Futures NET SHORT ₹{abs(net_position):.0f}Cr — market sell-off coming!"
    else:
        return "SLIGHTLY_SHORT", f"FII Index Futures slightly short ₹{abs(net_position):.0f}Cr"
```

#### Secret #6 — 52-Week Low Reversal Formula
```python
def check_52w_reversal_formula(ticker_info, df):
    """
    Contrarian value formula:
    Near 52W low + Good fundamentals + Low PE + Stable promoter = BUY
    """
    current = ticker_info.get('currentPrice', 0)
    low_52w  = ticker_info.get('fiftyTwoWeekLow', 0)
    high_52w = ticker_info.get('fiftyTwoWeekHigh', 0)
    pe       = ticker_info.get('trailingPE', 999)
    de       = ticker_info.get('debtToEquity', 999)
    
    pct_from_low  = ((current - low_52w) / low_52w) * 100
    pct_from_high = ((high_52w - current) / high_52w) * 100
    
    score = 0
    if pct_from_high > 20: score += 1   # Far from high = opportunity
    if pe < 25:            score += 1   # Reasonable PE
    if de < 50:            score += 1   # Low debt
    if pct_from_low > 10:  score += 1   # Bounced from low = recovery
    
    if score >= 3:
        return "STRONG_OPPORTUNITY", f"{pct_from_high:.1f}% below 52W high. Score {score}/4 — value zone"
    elif score == 2:
        return "MODERATE", f"{pct_from_high:.1f}% below 52W high. Score {score}/4"
    else:
        return "NEUTRAL", f"Score {score}/4 — not a clear opportunity"
```

---

## 5. 🤖 GROQ AI DECISION ENGINE

### Model: llama3-70b-8192 (Fast & Accurate)

```python
from groq import Groq

client = Groq(api_key=GROQ_API_KEY)

def get_groq_decision(stock_symbol, analysis_results, current_price):
    """
    Feeds all 21 condition results to Groq AI
    Gets: Trade decision, Entry, Target, SL, Confidence score
    """
    
    conditions_text = format_conditions_for_ai(analysis_results)
    
    prompt = f"""
You are an expert Indian stock market analyst with 20 years experience in NSE/BSE markets.

Analyze the following 21-condition scorecard for {stock_symbol} at current price ₹{current_price}:

{conditions_text}

Based on this analysis provide:
1. OVERALL VERDICT: (STRONG BUY / BUY / HOLD / SELL / STRONG SELL)
2. SHORT TERM (1-3 days): Entry price, Target, Stop Loss
3. MEDIUM TERM (3 months): Entry price, Target, Stop Loss
4. CONFIDENCE SCORE: X/10
5. KEY RISK: Top 1-2 risks to watch
6. KEY CATALYST: Top 1-2 triggers for the move
7. SUMMARY: 2 line plain English summary for retail trader

Format your response as JSON. Keep it concise and actionable.
Consider: India market is currently {get_india_market_mood()}.
FII activity: {get_fii_summary()}.
"""
    
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800
    )
    
    return parse_groq_response(response.choices[0].message.content)
```

---

## 6. 📱 TELEGRAM BOT INTEGRATION

### Setup
```python
# Use python-telegram-bot library
pip install python-telegram-bot

BOT_TOKEN = "your_telegram_bot_token"
CHAT_ID    = "your_chat_id"  # Your personal chat ID
```

### Bot Commands
| Command | Action |
|---------|--------|
| `/analyze NALCO` | Instant analysis of any stock |
| `/report` | Get latest full report now |
| `/watchlist` | Show all watched stocks |
| `/add HINDZINC` | Add stock to watchlist |
| `/remove HINDZINC` | Remove from watchlist |
| `/fii` | Show today's FII/DII data |
| `/vix` | Show India VIX and fear level |
| `/commodity` | Show all commodity prices |
| `/alert on NALCO 395` | Set price alert |

### Report Message Format
```
📊 MORNING MARKET REPORT
⏰ 8:30 AM | 01-Apr-2026
━━━━━━━━━━━━━━━━━━━━━━

🌍 GLOBAL SNAPSHOT
• Nifty Futures: ▲ 0.4% (Gap-up expected)
• India VIX: 18.2 (Moderate fear)
• Brent Crude: $107.4
• COMEX Silver: $32.1
• LME Aluminium: $2,680

💰 FII/DII TODAY
• FII Cash: +₹892 Cr (BUYING 🟢)
• DII Cash: +₹1,204 Cr (BUYING 🟢)
• FII Futures: NET LONG ₹2,400 Cr 🟢

━━━━━━━━━━━━━━━━━━━━━━
📈 STOCK ANALYSIS

1️⃣ NALCO — ₹386.10
   Score: 🟢13 🟡5 🔴3 | Grade: A
   Verdict: BUY | Confidence: 7/10
   Entry: ₹383-387 | Target: ₹405 | SL: ₹372
   🔑 Catalyst: Aluminium supply squeeze
   ⚠️ Risk: FII selling pressure

2️⃣ BEL — ₹405.20
   Score: 🟢15 🟡3 🔴3 | Grade: A+
   Verdict: STRONG BUY | Confidence: 8/10
   Entry: ₹400-408 | Target: ₹435 | SL: ₹390
   🔑 Catalyst: ₹1,660Cr new defence orders
   ⚠️ Risk: Ceasefire = defence dip

3️⃣ HINDZINC — ₹502.15
   Score: 🟢9 🟡4 🔴8 | Grade: C+
   Verdict: HOLD/WAIT | Confidence: 4/10
   📌 Watch Apr 17 earnings before entering
   Entry on dip: ₹490-495 | Target: ₹535 | SL: ₹478

━━━━━━━━━━━━━━━━━━━━━━
🔐 SECRET SIGNALS TODAY
• Max Pain: NALCO ₹380 (drift UP ✅)
• PCR: 0.72 (mild fear = contrarian buy)
• Delivery%: BEL 68% (operator accumulation 🔥)
• FII Futures: Net Long = market positive ✅

━━━━━━━━━━━━━━━━━━━━━━
⚡ TODAY'S ACTION
✅ BEL: Open > ₹408 → ENTER
✅ NALCO: Open > ₹385 → ENTER
⏳ HINDZINC: WAIT for Apr 17
❌ Don't trade if VIX > 25

⚠️ Not SEBI advice. Educational only.
```

---

## 7. ⏰ SCHEDULER & AUTOMATION

```python
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz

IST = pytz.timezone('Asia/Kolkata')
scheduler = BlockingScheduler(timezone=IST)

# Morning report — before market opens
@scheduler.scheduled_job('cron', hour=8, minute=30)
def morning_report():
    """Full 21-condition analysis with pre-market data"""
    run_full_analysis(session='morning')
    send_telegram_report(report_type='morning')

# Evening report — after market closes
@scheduler.scheduled_job('cron', hour=16, minute=15)
def evening_report():
    """Post-market analysis with final delivery % and FII data"""
    run_full_analysis(session='evening')
    send_telegram_report(report_type='evening')

# Market hours alert — if any stock hits alert price
@scheduler.scheduled_job('cron', hour='9-15', minute='*/15', day_of_week='mon-fri')
def intraday_price_alert():
    """Check price alerts every 15 minutes during market hours"""
    check_price_alerts()

# FII data refresh (published after 5 PM by NSE)
@scheduler.scheduled_job('cron', hour=17, minute=30)
def refresh_fii_data():
    """Fetch final FII/DII data published by NSE after market"""
    update_fii_data_cache()

scheduler.start()
```

---

## 8. 📁 PROJECT FOLDER STRUCTURE

```
stock_analysis_bot/
│
├── 📄 main.py                    # Entry point + scheduler
├── 📄 config.py                  # API keys, stock list, settings
├── 📄 requirements.txt
├── 📄 Dockerfile
├── 📄 docker-compose.yml
├── 📄 .env                       # Secret keys (gitignored)
│
├── 📁 data/
│   ├── fetchers/
│   │   ├── nse_fetcher.py        # NSE India real-time data
│   │   ├── yfinance_fetcher.py   # Yahoo Finance data
│   │   ├── fii_fetcher.py        # FII/DII data
│   │   ├── commodity_fetcher.py  # Zinc, Aluminium, Silver, Crude
│   │   ├── news_fetcher.py       # Geopolitical news
│   │   └── bse_fetcher.py        # BSE insider/promoter data
│   └── cache/
│       └── redis_cache.py        # Cache repeated API calls
│
├── 📁 analysis/
│   ├── technical.py              # Checks 1-6 (DMA, MACD, RSI, etc.)
│   ├── fundamental.py            # Checks 7-10 (Earnings, Margin, PE)
│   ├── macro.py                  # Checks 11-15 (FII, VIX, Commodity)
│   ├── secret_strategies.py      # Checks 16-21 (Max Pain, PCR, etc.)
│   └── scorer.py                 # Combine all 21 → final score
│
├── 📁 ai/
│   └── groq_engine.py            # Groq AI decision + summary
│
├── 📁 bot/
│   ├── telegram_bot.py           # Bot commands + handlers
│   ├── report_builder.py         # Format morning/evening report
│   └── alert_manager.py          # Price alerts
│
├── 📁 scheduler/
│   └── job_runner.py             # APScheduler jobs
│
└── 📁 logs/
    └── analysis_log.json         # Store all analysis history
```

---

## 9. ⚙️ ENVIRONMENT SETUP

### requirements.txt
```
yfinance==0.2.36
pandas==2.2.0
pandas-ta==0.3.14b
requests==2.31.0
beautifulsoup4==4.12.3
python-telegram-bot==21.0
groq==0.4.2
apscheduler==3.10.4
pytz==2024.1
redis==5.0.1
python-dotenv==1.0.0
lxml==5.1.0
fake-useragent==1.4.0
```

### .env file
```
GROQ_API_KEY=your_groq_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
NEWS_API_KEY=your_newsapi_key
REDIS_URL=redis://localhost:6379
```

### config.py
```python
WATCHLIST = [
    "NATIONALUM.NS",   # NALCO
    "HINDZINC.NS",     # Hindustan Zinc
    "BEL.NS",          # Bharat Electronics
    "NTPC.NS",         # NTPC
    "ICICIBANK.NS",    # ICICI Bank
    "PRECWIRE.NS",     # Precision Wires
]

INDUSTRY_PE = {
    "Basic Materials": 12,
    "Industrials": 28,
    "Financial Services": 18,
    "Utilities": 20,
    "Technology": 35,
    "Consumer Cyclical": 25,
}

REPORT_TIMES = {
    "morning": "08:30",
    "evening": "16:15",
}
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  stock_bot:
    build: .
    env_file: .env
    restart: always
    depends_on:
      - redis
    volumes:
      - ./logs:/app/logs

  redis:
    image: redis:alpine
    restart: always
```

---

## 10. 📅 PHASE-WISE IMPLEMENTATION PLAN

### Phase 1 — Foundation (Week 1-2)
- [ ] Setup Python project structure
- [ ] Implement yfinance data fetcher
- [ ] Implement Technical checks 1-6 (DMA, MACD, RSI, MA, 52W, Trend)
- [ ] Test with NALCO and HINDZINC
- [ ] Basic Telegram bot with `/analyze` command

### Phase 2 — Fundamental & Macro (Week 3-4)
- [ ] Implement fundamental checks 7-10 (Earnings, Margins, Debt, PE)
- [ ] Implement NSE FII/DII fetcher with session handling
- [ ] Implement India VIX and Nifty trend check
- [ ] Commodity price fetcher (Zinc, Aluminium, Silver, Crude)
- [ ] Add morning scheduler (8:30 AM)

### Phase 3 — Secret Strategies (Week 5-6)
- [ ] NSE option chain fetcher + Max Pain calculator
- [ ] NSE Bhav Copy delivery % fetcher
- [ ] PCR calculator from option chain data
- [ ] BSE promoter/insider activity scraper
- [ ] FII Futures position fetcher
- [ ] 52W Reversal formula implementation

### Phase 4 — Groq AI Integration (Week 7)
- [ ] Groq API setup
- [ ] Prompt engineering for stock decisions
- [ ] JSON response parsing
- [ ] Confidence score calculation
- [ ] Entry/Target/SL generation

### Phase 5 — Report & Telegram Polish (Week 8)
- [ ] Morning report builder (full format)
- [ ] Evening report builder (end of day summary)
- [ ] All Telegram commands working
- [ ] Price alert system
- [ ] Error handling + fallback logic

### Phase 6 — Deploy on Hetzner/Coolify (Week 9)
- [ ] Dockerize the application
- [ ] Setup on Hetzner VPS via Coolify
- [ ] Redis cache setup
- [ ] Logging + monitoring
- [ ] Test full morning-evening cycle
- [ ] Go live!

---

## 11. 🚨 RISK & DISCLAIMER LOGIC

```python
DISCLAIMER = """
⚠️ IMPORTANT DISCLAIMER
This analysis is generated by an automated bot for educational purposes only.
This is NOT SEBI registered investment advice.
Always do your own research before trading.
Past performance does not guarantee future returns.
The bot creator is not responsible for any trading losses.
"""

def add_disclaimer_to_report(report):
    return report + "\n" + DISCLAIMER
```

---

## 12. 📊 SCORING SYSTEM

```python
SIGNAL_WEIGHTS = {
    "STRONG_BUY":   2,
    "BULLISH":      1,
    "NEUTRAL":      0,
    "CAUTION":     -1,
    "BEARISH":     -1,
    "STRONG_SELL": -2,
}

GRADE_SCALE = {
    (18, 21): "A+",   # Strong Buy
    (15, 17): "A",    # Buy
    (12, 14): "B+",   # Moderate Buy
    (9,  11): "B",    # Watchlist
    (6,   8): "C",    # Neutral
    (0,   5): "D",    # Avoid
}
```

---

## 📌 IMPORTANT NOTES

1. **NSE API requires session management** — always hit homepage first to get cookies before hitting data APIs
2. **Rate limiting** — add `time.sleep(1)` between NSE API calls to avoid IP ban
3. **Market holidays** — add NSE holiday calendar check before running analysis
4. **Option chain data** — only available for F&O stocks; skip Max Pain for non-F&O stocks like PRECWIRE
5. **Groq free tier** — 14,400 tokens/minute; sufficient for 6 stocks × 2 reports/day
6. **Backup data source** — if NSE API fails, fallback to yfinance for price data
7. **Redis caching** — cache FII/DII and option chain data for 30 minutes to avoid redundant calls

---

*Planning document version 1.0 | Created for Ezhil's Stock Analysis Bot Project*
*Stack: Python 3.11 + Groq AI (llama3-70b) + Telegram Bot + Hetzner VPS + Coolify + Docker*
