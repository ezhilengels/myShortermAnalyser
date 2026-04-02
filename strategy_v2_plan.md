# Strategy V2 Plan

This document is a planning-only blueprint for a future Version 2 of the bot.
It does not change the current 21-check implementation.

## Goal

Evaluate the proposed new strategies 22-38 and define:

- what is realistically worth building
- what data sources are required
- what should be added first
- what should remain experimental

## Planning Principles

- Prefer stock-specific signals over broad market noise.
- Prefer stable, repeatable data sources over clever but flaky ones.
- Treat live-session signals separately from end-of-day signals.
- Do not add too many weak checks just to increase count.
- A smaller set of reliable checks is better than many fragile ones.

## Strategy Review

### Strategy 22 — Mutual Fund Holding Change

- Idea: track monthly/quarterly MF ownership trend.
- Value: high
- Source quality: medium to high
- Difficulty: medium
- Notes:
  - very useful for stock-specific institutional accumulation
  - should use monthly/quarterly holding trend, not one isolated snapshot
  - works best as a medium-term conviction signal
- Recommendation: build
- Suggested signal:
  - MF holding rising 2-3 periods with stable/positive price structure = bullish
  - MF holding falling while price weak = bearish

### Strategy 23 — Block Deal / Bulk Deal Scanner

- Idea: detect meaningful institutional entry/exit via block or bulk deals.
- Value: high
- Source quality: medium
- Difficulty: medium
- Notes:
  - very useful if filtered properly
  - raw block deals are noisy unless filtered by size, price premium/discount, and participant type
  - should not trigger on tiny or routine deals
- Recommendation: build
- Suggested signal:
  - premium buy-side block deal with meaningful size = bullish
  - repeated discount sell-side deals = caution/bearish

### Strategy 24 — FII Sector Rotation

- Idea: detect FII movement into or out of sectors.
- Value: high
- Source quality: medium
- Difficulty: medium to high
- Notes:
  - very good as a sector-level confirmation layer
  - stronger for metals, banking, IT, energy than for isolated stock calls
  - should support sector-alignment logic, not replace stock quality logic
- Recommendation: build
- Suggested signal:
  - 2-3 weeks of sector-level foreign inflow plus stock outperformance = bullish sector tailwind

### Strategy 25 — Candlestick Pattern Recognition

- Idea: detect hammer, engulfing, doji, etc.
- Value: medium
- Source quality: high
- Difficulty: low to medium
- Notes:
  - easy to build
  - dangerous if used standalone
  - should only matter near support/resistance or after trend exhaustion
- Recommendation: build later, as context only

### Strategy 26 — Volume Price Trend (VPT)

- Idea: use VPT to detect hidden accumulation/distribution.
- Value: medium to high
- Source quality: high
- Difficulty: low
- Notes:
  - simple to compute
  - useful when price is flat but accumulation is building
  - better than raw volume alone
- Recommendation: build

### Strategy 27 — Supertrend Indicator

- Idea: daily Supertrend for clean swing signals.
- Value: high
- Source quality: high
- Difficulty: low to medium
- Notes:
  - popular and practical
  - should integrate well with DMA and MACD
  - useful as a clean trend filter
- Recommendation: build

### Strategy 28 — Support & Resistance Zones

- Idea: auto-calculate support/resistance zones.
- Value: high
- Source quality: high
- Difficulty: medium
- Notes:
  - very useful if zone-based, not single-price-based
  - better to use swing highs/lows and pivots together
  - can support breakout trap logic and entry planning
- Recommendation: build

### Strategy 29 — Dow Jones / SGX Nifty Pre-market Signal

- Idea: use overnight US/global index moves to infer Indian open.
- Value: medium
- Source quality: medium
- Difficulty: medium
- Notes:
  - useful only for morning reports
  - not very useful for long-horizon stock conviction
  - should remain context-only
- Recommendation: optional, context only

### Strategy 30 — Dollar Index (DXY) Impact

- Idea: rising dollar hurts emerging-market flows.
- Value: high
- Source quality: high
- Difficulty: low
- Notes:
  - strong macro context signal
  - especially relevant for FII-sensitive sectors
  - should be context, not direct stock conviction
- Recommendation: build

### Strategy 31 — US 10-Year Bond Yield

- Idea: higher yields pull capital away from EM risk assets.
- Value: high
- Source quality: high
- Difficulty: low
- Notes:
  - strong macro overlay
  - useful with DXY and VIX
  - should remain context-only
- Recommendation: build

### Strategy 32 — China PMI / Manufacturing Data

- Idea: China demand heavily influences metals.
- Value: high for metal stocks, low elsewhere
- Source quality: medium
- Difficulty: medium
- Notes:
  - very useful for NALCO, HINDZINC, HINDALCO, copper-linked names
  - should be sector-specific, not global stock logic
  - scraping risk exists depending on source
- Recommendation: build if metals remain a focus

### Strategy 33 — News Sentiment Score

- Idea: use AI to score stock-specific headlines.
- Value: medium
- Source quality: medium
- Difficulty: medium
- Notes:
  - useful if limited to recent stock-specific headlines
  - can become noisy or expensive if overused
  - should never dominate the verdict
- Recommendation: build later, context only

### Strategy 34 — Google Trends

- Idea: search interest as retail attention proxy.
- Value: medium
- Source quality: medium
- Difficulty: medium
- Notes:
  - more useful as a warning/froth indicator than a buy engine
  - can help detect retail FOMO
- Recommendation: optional, context only

### Strategy 35 — Short Interest / Short Squeeze Potential

- Idea: detect rising price with elevated shorting.
- Value: medium to high
- Source quality: medium
- Difficulty: medium to high
- Notes:
  - powerful if source quality is good
  - dangerous if short data is incomplete or delayed
- Recommendation: experimental

### Strategy 36 — Bollinger Band Squeeze

- Idea: volatility compression before expansion.
- Value: medium to high
- Source quality: high
- Difficulty: low
- Notes:
  - simple and useful
  - should be combined with volume and trend
- Recommendation: build

### Strategy 37 — Relative Strength vs Nifty

- Idea: stock outperforming Nifty signals leadership.
- Value: high
- Source quality: high
- Difficulty: low
- Notes:
  - very strong, practical signal
  - overlaps with the new sector-alignment idea but is still independently useful
- Recommendation: build

### Strategy 38 — 52-Week High Breakout Club

- Idea: new 52W high with strong volume confirms institutional momentum.
- Value: high
- Source quality: high
- Difficulty: low
- Notes:
  - strong momentum signal
  - should use volume confirmation and avoid weak breakouts
- Recommendation: build

## Recommended Priority Order

### Phase 1 — Best Value, Low/Medium Risk

- Strategy 27 — Supertrend Indicator
- Strategy 28 — Support & Resistance Zones
- Strategy 30 — Dollar Index (DXY)
- Strategy 31 — US 10-Year Bond Yield
- Strategy 36 — Bollinger Band Squeeze
- Strategy 37 — Relative Strength vs Nifty
- Strategy 38 — 52-Week High Breakout Club

Reason:
- strong signal quality
- reliable data
- low-to-medium implementation complexity

### Phase 2 — Strong India/Institutional Edge

- Strategy 22 — Mutual Fund Holding Change
- Strategy 23 — Block Deal / Bulk Deal Scanner
- Strategy 24 — FII Sector Rotation
- Strategy 26 — Volume Price Trend (VPT)
- Strategy 32 — China PMI / Manufacturing Data

Reason:
- strong edge if implemented well
- more data-source work required
- better after Phase 1 stabilizes

### Phase 3 — Context / Experimental

- Strategy 25 — Candlestick Pattern Recognition
- Strategy 29 — Dow Jones / SGX Nifty Pre-market Signal
- Strategy 33 — News Sentiment Score
- Strategy 34 — Google Trends
- Strategy 35 — Short Interest / Short Squeeze Potential

Reason:
- useful, but more fragile or easier to overuse
- should not be allowed to drive final conviction

## Suggested Replacements vs Additions

If V2 keeps a fixed number of checks, the best replacements are:

- replace weak or broad macro-only checks first
- replace noisy live-session checks if they remain unstable
- keep high-quality core trend/fundamental checks

Best candidates to replace in V2 if needed:

- current geopolitical/news scoring
- weak derivative context if still unstable
- low-value market-wide flow checks

Best candidates to keep:

- DMA, MACD, RSI, MA alignment
- growth, margins, debt, valuation
- commodity tailwind
- sector alignment
- 52W logic

## Data Source Suggestions

### Stable / Preferred

- Yahoo Finance
  - price history
  - indices
  - DXY
  - US 10Y
- Screener
  - Indian fundamentals
  - shareholding trends
- NSE
  - block deals
  - derivatives
  - delivery data

### Higher-Risk / Needs Care

- AMFI
  - mutual fund holdings may need careful parsing and normalization
- Investing.com or similar for China PMI
  - scraping fragility risk
- Google Trends / pytrends
  - dependency and quota sensitivity
- short-interest style NSE data
  - verify availability and consistency before relying on it

## Proposed V2 Architecture

### Category A — Core Conviction

- Supertrend
- Relative Strength vs Nifty
- Support/Resistance Zones
- 52W High Breakout Club
- VPT
- Mutual Fund Holding Change
- Block Deal Scanner

### Category B — Sector / Macro Context

- FII Sector Rotation
- DXY Impact
- US 10Y Yield
- China PMI
- Global Sentiment

### Category C — Tactical / Experimental

- Candlestick Patterns
- Bollinger Band Squeeze
- Pre-market Global Signal
- News Sentiment
- Google Trends
- Short Squeeze Potential

## Recommended Build Order for Version 2

1. Supertrend
2. Relative Strength vs Nifty
3. 52-Week High Breakout Club
4. Support & Resistance Zones
5. DXY
6. US 10-Year Yield
7. VPT
8. Mutual Fund Holding Change
9. Block Deal Scanner
10. FII Sector Rotation
11. China PMI
12. Bollinger Band Squeeze
13. Candlestick Patterns
14. News Sentiment
15. Google Trends
16. Short Squeeze Potential
17. Pre-market Global Signal

## Final Recommendation

Do not build all of 22-38 at once.

Best V2 approach:

- first build 5-7 strong, data-stable additions
- test them
- only then add experimental sentiment or alternative-data ideas

If the goal is maximum accuracy, the best V2 shortlist is:

- 22 Mutual Fund Holding Change
- 23 Block Deal / Bulk Deal Scanner
- 24 FII Sector Rotation
- 27 Supertrend
- 28 Support & Resistance Zones
- 30 Dollar Index (DXY)
- 31 US 10-Year Bond Yield
- 36 Bollinger Band Squeeze
- 37 Relative Strength vs Nifty
- 38 52-Week High Breakout Club
