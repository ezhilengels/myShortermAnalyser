"""
v4/valuation_engine.py — Multi-model intrinsic valuation engine.
Implements Strategy V4: Graham, DCF, Lynch, Buffett, EPV, and DDM.
"""

import logging
from typing import Any, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Constants for Indian Market
G_SEC_YIELD = 7.05  # Current India 10Y Bond Yield
RISK_FREE_RATE = 0.0705
EQUITY_RISK_PREMIUM = 0.08
WACC_DEFAULT = 0.12
DISCOUNT_RATE_INDIA = 0.13
TERMINAL_GROWTH_INDIA = 0.05

def calculate_graham_iv(eps: float, growth_rate: float, yield_10y: float = G_SEC_YIELD) -> float:
    """
    Formula 1: Benjamin Graham Revised (1974)
    IV = EPS * (8.5 + 2g) * 4.4 / Y
    """
    if eps <= 0: return 0.0
    # Capping growth for conservative estimate
    g = min(growth_rate, 20.0)
    return eps * (8.5 + 2 * g) * (4.4 / yield_10y)

def calculate_dcf_iv(fcf: float, growth_stage1: float, discount_rate: float = DISCOUNT_RATE_INDIA) -> float:
    """
    Formula 2: Simplified 2-Stage DCF
    Stage 1: 5 years high growth (Capped at 20%)
    Stage 2: 5 years moderate growth (half of stage 1)
    Terminal: 5% stable
    """
    if fcf <= 0: return 0.0
    
    # Growth Trap Cap: Max 20%
    g1 = min(growth_stage1, 20.0)
    
    total_pv = 0.0
    current_fcf = fcf
    
    # Stage 1: Years 1-5
    for i in range(1, 6):
        current_fcf *= (1 + g1 / 100)
        total_pv += current_fcf / ((1 + discount_rate) ** i)
        
    # Stage 2: Years 6-10
    g2 = g1 / 2
    for i in range(6, 11):
        current_fcf *= (1 + g2 / 100)
        total_pv += current_fcf / ((1 + discount_rate) ** i)
        
    # Terminal Value
    terminal_fcf = current_fcf * (1 + TERMINAL_GROWTH_INDIA)
    tv = terminal_fcf / (discount_rate - TERMINAL_GROWTH_INDIA)
    total_pv += tv / ((1 + discount_rate) ** 10)
    
    return total_pv

def calculate_lynch_iv(eps: float, growth_rate: float) -> float:
    """
    Formula 3: Peter Lynch Fair Value
    Fair P/E = Growth Rate (Capped at 20%)
    IV = EPS * Growth_Rate
    """
    if eps <= 0 or growth_rate <= 0: return 0.0
    g = min(growth_rate, 20.0)
    return eps * g

def calculate_buffett_iv(owner_earnings: float, growth_rate: float, discount_rate: float = DISCOUNT_RATE_INDIA) -> float:
    """
    Formula 4: Buffett Owner Earnings
    IV = Owner Earnings / (Discount Rate - Growth Rate)
    """
    if owner_earnings <= 0: return 0.0
    # Conservative growth cap for Gordon Growth: Max 6%
    g = min(growth_rate / 100, 0.06) 
    r = discount_rate
    if r <= g: r = g + 0.05 # Prevent division by zero/negative
    return owner_earnings / (r - g)

def calculate_epv_iv(ebit: float, tax_rate: float, wacc: float = WACC_DEFAULT) -> float:
    """
    Formula 5: Earnings Power Value (EPV)
    IV = Adjusted EBIT * (1 - tax) / WACC
    """
    if ebit <= 0: return 0.0
    return (ebit * (1 - tax_rate)) / wacc

def calculate_ddm_iv(dividend: float, growth_rate: float, discount_rate: float = DISCOUNT_RATE_INDIA) -> float:
    """
    Formula 6: Dividend Discount Model (Gordon)
    IV = D1 / (r - g)
    """
    if dividend <= 0: return 0.0
    d1 = dividend * (1 + (growth_rate/100))
    g = min(growth_rate / 100, 0.06)
    r = discount_rate
    if r <= g: r = g + 0.05
    return d1 / (r - g)

def get_buffett_sanity_check(eps: float, price: float) -> Tuple[float, str]:
    """Earnings Yield vs Bond Yield"""
    if price <= 0: return 0.0, "INVALID PRICE"
    yield_val = (eps / price) * 100
    verdict = "ATTRACTIVE" if yield_val > G_SEC_YIELD else "UNATTRACTIVE"
    return yield_val, verdict

def calculate_pb_roe_iv(book_value: float, roe: float) -> float:
    """
    Special Formula for Banks/Financials: P/B + ROE
    Fair Value = Book Value * (ROE / 12) 
    (Assuming a bank earning 12% ROE deserves to trade at 1.0x Book)
    """
    if book_value <= 0 or roe <= 0: return 0.0
    return book_value * (roe / 12.0)

def get_model_pair(sector: str, industry: str) -> Tuple[str, str]:
    """Return (Primary, Secondary) models based on Sector-Based Model Selection mapping."""
    sector = sector.lower()
    ind = industry.lower()
    
    if "financial" in sector or "bank" in ind:
        return ("PB_ROE", "GRAHAM") # Matches Table
    if "technology" in sector or "health" in sector:
        return ("LYNCH", "DCF")
    if "utility" in sector or "energy" in sector:
        return ("DDM", "EPV")
    if "consumer defensive" in sector:
        return ("DCF", "DDM")
    if "basic materials" in sector or "industrial" in sector:
        return ("GRAHAM", "BUFFETT")
    
    return ("DCF", "GRAHAM") # Default fallback

def calculate_weighted_iv(iv_map: Dict[str, float], sector: str, industry: str) -> Tuple[float, str]:
    """
    Calculate a weighted intrinsic value using 70% of the LOWER model and 30% of HIGHER model.
    This ensures conservative, pessimistic valuation for higher win rates.
    """
    primary_name, secondary_name = get_model_pair(sector, industry)
    
    p_val = iv_map.get(primary_name, 0.0)
    s_val = iv_map.get(secondary_name, 0.0)
    
    if p_val > 0 and s_val > 0:
        low_val = min(p_val, s_val)
        high_val = max(p_val, s_val)
        weighted = (low_val * 0.7) + (high_val * 0.3)
        return weighted, f"Conservative Weight (70% Low/30% High) of {primary_name} & {secondary_name}"
    elif p_val > 0:
        return p_val, f"100% {primary_name} (Secondary {secondary_name} unavailable)"
    elif s_val > 0:
        return s_val, f"100% {secondary_name} (Primary {primary_name} unavailable)"
    
    return 0.0, "NO DATA"
