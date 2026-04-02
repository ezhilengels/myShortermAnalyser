"""
v4/valuation_data.py — Specialized data gatherer for V4 intrinsic valuation.
Handles field validation and maps data from multiple fetchers.
"""

import logging
from typing import Dict, Any, Optional

from data.fetchers.yfinance_fetcher import get_ticker_info, get_financials
from data.fetchers.screener_fetcher import get_screener_snapshot

logger = logging.getLogger(__name__)

def gather_valuation_data(symbol: str) -> Dict[str, Any]:
    """
    Gather and validate all fields required for the 6 valuation models.
    Returns a dict of values or error flags for missing data.
    """
    data = {
        "symbol": symbol,
        "valid": True,
        "missing_fields": [],
        "errors": []
    }
    
    try:
        # 1. Fetch from yfinance
        logger.info(f"📡 Fetching Yahoo Finance info for {symbol}...")
        info = get_ticker_info(symbol)
        if not info:
            data["valid"] = False
            data["errors"].append("Yahoo Finance info not available")
            return data
            
        data["price"] = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        data["eps_ttm"] = info.get("trailingEps") or 0.0
        data["dividend_yield"] = (info.get("dividendYield") or 0.0) * 100
        data["dividend_rate"] = info.get("dividendRate") or 0.0
        data["sector"] = info.get("sector", "Unknown")
        data["industry"] = info.get("industry", "Unknown")
        data["market_cap"] = info.get("marketCap") or 0.0
        data["book_value"] = info.get("bookValue") or 0.0
        
        # 2. Fetch from Screener (Primary source for Growth & FCF)
        logger.info(f"🌐 Fetching Screener snapshot for {symbol}...")
        screener = get_screener_snapshot(symbol)
        if screener and screener.get("source_ok"):
            logger.info(f"✅ Screener data acquired for {symbol}. Processing financials...")
            if not data["book_value"]:
                data["book_value"] = screener.get("ratios", {}).get("book_value") or 0.0
            # Growth rates
            sales_growth = screener.get("growth", {}).get("annual_sales", {})
            profit_growth = screener.get("growth", {}).get("annual_profit", {})
            
            data["growth_5y"] = profit_growth.get("cagr") or sales_growth.get("cagr") or 0.0
            data["growth_yoy"] = profit_growth.get("yoy") or 0.0
            
            # Detailed Financials
            pl = screener.get("profit_loss", {})
            cf = screener.get("cash_flow", {})
            
            data["net_profit"] = profit_growth.get("latest") or 0.0
            data["pbt"] = pl.get("pbt_latest") or 0.0
            data["tax_rate"] = (pl.get("tax_latest") or 0.0) / 100
            data["interest"] = pl.get("interest_latest") or 0.0
            data["depreciation"] = pl.get("depreciation_latest") or 0.0
            data["capex"] = cf.get("capex_latest") or 0.0
            
            # 2.2 Proxy Fallbacks for missing Depreciation/Capex (common in some bank/PSU reports)
            # If depreciation is 0, use a small proxy (e.g., 10% of Net Profit) to allow models to work
            if data["depreciation"] <= 0 and data["net_profit"] > 0:
                data["depreciation"] = data["net_profit"] * 0.10
                
            # If capex is 0, assume it is at least 50% of depreciation (Maintenance Capex)
            if data["capex"] <= 0 and data["depreciation"] > 0:
                data["capex"] = data["depreciation"] * 0.50

            data["ebit"] = data["pbt"] + data["interest"]
            
            # FCF Calculation: Cash from Operations - Capex
            fcf_crores = cf.get("operating_latest", 0.0) - data["capex"]
            
            # Owner Earnings: Net Profit + Depreciation - Maintenance Capex
            # Estimating Maintenance Capex as 80% of Depreciation if Capex is higher, else actual Capex
            m_capex = min(data["capex"], data["depreciation"] * 0.8) if data["depreciation"] > 0 else data["capex"]
            oe_crores = data["net_profit"] + data["depreciation"] - m_capex
            
            # 2.5 Normalization to Per-Share (Screener uses Crores, yfinance Price is per share)
            # Factor = Price / (Market Cap in Crores)
            mc_crores = (screener.get("ratios", {}).get("market_cap_cr") or (data["market_cap"] / 10_000_000))
            if mc_crores > 0:
                share_factor = data["price"] / mc_crores
                data["fcf"] = fcf_crores * share_factor
                data["owner_earnings"] = oe_crores * share_factor
                data["ebit"] = data["ebit"] * share_factor
                data["net_profit_per_share"] = data["net_profit"] * share_factor
            else:
                data["fcf"] = 0.0
                data["owner_earnings"] = 0.0
                data["ebit"] = 0.0

            data["roe"] = screener.get("ratios", {}).get("roe") or (info.get("returnOnEquity") or 0.0) * 100
        else:
            logger.warning(f"⚠️ Screener data missing for {symbol}. Falling back to Yahoo essentials.")
            data["growth_5y"] = (info.get("earningsGrowth") or info.get("revenueGrowth") or 0.0) * 100
            data["growth_yoy"] = 0.0
            data["roe"] = (info.get("returnOnEquity") or 0.0) * 100
            data["fcf"] = 0.0
            data["owner_earnings"] = 0.0
            data["ebit"] = 0.0
            data["tax_rate"] = 0.25 # Default 25%

        # 3. Model-specific strict validation
        # Graham: EPS, Growth
        # DCF: FCF (requires Net Profit, Depr, Capex), Growth
        # Lynch: EPS, Growth
        # Buffett: Owner Earnings (requires Net Profit, Depr, Capex), Growth
        # EPV: EBIT, Tax Rate
        # DDM: Dividend Rate, Growth

        from config import V4_STRICT_MODE
        
        # Check all core fields mentioned in spec
        # Mandatory for a basic valuation
        mandatory_checks = {
            "EPS (TTM)": data.get("eps_ttm", 0) > 0,
            "Net Profit": data.get("net_profit_per_share", 0) > 0,
            "EBIT": data.get("ebit", 0) > 0,
            "Tax Rate": data.get("tax_rate", 0) > 0,
            "Book Value": data.get("book_value", 0) > 0
        }

        # Optional fields (we have proxies or they only affect 1 model)
        optional_fields = ["Depreciation", "Capex", "Dividends"]

        # If strict mode is ON, and any of these are missing, we report them
        if V4_STRICT_MODE:
            for field, present in mandatory_checks.items():
                if not present:
                    data["missing_fields"].append(field)
            
            if data["missing_fields"]:
                data["valid"] = False
        else:
            # Legacy simple validation if strict mode is OFF
            if data["price"] <= 0: data["missing_fields"].append("Price")
            if data["eps_ttm"] <= 0: data["missing_fields"].append("EPS")
            if data["growth_5y"] <= 0: data["missing_fields"].append("Growth")
            if data["missing_fields"]:
                data["valid"] = False

        # Independent model validity (always useful to know)
        data["model_validity"] = {
            "GRAHAM": data.get("eps_ttm", 0) > 0 and data.get("growth_5y", 0) > 0,
            "DCF": data.get("fcf", 0) > 0 and data.get("growth_5y", 0) > 0,
            "LYNCH": data.get("eps_ttm", 0) > 0 and data.get("growth_5y", 0) > 0,
            "BUFFETT": data.get("owner_earnings", 0) > 0 and data.get("growth_5y", 0) > 0,
            "EPV": data.get("ebit", 0) > 0 and data.get("tax_rate", 0) > 0,
            "DDM": data.get("dividend_rate", 0) > 0 and data.get("growth_5y", 0) > 0,
            "PB_ROE": data.get("book_value", 0) > 0 and data.get("roe", 0) > 0
        }
        
        valid_models = [m for m, v in data["model_validity"].items() if v]
        logger.info(f"📊 {symbol} Summary: {len(valid_models)} valid models found ({', '.join(valid_models)})")

    except Exception as e:
        logger.error(f"V4 data gathering error for {symbol}: {e}")
        data["valid"] = False
        data["errors"].append(str(e))
        
    return data
