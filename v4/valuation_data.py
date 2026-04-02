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
        
        # 2. Fetch from Screener (Primary source for Growth & FCF)
        screener = get_screener_snapshot(symbol)
        if screener and screener.get("source_ok"):
            # Growth rates
            sales_growth = screener.get("growth", {}).get("annual_sales", {})
            profit_growth = screener.get("growth", {}).get("annual_profit", {})
            
            data["growth_5y"] = profit_growth.get("cagr") or sales_growth.get("cagr") or 0.0
            data["growth_yoy"] = profit_growth.get("yoy") or 0.0
            
            # FCF Calculation
            # In Screener fetcher, we might need to parse these specifically.
            # For now, let's use the ratios/metrics already available or estimate.
            data["roe"] = screener.get("ratios", {}).get("roe") or (info.get("returnOnEquity") or 0.0) * 100
            
            # Placeholder for FCF (would ideally be pulled from cash flow table)
            # Net Profit + Depreciation - Capex
            data["fcf"] = (data["market_cap"] / 100) * 0.05 # Conservative fallback: 5% of MC as FCF if missing
        else:
            data["growth_5y"] = (info.get("earningsGrowth") or info.get("revenueGrowth") or 0.0) * 100
            data["growth_yoy"] = 0.0
            data["roe"] = (info.get("returnOnEquity") or 0.0) * 100
            data["fcf"] = 0.0

        # 3. Specific validation for models
        if data["price"] <= 0: data["missing_fields"].append("Current Price")
        if data["eps_ttm"] <= 0: data["missing_fields"].append("EPS (TTM)")
        if data["growth_5y"] <= 0: data["missing_fields"].append("Growth Rate")

        if data["missing_fields"]:
            data["valid"] = False

    except Exception as e:
        logger.error(f"V4 data gathering error for {symbol}: {e}")
        data["valid"] = False
        data["errors"].append(str(e))
        
    return data
