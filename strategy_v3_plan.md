# Strategy V3 Plan

This document is planning-only for a future Version 3 of the bot.
It does not modify the current 21-check core or the current additional-signal layer.

## Goal

Build a large-universe stock screener that can scan a basket like:

- Nifty 200
- Nifty 500
- sector-specific curated universes

and then produce a daily AI-assisted shortlist of the top 3 ideas.

This should live as a separate V3 flow and a separate Telegram command:

- `/stocktips`

The current `/analyze` and current report flow should remain unchanged.

## Freeze Rule

V1 / current bot stays frozen:

- `21 scored checks` remain the main current engine
- `additional non-scoring signals` remain as a separate layer
- no V3 scoring or stock-universe scan should alter the current single-stock logic

V3 should be built as a parallel pipeline, not as a rewrite of the current bot.

## V3 Product Idea

`/stocktips` should answer:

- out of a large stock universe, which are the best 3 stocks today?

This is different from `/analyze`:

- `/analyze` = deep dive on one stock
- `/stocktips` = ranking engine across many stocks

## Core V3 Approach

Use a 3-stage pipeline:

### Stage 1 — Pre-Filter

Purpose:

- eliminate weak candidates quickly
- reduce API load
- reduce AI cost

Suggested filters:

- price above `200 DMA`
- price above `50 DMA`
- average daily traded value above minimum liquidity threshold
- current volume above recent average volume
- optional: exclude stocks with missing core data

Output:

- a reduced candidate list from `200-500` stocks down to maybe `20-60`

### Stage 2 — Strategy Validation

Purpose:

- run a deeper scoring engine only on filtered candidates

Suggested scoring basis:

- do not run all expensive/fragile checks here
- use a dedicated V3 scoring subset with the strongest signals only

Recommended V3 scoring groups:

- `Trend`
  - DMA Position
  - MACD
  - RSI
  - Moving Avg Alignment
  - Supertrend
  - Relative Strength
- `Breakout / Participation`
  - 52W High Breakout Club
  - VPT
  - Support / Resistance context
  - Breakout Failure Trap
- `Fundamentals`
  - Earnings Growth
  - Margin / ROE
  - Debt
  - Valuation
- `Context`
  - Sector Alignment
  - Commodity Tailwind where relevant
  - China PMI for metal-linked names
  - News Sentiment

Important:

- do not let weak source-dependent checks dominate V3 ranking
- derivative and niche context checks should be low-weight or optional

Output:

- ranked list of top candidates, for example top `10`

### Stage 3 — AI Finalization

Purpose:

- take the highest-scoring candidates and choose the final top 3
- AI should rank, not invent

AI should receive:

- symbol
- sector
- score
- strongest positive checks
- strongest risks
- trend summary
- valuation summary
- confidence

AI should return:

- rank `1-3`
- one-line reason for each
- risk note for each

Important AI rule:

- AI should only choose from the top validated candidates
- AI should not override weak evidence into a top-3 pick

## Recommended V3 Architecture

Create a new V3 path with separate files, for example:

- `v3/universe_loader.py`
- `v3/prefilter.py`
- `v3/ranker.py`
- `v3/ai_selector.py`
- `v3/stocktips_service.py`

Current code should remain untouched as much as possible.

Best design principle:

- V3 reuses existing fetchers and indicators where safe
- V3 has its own orchestration and ranking logic
- V3 does not directly mutate V1 scoring rules

## `/stocktips` Command Design

Suggested flow:

1. load configured universe
2. run pre-filter
3. run V3 validation on survivors
4. pick top 10
5. send top 10 to AI for ranking
6. return final top 3 with concise rationale

Suggested Telegram response:

- `Top 3 stock ideas today`
- rank 1, 2, 3
- entry context
- why picked
- key risk

Optional second section:

- `Near misses / watchlist`

## Universe Design

V3 should support multiple universes:

- `nifty200`
- `nifty500`
- `metals`
- `banks`
- `custom`

Best approach:

- store universes as separate config files or JSON lists
- avoid hardcoding 500 symbols inside one Python file

## Performance Strategy

To scan a large universe efficiently:

- use `concurrent.futures.ThreadPoolExecutor` for network-bound fetches
- batch work in stages
- cache aggressively
- avoid running expensive fetchers on every stock

Recommended pattern:

- Stage 1:
  - fetch only price history + light info
- Stage 2:
  - fetch fundamentals and additional context only for survivors
- Stage 3:
  - AI only for top 10

## Data Discipline

For V3, not all checks should be used equally.

Use only stronger signals for ranking.

Recommended high-trust V3 inputs:

- DMA Position
- MACD
- RSI
- Moving Avg Alignment
- Relative Strength
- Supertrend
- 52W High Breakout Club
- VPT
- Earnings Growth
- Margin / ROE
- Debt
- Valuation
- Sector Alignment

Use as context only:

- News Sentiment
- DXY
- US 10Y Yield
- Dow / pre-market signal
- Google Trends
- China PMI

Use very lightly or exclude from V3 ranking:

- block/bulk deals
- MF holding drift
- short squeeze proxy
- derivatives-heavy signals

## Confidence System

V3 should produce:

- `technical_score`
- `fundamental_score`
- `context_score`
- `total_score`
- `confidence`

Top-3 selection should require:

- positive total score
- minimum confidence threshold
- low missing critical data

Do not allow:

- low-confidence stocks in final top 3 unless the universe is weak overall

## Risk Controls

V3 should explicitly exclude:

- illiquid stocks
- highly gapped / broken data names
- symbols with too many unavailable critical fields

Optional future controls:

- max 1 stock per sector in top 3
- exclude if broad market risk is too high
- exclude if earnings event is too close

## Scheduling

Best timing ideas:

- morning run before market open for fresh shortlist
- optional evening run for next-day prep

Suggested V3 schedule:

- pre-open shortlist around `8:15-8:30 AM IST`

## AI Usage Rules

AI should be used only after quantitative narrowing.

Good V3 AI role:

- rank top 10
- compare similar candidates
- add risk/reward framing

Bad V3 AI role:

- scan all 500 stocks
- override weak quantitative ranking

## Recommended V3 Rollout

### Phase 1

Build non-AI screener first:

- universe loader
- pre-filter
- ranking engine
- top 10 output

Reason:

- easier to validate
- cheaper
- more transparent

### Phase 2

Add AI finalizer:

- top 10 in
- top 3 out

### Phase 3

Add `/stocktips` Telegram command

### Phase 4

Add scheduling and historical score validation

## What V3 Should Not Do

- should not merge into the current 21-score engine immediately
- should not run expensive deep checks on all 500 stocks
- should not let AI pick stocks outside the validated shortlist
- should not rely heavily on weak or flaky sources for universe-wide scanning

## Practical Recommendation

The best V3 shape is:

- `large universe quick scan`
- `reduced shortlist deep score`
- `AI ranking on top 10`
- `/stocktips` returns final top 3

This is the safest, most scalable, and most realistic approach.

## Suggested First V3 Scope

Start with:

- universe: `Nifty 200`
- pre-filter:
  - price above 200DMA
  - price above 50DMA
  - volume above 20-day average
- validation:
  - strongest 10-14 signals only
- AI:
  - final ranking of top 10
- output:
  - final top 3

This is enough to prove the product before scaling to `Nifty 500`.

## `/stocktips` Planning Summary

Command:

- `/stocktips`

Behavior:

- scan broad universe
- shortlist candidates
- score them
- AI ranks top 10
- return top 3

Current bot impact:

- none
- current V1 remains stable

