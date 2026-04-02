# Stock Analysis Bot — Strategy V4 🚀

An advanced, automated Indian stock analysis bot that combines Technical, Fundamental, Macro, and Secret Strategy signals with **Multi-Model Intrinsic Valuation (Strategy V4)** and **Groq AI** decision making.

## 🌟 Key Features
- **33-Check Analysis**: Covers Technical (6), Fundamental (5), Macro (5), and 17+ Additional Signals.
- **Strategy V4 Valuation**: Calculates Intrinsic Value using 6 models (Graham, DCF, Lynch, Buffett, EPV, DDM) and automatically selects the best fit by sector.
- **Groq AI Integration**: Uses `llama-3.3-70b` to synthesize all signals into a plain-English trading verdict with Entry, Target, and SL.
- **Telegram Bot**: Full interactive control via `/analyze`, `/stocktips`, `/valuation`, and more.
- **Portfolio Audit**: Specialized tool to audit your holdings using intrinsic value benchmarks.
- **Automated Reports**: Scheduled Morning (8:30 AM) and Evening (4:15 PM) market wraps.

## 🛠️ Commands
- `/analyze SYMBOL` — Full 33-check analysis + AI verdict.
- `/value SYMBOL` — Deep-dive V4 Intrinsic Valuation for a specific stock.
- `/valuation [universe]` — Scan an entire universe (e.g., nifty50, watchlist) and rank by Margin of Safety.
- `/stocktips [universe]` — Run the V3 pipeline to find high-conviction swing trades.
- `/report` — Get the latest full market report.
- `/fii`, `/vix`, `/commodity` — Quick snapshots of market context.
- `/alert SYMBOL PRICE [above|below]` — Set real-time price alerts.

## 🚀 Getting Started
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure environment**:
   Create a `.env` file with your `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, and `NEWS_API_KEY`.
3. **Run the Bot**:
   ```bash
   python3 main.py
   ```

## 📊 V4 Valuation Modes
- **Single Stock**: `python3 valuation_only.py NALCO`
- **Universe Scan**: `python3 main.py --valuation nifty50`
- **Portfolio Audit**: `python3 v4_portfolio_audit.py`

Built-in Universes
   - watchlist: Evaluates the stocks specifically listed in your config.py.
   - nifty50: Evaluates the 50 major stocks of the NSE.
   - nifty100: Evaluates the top 100 NSE stocks.
   - nifty200: Evaluates the top 200 NSE stocks.
   - nifty500: Evaluates the top 500 NSE stocks.
   - custom & custom1: These point to data/universes/custom.txt and custom1.txt,
     respectively, which you can edit with your own lists.

  Specialized Groups (Experimental)
   - metals: (Currently points to data/universes/metals.txt).
   - banks: (Currently points to data/universes/banks.txt).

## 📜 Disclaimer
This tool is for educational purposes only. Not SEBI registered advice. Trading involves risk.
