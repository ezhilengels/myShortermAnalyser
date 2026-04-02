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
    Stage 1: 5 years high growth
    Stage 2: 5 years moderate growth (half of stage 1)
    Terminal: 5% stable
    """
    if fcf <= 0: return 0.0
    
    total_pv = 0.0
    current_fcf = fcf
    
    # Stage 1: Years 1-5
    for i in range(1, 6):
        current_fcf *= (1 + growth_stage1 / 100)
        total_pv += current_fcf / ((1 + discount_rate) ** i)
        
    # Stage 2: Years 6-10
    growth_stage2 = growth_stage1 / 2
    for i in range(6, 11):
        current_fcf *= (1 + growth_stage2 / 100)
        total_pv += current_fcf / ((1 + discount_rate) ** i)
        
    # Terminal Value
    terminal_fcf = current_fcf * (1 + TERMINAL_GROWTH_INDIA)
    tv = terminal_fcf / (discount_rate - TERMINAL_GROWTH_INDIA)
    total_pv += tv / ((1 + discount_rate) ** 10)
    
    return total_pv

def calculate_lynch_iv(eps: float, growth_rate: float) -> float:
    """
    Formula 3: Peter Lynch Fair Value
    Fair P/E = Growth Rate
    IV = EPS * Growth_Rate
    """
    if eps <= 0 or growth_rate <= 0: return 0.0
    return eps * growth_rate

def calculate_buffett_iv(owner_earnings: float, growth_rate: float, discount_rate: float = DISCOUNT_RATE_INDIA) -> float:
    """
    Formula 4: Buffett Owner Earnings
    IV = Owner Earnings / (Discount Rate - Growth Rate)
    """
    if owner_earnings <= 0: return 0.0
    # Conservative growth cap for Gordon Growth
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

def select_best_model(sector: str, industry: str) -> str:
    """Determine which formula is best for the given sector."""
    sector = sector.lower()
    if "financial" in sector or "bank" in industry.lower():
        return "GRAHAM" # Banks use different metrics, Graham is safest proxy here
    if "technology" in sector or "health" in sector:
        return "LYNCH"
    if "utility" in sector or "energy" in sector:
        return "DDM"
    if "consumer defensive" in sector:
        return "DCF"
    if "basic materials" in sector or "industrial" in sector:
        return "GRAHAM"
    return "DCF" # Default
