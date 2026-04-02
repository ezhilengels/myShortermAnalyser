# Strategy V4: Multi-Model Intrinsic Valuation Plan

## 1. Objective
Implement a sophisticated valuation engine that goes beyond simple PE ratios by calculating "Intrinsic Value" (IV) using six distinct financial models. The engine will automatically select the most appropriate model based on the stock's sector and characteristics.

## 2. Core Formulas to Implement

### Formula 1: Benjamin Graham (1974 Revised)
*   **Target:** General manufacturing and stable companies.
*   **Logic:** `IV = EPS * (8.5 + 2g) * (4.4 / Y)`
*   **Inputs:** 
    *   `EPS`: Trailing 12 Months (TTM).
    *   `g`: 5-year historical EPS CAGR.
    *   `Y`: Current 10-Year G-Sec yield (Default: 7.0%).

### Formula 2: 2-Stage DCF (Discounted Cash Flow)
*   **Target:** Large stable companies (FMCG, Blue chips).
*   **Logic:** 5 years of high growth + 5 years of moderate growth + Terminal Value.
*   **Inputs:**
    *   `FCF`: Net Profit + Depreciation - Capex.
    *   `r`: Discount rate (Default: 12-15% for India).
    *   `g_terminal`: 5-6%.

### Formula 3: Peter Lynch (PEG Based)
*   **Target:** High-growth IT and Pharma.
*   **Logic:** `IV = EPS * Growth Rate` (where Fair P/E = Growth Rate).
*   **Inputs:**
    *   `EPS`: TTM.
    *   `Growth Rate`: Expected or historical 3-5 year CAGR.

### Formula 4: Buffett Owner Earnings
*   **Target:** Asset-heavy companies with high depreciation.
*   **Logic:** `Owner Earnings = Net Profit + Depreciation - Maintenance Capex`.
*   **Logic:** `IV = Owner Earnings / (r - g)`.

### Formula 5: Earnings Power Value (EPV)
*   **Target:** Value stocks where growth is uncertain.
*   **Logic:** `EPV = Adjusted EBIT * (1 - tax_rate) / WACC`.
*   **Assumption:** Zero growth; calculates if the current price is supported by current earnings alone.

### Formula 6: Dividend Discount Model (DDM)
*   **Target:** PSUs and high-dividend payers (e.g., Coal India, ITC).
*   **Logic:** `IV = D1 / (r - g)`.
*   **Inputs:**
    *   `D1`: Expected next-year dividend.

---

## 3. Implementation Strategy

### A. Data Fetching & Validation (Critical)
The engine must check for the presence of all required variables before attempting a calculation.
*   **Required Fields:** `EPS`, `Net Profit`, `Depreciation`, `Capex`, `Dividends`, `EBIT`, `Tax Rate`.
*   **Validation:** If any field is missing or `0` (where it shouldn't be), the model must return: `UNAVAILABLE: Missing [Field Name]`.
*   **Sources:** Use `Screener` as the primary source for Cash Flow (Capex/Depreciation) and `yfinance` for live pricing and sector info.

### B. Sector-Based Model Selection
The bot will use the following mapping:
| Stock Type | Primary Model | Secondary Model |
| :--- | :--- | :--- |
| **Large Stable (FMCG)** | DCF | DDM |
| **IT / Pharma / Growth** | Peter Lynch | DCF |
| **PSUs / Mature** | DDM | EPV |
| **Cyclicals (Steel/Cement)**| Graham | Owner Earnings |
| **Financials (Banks)** | P/B + ROE | Graham |

### C. The "Buffett Check" (Sanity Filter)
Every analysis will include the **Earnings Yield vs Bond Yield** check:
*   `Earnings Yield = (EPS / Current Price) * 100`
*   **Verdict:** Attractive if `Earnings Yield > G-Sec Yield (7%)`.

---

## 4. Margin of Safety & Verdicts
*   **UNDERVALUED:** CMP ≤ 70% of IV (30% Margin of Safety).
*   **FAIR VALUE:** 70% < CMP ≤ 100% of IV.
*   **OVERVALUED:** CMP > IV.

## 5. File Structure Changes
1.  **Create** `analysis/valuation_v4.py`: Contains the 6 formulas and the selection logic.
2.  **Update** `config.py`: Add constants for `G_SEC_YIELD`, `DISCOUNT_RATE_INDIA`, and `WACC_DEFAULT`.
3.  **Update** `bot/report_builder.py`: To display the "Intrinsic Value" and the specific formula used.

## 6. Success Criteria
*   The bot identifies specific reasons (missing data) when a valuation cannot be performed.
*   No more "mostly failing" generic PE signals; instead, model-specific valuations.
*   Transparent output: "Intrinsic Value (DCF): ₹1200 | CMP: ₹900 | Margin of Safety: 25%".
