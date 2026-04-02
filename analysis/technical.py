"""
technical.py — Technical Analysis Checks 1 through 6 plus optional non-scoring
additional signals.

Check 1: DMA Position (50 DMA + 200 DMA)
Check 2: MACD Signal
Check 3: RSI Zone
Check 4: Multi-timeframe Moving Averages (5/20/50/200 DMA)
Check 5: 52-Week Range Position
Check 6: Breakout Failure Trap

Additional signals:
- Supertrend
- Bollinger Band Squeeze
- Support & Resistance Zones
- Relative Strength vs Nifty
- VPT Accumulation
- Candlestick Pattern Recognition
- 52-Week High Breakout Club

NOTE: Uses pure pandas/numpy — no pandas-ta dependency required.
"""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PURE PANDAS INDICATOR HELPERS
# ─────────────────────────────────────────────

def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range using Wilder's EWM.
    Requires High, Low, Close columns.
    """
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return atr


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI using EWM (same as pandas-ta / TradingView).
    Returns a Series of RSI values.
    """
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    # Wilder's smoothing = EWM with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calc_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> tuple:
    """
    Standard MACD using EWM.
    Returns (macd_line, signal_line, histogram) as pd.Series.
    """
    ema_fast    = series.ewm(span=fast,   adjust=False).mean()
    ema_slow    = series.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def _cluster_levels(levels: list[float], tolerance_pct: float = 1.2) -> list[float]:
    """Group nearby price levels into zones and return zone centroids."""
    if not levels:
        return []

    sorted_levels = sorted(float(level) for level in levels)
    clusters: list[list[float]] = [[sorted_levels[0]]]

    for level in sorted_levels[1:]:
        anchor = sum(clusters[-1]) / len(clusters[-1])
        tolerance = max(anchor * tolerance_pct / 100.0, 0.01)
        if abs(level - anchor) <= tolerance:
            clusters[-1].append(level)
        else:
            clusters.append([level])

    return [sum(cluster) / len(cluster) for cluster in clusters]


# ─────────────────────────────────────────────
# CHECK FUNCTIONS
# ─────────────────────────────────────────────

def check_dma_position(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 1 — DMA Position (50 DMA + 200 DMA).
    Returns (signal, detail_message)
    """
    try:
        if len(df) < 200:
            return "UNAVAILABLE", "Insufficient data for 200 DMA"

        price  = df["Close"].iloc[-1]
        sma50  = df["Close"].rolling(50).mean().iloc[-1]
        sma200 = df["Close"].rolling(200).mean().iloc[-1]

        if price > sma50 and price > sma200:
            return "BULLISH", f"Price ₹{price:.2f} above 50DMA ₹{sma50:.2f} & 200DMA ₹{sma200:.2f}"
        elif price < sma50 and price < sma200:
            return "BEARISH", f"Price ₹{price:.2f} below both DMAs (50: ₹{sma50:.2f}, 200: ₹{sma200:.2f})"
        elif price < sma50:
            return "BEARISH", f"Price ₹{price:.2f} below 50DMA ₹{sma50:.2f} — short-term weak"
        else:
            return "NEUTRAL", "Price between 50DMA & 200DMA — mixed signals"
    except Exception as e:
        logger.error(f"DMA check error: {e}")
        return "UNAVAILABLE", "DMA check error"


def check_macd(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 2 — MACD (12, 26, 9) — pure pandas EWM implementation.
    Returns (signal, detail_message)
    """
    try:
        if len(df) < 35:
            return "UNAVAILABLE", "Insufficient data for MACD"

        macd_line, signal_line, histogram = _calc_macd(df["Close"])

        ml  = macd_line.iloc[-1]
        sl  = signal_line.iloc[-1]
        hst = histogram.iloc[-1]
        prev_ml = macd_line.iloc[-2]
        prev_sl = signal_line.iloc[-2]
        prev_h1 = histogram.iloc[-2]
        prev_h2 = histogram.iloc[-3]

        if pd.isna(ml) or pd.isna(sl):
            return "UNAVAILABLE", "MACD data unavailable"

        crossed_up = prev_ml <= prev_sl and ml > sl
        crossed_down = prev_ml >= prev_sl and ml < sl
        hist_rising = hst > prev_h1 > prev_h2
        hist_falling = hst < prev_h1 < prev_h2
        separation = abs(ml - sl)

        if ml > sl and hst > 0 and hist_rising:
            signal = "STRONG_BUY" if crossed_up or separation > 1.5 else "BULLISH"
            return signal, (
                f"MACD {ml:.3f} above Signal {sl:.3f}, histogram improving — bullish momentum building"
            )
        elif ml > sl and hst > 0:
            return "BULLISH", f"MACD {ml:.3f} above Signal {sl:.3f} — bullish but momentum is flattening"
        elif ml < sl and hst < 0 and hist_falling:
            signal = "STRONG_SELL" if crossed_down or separation > 1.5 else "BEARISH"
            return signal, (
                f"MACD {ml:.3f} below Signal {sl:.3f}, histogram weakening — bearish momentum building"
            )
        elif ml < sl and hst < 0:
            return "SLIGHTLY_BEARISH", f"MACD {ml:.3f} below Signal {sl:.3f} — bearish but sell pressure is stabilizing"
        elif crossed_up:
            return "BULLISH", "MACD bullish crossover just triggered — early momentum reversal"
        elif crossed_down:
            return "BEARISH", "MACD bearish crossover just triggered — early downside reversal"
        else:
            return "NEUTRAL", "MACD mixed — directional confirmation pending"
    except Exception as e:
        logger.error(f"MACD check error: {e}")
        return "UNAVAILABLE", "MACD check error"


def check_rsi(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 3 — RSI 14-period — pure pandas EWM implementation (Wilder's method).
    Returns (signal, detail_message)
    """
    try:
        if len(df) < 15:
            return "UNAVAILABLE", "Insufficient data for RSI"

        rsi    = _calc_rsi(df["Close"], period=14)
        rsi_val = rsi.iloc[-1]

        if pd.isna(rsi_val):
            return "UNAVAILABLE", "RSI data unavailable"

        if rsi_val > 75:
            return "OVERBOUGHT", f"RSI {rsi_val:.1f} — heavily overbought, avoid entry"
        elif rsi_val > 60:
            return "BULLISH", f"RSI {rsi_val:.1f} — strong uptrend momentum"
        elif 45 <= rsi_val <= 60:
            return "BULLISH", f"RSI {rsi_val:.1f} — healthy uptrend zone"
        elif 30 <= rsi_val < 45:
            return "NEUTRAL", f"RSI {rsi_val:.1f} — mild weakness, watch for recovery"
        else:
            return "OVERSOLD_BUY", f"RSI {rsi_val:.1f} — oversold, contrarian buy zone"
    except Exception as e:
        logger.error(f"RSI check error: {e}")
        return "UNAVAILABLE", "RSI check error"


def check_moving_averages(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 4 — Multi-timeframe Moving Average Alignment (5/20/50/200 DMA).
    Returns (signal, detail_message)
    """
    try:
        if len(df) < 200:
            return "UNAVAILABLE", "Insufficient data for all MAs"

        price  = df["Close"].iloc[-1]
        sma5   = df["Close"].rolling(5).mean().iloc[-1]
        sma20  = df["Close"].rolling(20).mean().iloc[-1]
        sma50  = df["Close"].rolling(50).mean().iloc[-1]
        sma200 = df["Close"].rolling(200).mean().iloc[-1]

        bullish_count = sum([
            price > sma5,
            price > sma20,
            price > sma50,
            price > sma200,
        ])

        if bullish_count == 4:
            return "STRONG_BUY", "Price above all 4 MAs (5/20/50/200) — strong alignment"
        elif bullish_count == 3:
            return "BULLISH", f"Price above {bullish_count}/4 MAs — mostly bullish"
        elif bullish_count == 2:
            return "NEUTRAL", f"Price above {bullish_count}/4 MAs — mixed signals"
        else:
            return "BEARISH", f"Price below {4 - bullish_count}/4 MAs — bearish alignment"
    except Exception as e:
        logger.error(f"Moving averages check error: {e}")
        return "UNAVAILABLE", "Moving averages check error"


def check_52w_range(ticker_info: dict) -> tuple[str, str]:
    """
    Check 5 — 52-Week Range Position.
    Returns (signal, detail_message)
    """
    try:
        current  = float(ticker_info.get("currentPrice") or ticker_info.get("regularMarketPrice") or 0)
        high_52w = float(ticker_info.get("fiftyTwoWeekHigh") or 0)
        low_52w  = float(ticker_info.get("fiftyTwoWeekLow")  or 0)

        if high_52w == 0 or low_52w == 0 or current == 0:
            return "UNAVAILABLE", "52W range data unavailable"

        range_size = high_52w - low_52w
        if range_size == 0:
            return "UNAVAILABLE", "52W range is zero — unusual data"

        range_pct     = ((current - low_52w) / range_size) * 100
        pct_from_high = ((high_52w - current) / high_52w) * 100

        if range_pct <= 20:
            return "OPPORTUNITY", f"Lower quintile of 52W range — value zone, {pct_from_high:.1f}% below 52W high ₹{high_52w}"
        elif range_pct <= 40:
            return "BULLISH", f"Lower half of 52W range — accumulation zone, {pct_from_high:.1f}% below 52W high"
        elif range_pct >= 90:
            return "CAUTION", f"Top decile of 52W range — stretched near high ₹{high_52w}, only {pct_from_high:.1f}% below resistance"
        elif range_pct >= 75:
            return "BULLISH", f"Upper quartile of 52W range — momentum zone, {pct_from_high:.1f}% below 52W high ₹{high_52w}"
        else:
            return "NEUTRAL", f"Middle of 52W range — neither deep value nor breakout stretch ({pct_from_high:.1f}% below high)"
    except Exception as e:
        logger.error(f"52W range check error: {e}")
        return "UNAVAILABLE", "52W range check error"


def check_breakout_failure_trap(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 6 — Breakout Failure Trap using daily candles and volume.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 30 or "Volume" not in df.columns:
            return "UNAVAILABLE", "Insufficient daily data for breakout-failure check"

        recent = df.tail(25).copy()
        current_close = float(recent["Close"].iloc[-1])
        current_high = float(recent["High"].iloc[-1])
        current_low = float(recent["Low"].iloc[-1])
        current_volume = float(recent["Volume"].iloc[-1] or 0)
        prior_volume_window = recent["Volume"].iloc[:-1].tail(20)
        avg_volume = float(prior_volume_window.mean() or 0)
        if avg_volume == 0:
            return "UNAVAILABLE", "Volume data unavailable for breakout-failure check"

        setup_window = recent.iloc[:-3] if len(recent) > 8 else recent.iloc[:-1]
        if setup_window.empty:
            return "UNAVAILABLE", "Not enough history to define breakout resistance"

        resistance = float(setup_window["High"].max())
        recent_breakout = recent.tail(3)
        breakout_seen = bool((recent_breakout["High"] > resistance * 1.005).any())
        close_above_resistance = current_close > resistance * 1.002
        close_back_below = current_close < resistance * 0.995
        range_size = max(current_high - current_low, 1e-9)
        close_in_lower_range = ((current_close - current_low) / range_size) < 0.4
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        if breakout_seen and close_back_below and volume_ratio >= 1.3 and close_in_lower_range:
            return "CAUTION", (
                f"Recent breakout above ₹{resistance:.2f} failed; close slipped back below resistance on {volume_ratio:.2f}x volume — possible operator trap"
            )
        elif close_above_resistance and volume_ratio >= 1.4:
            return "BULLISH", (
                f"Price closed above breakout level ₹{resistance:.2f} on {volume_ratio:.2f}x volume — breakout looks supported"
            )
        else:
            return "NEUTRAL", (
                f"No clean breakout trap: price vs resistance ₹{resistance:.2f}, volume {volume_ratio:.2f}x average"
            )
    except Exception as e:
        logger.error(f"Breakout failure check error: {e}")
        return "UNAVAILABLE", "Breakout failure check error"


# ─────────────────────────────────────────────
# V2 GROUP 2 CHECK (29)
# ─────────────────────────────────────────────

def check_vpt(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 29 — Volume Price Trend (VPT).
    VPT = cumulative sum of (Volume * daily_return).
    Divergence between VPT slope and price slope reveals hidden accumulation or distribution.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 25 or "Volume" not in df.columns:
            return "UNAVAILABLE", "Insufficient OHLCV data for VPT"

        close     = df["Close"]
        volume    = df["Volume"].fillna(0)
        daily_ret = close.pct_change().fillna(0)
        vpt       = (volume * daily_ret).cumsum()

        vpt_20   = vpt.tail(20).values.astype(float)
        price_20 = close.tail(20).values.astype(float)

        if len(vpt_20) < 20 or len(price_20) < 20:
            return "UNAVAILABLE", "Not enough bars for VPT slope comparison"

        x = np.arange(20, dtype=float)

        def _norm(arr: np.ndarray) -> np.ndarray:
            rng = arr.max() - arr.min()
            return (arr - arr.min()) / rng if rng > 0 else np.zeros_like(arr)

        vpt_slope   = float(np.polyfit(x, _norm(vpt_20),   1)[0])
        price_slope = float(np.polyfit(x, _norm(price_20), 1)[0])
        cur_price   = float(close.iloc[-1])

        # Both rising — volume confirming uptrend
        if vpt_slope > 0.02 and price_slope > 0.02:
            if (vpt_slope - price_slope) > 0.015:
                return "STRONG_BUY", (
                    f"VPT uptrend LEADING price at ₹{cur_price:.2f} — hidden accumulation. "
                    f"VPT slope {vpt_slope:+.3f} vs price {price_slope:+.3f}"
                )
            return "BULLISH", (
                f"VPT and price both rising — volume confirming uptrend at ₹{cur_price:.2f}. "
                f"Slopes: VPT {vpt_slope:+.3f}, price {price_slope:+.3f}"
            )

        # VPT rising while price flat/down → quiet accumulation
        if vpt_slope > 0.015 and price_slope <= 0.005:
            return "BULLISH", (
                f"VPT rising ({vpt_slope:+.3f}) while price flat ({price_slope:+.3f}) at ₹{cur_price:.2f} "
                "— hidden accumulation: institutional buying under the surface"
            )

        # VPT falling while price rising → distribution into strength
        if vpt_slope < -0.015 and price_slope > 0.005:
            return "BEARISH", (
                f"VPT falling ({vpt_slope:+.3f}) while price rising ({price_slope:+.3f}) at ₹{cur_price:.2f} "
                "— distribution into strength: smart money exiting on rally"
            )

        # Both falling — volume confirming downtrend
        if vpt_slope < -0.02 and price_slope < -0.02:
            return "BEARISH", (
                f"VPT and price both declining — volume confirming downtrend at ₹{cur_price:.2f}. "
                f"Slopes: VPT {vpt_slope:+.3f}, price {price_slope:+.3f}"
            )

        return "NEUTRAL", (
            f"VPT {vpt_slope:+.3f} vs price {price_slope:+.3f} slope — "
            f"no clear accumulation or distribution pattern at ₹{cur_price:.2f}"
        )

    except Exception as e:
        logger.error(f"VPT check error: {e}")
        return "UNAVAILABLE", "VPT check error"


# ─────────────────────────────────────────────
# V2 GROUP 1 CHECKS (22–26)
# ─────────────────────────────────────────────

def check_supertrend(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 22 — Supertrend Indicator (period=10, multiplier=3).
    Direction: price above supertrend = BULLISH, below = BEARISH.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 20 or "High" not in df.columns or "Low" not in df.columns:
            return "UNAVAILABLE", "Insufficient OHLCV data for Supertrend"

        period     = 10
        multiplier = 3.0

        close = df["Close"].values
        high  = df["High"].values
        low   = df["Low"].values
        n     = len(close)

        # True Range (vectorised)
        prev_close    = np.roll(close, 1)
        prev_close[0] = close[0]
        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
        )

        # Wilder ATR
        atr = np.zeros(n)
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        hl2         = (high + low) / 2.0
        upper_basic = hl2 + multiplier * atr
        lower_basic = hl2 - multiplier * atr

        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        supertrend  = np.zeros(n)
        direction   = np.zeros(n, dtype=int)   # 1=BULLISH, -1=BEARISH

        # Initialise at period
        final_upper[period] = upper_basic[period]
        final_lower[period] = lower_basic[period]
        if close[period] > lower_basic[period]:
            direction[period]  = 1     # BULLISH
            supertrend[period] = final_lower[period]
        else:
            direction[period]  = -1    # BEARISH
            supertrend[period] = final_upper[period]

        for i in range(period + 1, n):
            # Tighten upper band (never widen it)
            if upper_basic[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
                final_upper[i] = upper_basic[i]
            else:
                final_upper[i] = final_upper[i - 1]

            # Loosen lower band (never narrow it)
            if lower_basic[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
                final_lower[i] = lower_basic[i]
            else:
                final_lower[i] = final_lower[i - 1]

            if direction[i - 1] == 1:    # Was BULLISH
                if close[i] < final_lower[i]:
                    direction[i]  = -1   # Flip to BEARISH
                    supertrend[i] = final_upper[i]
                else:
                    direction[i]  = 1
                    supertrend[i] = final_lower[i]
            else:                        # Was BEARISH
                if close[i] > final_upper[i]:
                    direction[i]  = 1    # Flip to BULLISH
                    supertrend[i] = final_lower[i]
                else:
                    direction[i]  = -1
                    supertrend[i] = final_upper[i]

        cur_dir    = int(direction[-1])
        cur_st     = float(supertrend[-1])
        prev_dir   = int(direction[-2])
        cur_price  = float(close[-1])
        just_flipped = cur_dir != prev_dir

        if cur_dir == 1:
            if just_flipped:
                return "STRONG_BUY", (
                    f"Supertrend just flipped BULLISH — price ₹{cur_price:.2f} crossed above "
                    f"supertrend ₹{cur_st:.2f}"
                )
            return "BULLISH", (
                f"Supertrend BULLISH — price ₹{cur_price:.2f} holding above supertrend ₹{cur_st:.2f}"
            )
        else:
            if just_flipped:
                return "STRONG_SELL", (
                    f"Supertrend just flipped BEARISH — price ₹{cur_price:.2f} crossed below "
                    f"supertrend ₹{cur_st:.2f}"
                )
            return "BEARISH", (
                f"Supertrend BEARISH — price ₹{cur_price:.2f} below supertrend ₹{cur_st:.2f}"
            )

    except Exception as e:
        logger.error(f"Supertrend check error: {e}")
        return "UNAVAILABLE", "Supertrend check error"


def check_bollinger_squeeze(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 23 — Bollinger Band Squeeze.
    Squeeze = Bollinger Bands inside Keltner Channel (volatility compression).
    Release direction tells you the breakout bias.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 25 or "High" not in df.columns or "Low" not in df.columns:
            return "UNAVAILABLE", "Insufficient OHLCV data for Bollinger Squeeze"

        period     = 20
        bb_std_mul = 2.0
        kc_atr_mul = 1.5

        close = df["Close"]

        # Bollinger Bands
        bb_mid   = close.rolling(period).mean()
        bb_sd    = close.rolling(period).std(ddof=0)
        bb_upper = bb_mid + bb_std_mul * bb_sd
        bb_lower = bb_mid - bb_std_mul * bb_sd

        # Keltner Channel
        atr      = _calc_atr(df, period)
        kc_upper = bb_mid + kc_atr_mul * atr
        kc_lower = bb_mid - kc_atr_mul * atr

        # Squeeze: BB inside KC
        squeeze_now  = bool(bb_upper.iloc[-1] < kc_upper.iloc[-1] and
                            bb_lower.iloc[-1] > kc_lower.iloc[-1])
        squeeze_prev = bool(bb_upper.iloc[-2] < kc_upper.iloc[-2] and
                            bb_lower.iloc[-2] > kc_lower.iloc[-2])

        just_released = squeeze_prev and not squeeze_now
        still_squeezing = squeeze_now and squeeze_prev

        cur_price   = float(close.iloc[-1])
        cur_bb_mid  = float(bb_mid.iloc[-1])
        bb_width    = float((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] * 100)

        if just_released:
            if cur_price > cur_bb_mid:
                return "STRONG_BUY", (
                    f"Bollinger squeeze RELEASED upward — price ₹{cur_price:.2f} above mid ₹{cur_bb_mid:.2f}, "
                    f"BB width expanding to {bb_width:.1f}%"
                )
            else:
                return "BEARISH", (
                    f"Bollinger squeeze released DOWNWARD — price ₹{cur_price:.2f} below mid ₹{cur_bb_mid:.2f}, "
                    f"BB width expanding to {bb_width:.1f}%"
                )
        elif still_squeezing:
            return "NEUTRAL", (
                f"Bollinger squeeze IN PROGRESS — volatility compressed, BB width {bb_width:.1f}%. "
                "Wait for breakout direction"
            )
        else:
            # No squeeze — normal Bollinger band position
            pct_b = float((close.iloc[-1] - bb_lower.iloc[-1]) /
                          (bb_upper.iloc[-1] - bb_lower.iloc[-1]) * 100)
            if pct_b > 80:
                return "CAUTION", (
                    f"Price at upper Bollinger ({pct_b:.0f}%B, width {bb_width:.1f}%) — "
                    "overbought zone, watch for pullback"
                )
            elif pct_b < 20:
                return "BULLISH", (
                    f"Price at lower Bollinger ({pct_b:.0f}%B, width {bb_width:.1f}%) — "
                    "oversold zone, potential bounce"
                )
            else:
                return "NEUTRAL", (
                    f"No squeeze; price mid-band at {pct_b:.0f}%B, BB width {bb_width:.1f}%"
                )

    except Exception as e:
        logger.error(f"Bollinger squeeze check error: {e}")
        return "UNAVAILABLE", "Bollinger squeeze check error"


def check_support_resistance(df: pd.DataFrame) -> tuple[str, str]:
    """
    Check 24 — Support & Resistance Zones (swing pivot detection).
    Finds nearest swing high (resistance) and swing low (support)
    relative to current price over the last 60 bars.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 30 or "High" not in df.columns or "Low" not in df.columns:
            return "UNAVAILABLE", "Insufficient OHLCV data for S&R check"

        lookback = min(60, len(df) - 1)
        window   = 5   # bars on each side to confirm a swing

        recent = df.tail(lookback).copy()
        highs  = recent["High"].values
        lows   = recent["Low"].values
        closes = recent["Close"].values

        cur_price = float(closes[-1])

        swing_highs = []
        swing_lows  = []

        for i in range(window, len(closes) - window):
            if highs[i] == max(highs[i - window: i + window + 1]):
                swing_highs.append(float(highs[i]))
            if lows[i] == min(lows[i - window: i + window + 1]):
                swing_lows.append(float(lows[i]))

        if not swing_highs and not swing_lows:
            return "NEUTRAL", "No clear swing pivots found in recent price history"

        resistance_zones = _cluster_levels(swing_highs)
        support_zones = _cluster_levels(swing_lows)

        resistances = sorted([h for h in resistance_zones if h > cur_price])
        supports = sorted([l for l in support_zones if l < cur_price], reverse=True)

        nearest_res = resistances[0] if resistances else None
        nearest_sup = supports[0]    if supports    else None

        res_pct = ((nearest_res - cur_price) / cur_price * 100) if nearest_res else None
        sup_pct = ((cur_price - nearest_sup) / cur_price * 100) if nearest_sup else None

        if nearest_sup is not None and sup_pct is not None and sup_pct <= 3.0:
            res_str = f", resistance ₹{nearest_res:.2f} ({res_pct:.1f}% away)" if nearest_res else ""
            return "BULLISH", (
                f"Price ₹{cur_price:.2f} near support zone ₹{nearest_sup:.2f} "
                f"({sup_pct:.1f}% below){res_str} — potential bounce zone"
            )
        elif nearest_res is not None and res_pct is not None and res_pct <= 2.0:
            sup_str = f", support ₹{nearest_sup:.2f} ({sup_pct:.1f}% below)" if nearest_sup else ""
            return "CAUTION", (
                f"Price ₹{cur_price:.2f} approaching resistance zone ₹{nearest_res:.2f} "
                f"({res_pct:.1f}% away){sup_str} — watch for breakout or rejection"
            )
        else:
            parts = []
            if nearest_sup:
                parts.append(f"support ₹{nearest_sup:.2f} ({sup_pct:.1f}% below)")
            if nearest_res:
                parts.append(f"resistance ₹{nearest_res:.2f} ({res_pct:.1f}% away)")
            zone_desc = " | ".join(parts) if parts else "no clear zones"
            return "NEUTRAL", f"Price ₹{cur_price:.2f} mid-zone — {zone_desc}"

    except Exception as e:
        logger.error(f"Support/Resistance check error: {e}")
        return "UNAVAILABLE", "Support/Resistance check error"


def check_relative_strength(df: pd.DataFrame, stock_symbol: str) -> tuple[str, str]:
    """
    Check 25 — Relative Strength vs Nifty (20-day return comparison).
    Strong outperformance = leadership signal.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 22:
            return "UNAVAILABLE", "Insufficient stock data for relative strength check"

        from data.fetchers.yfinance_fetcher import get_market_history
        from config import STOCK_SECTOR_BENCHMARKS

        nifty_hist = get_market_history("^NSEI", period="2mo", interval="1d")
        if nifty_hist.empty or len(nifty_hist) < 20:
            return "UNAVAILABLE", "Nifty data unavailable for relative strength check"

        sector_symbol = STOCK_SECTOR_BENCHMARKS.get(stock_symbol)
        sector_hist = get_market_history(sector_symbol, period="2mo", interval="1d") if sector_symbol else pd.DataFrame()

        stock_20  = df["Close"].tail(20)
        nifty_20  = nifty_hist["Close"].tail(20)
        sector_20 = sector_hist["Close"].tail(20) if not sector_hist.empty and len(sector_hist) >= 20 else None

        if len(stock_20) < 2 or len(nifty_20) < 2:
            return "UNAVAILABLE", "Not enough aligned bars for relative strength"

        stock_ret = (float(stock_20.iloc[-1]) - float(stock_20.iloc[0])) / float(stock_20.iloc[0]) * 100
        nifty_ret = (float(nifty_20.iloc[-1]) - float(nifty_20.iloc[0])) / float(nifty_20.iloc[0]) * 100
        rs_nifty = stock_ret - nifty_ret
        rs_sector = None
        if sector_20 is not None and len(sector_20) >= 2:
            sector_ret = (float(sector_20.iloc[-1]) - float(sector_20.iloc[0])) / float(sector_20.iloc[0]) * 100
            rs_sector = stock_ret - sector_ret
        detail_tail = (
            f", sector {sector_symbol} RS {rs_sector:+.1f}%"
            if rs_sector is not None and sector_symbol
            else ""
        )

        if rs_nifty >= 6 and (rs_sector is None or rs_sector >= 2):
            return "STRONG_BUY", (
                f"Strong RS leader: stock {stock_ret:+.1f}% vs Nifty {nifty_ret:+.1f}% "
                f"(RS = {rs_nifty:+.1f}%){detail_tail} over 20 days — institutional momentum"
            )
        elif rs_nifty >= 3 and (rs_sector is None or rs_sector >= 0):
            return "BULLISH", (
                f"Outperforming: stock {stock_ret:+.1f}% vs Nifty {nifty_ret:+.1f}% "
                f"(RS = {rs_nifty:+.1f}%){detail_tail} over 20 days"
            )
        elif rs_nifty <= -6 and (rs_sector is None or rs_sector <= -2):
            return "BEARISH", (
                f"Significant underperformance: stock {stock_ret:+.1f}% vs Nifty {nifty_ret:+.1f}% "
                f"(RS = {rs_nifty:+.1f}%){detail_tail} over 20 days — avoid"
            )
        elif rs_nifty <= -3 and (rs_sector is None or rs_sector < 0):
            return "CAUTION", (
                f"Lagging Nifty: stock {stock_ret:+.1f}% vs Nifty {nifty_ret:+.1f}% "
                f"(RS = {rs_nifty:+.1f}%){detail_tail} over 20 days"
            )
        else:
            return "NEUTRAL", (
                f"Inline with Nifty: stock {stock_ret:+.1f}% vs Nifty {nifty_ret:+.1f}% "
                f"(RS = {rs_nifty:+.1f}%){detail_tail} over 20 days"
            )

    except Exception as e:
        logger.error(f"Relative strength check error: {e}")
        return "UNAVAILABLE", "Relative strength check error"


def check_52w_breakout_club(df: pd.DataFrame, ticker_info: dict) -> tuple[str, str]:
    """
    Check 26 — 52-Week High Breakout Club.
    New 52W high with strong volume = institutional momentum confirmation.
    Returns (signal, detail_message)
    """
    try:
        if df is None or len(df) < 20 or "Volume" not in df.columns:
            return "UNAVAILABLE", "Insufficient data for 52W breakout club check"

        high_52w = float(ticker_info.get("fiftyTwoWeekHigh") or 0)
        if high_52w == 0:
            return "UNAVAILABLE", "52W high unavailable"

        cur_price    = float(df["Close"].iloc[-1])
        cur_volume   = float(df["Volume"].iloc[-1] or 0)
        avg_volume   = float(df["Volume"].iloc[:-1].tail(20).mean() or 1)
        volume_ratio = cur_volume / avg_volume if avg_volume > 0 else 1.0
        recent_20 = df["Close"].tail(20)
        rs_20 = ((float(recent_20.iloc[-1]) - float(recent_20.iloc[0])) / float(recent_20.iloc[0]) * 100) if len(recent_20) >= 2 else 0.0
        avg_turnover = float((df["Close"].iloc[:-1].tail(20) * df["Volume"].iloc[:-1].tail(20)).mean() or 0)
        cur_turnover = cur_price * cur_volume

        pct_from_high = (high_52w - cur_price) / high_52w * 100

        if cur_price >= high_52w * 0.999:
            if volume_ratio >= 1.5 and rs_20 >= 5 and cur_turnover >= avg_turnover * 1.2:
                return "STRONG_BUY", (
                    f"52W high breakout with {volume_ratio:.1f}x volume — "
                    f"price ₹{cur_price:.2f} at/above 52W high ₹{high_52w:.2f}, 20-day move {rs_20:+.1f}% "
                    "— institutional momentum confirmed"
                )
            elif volume_ratio >= 1.1 and rs_20 >= 3:
                return "BULLISH", (
                    f"At 52W high ₹{high_52w:.2f} with {volume_ratio:.1f}x volume — "
                    f"breakout attempt with 20-day strength {rs_20:+.1f}%, needs stronger confirmation"
                )
            else:
                return "CAUTION", (
                    f"At 52W high ₹{high_52w:.2f} but weak volume {volume_ratio:.1f}x / 20-day strength {rs_20:+.1f}% — "
                    "low-conviction breakout, watch for failure"
                )

        elif pct_from_high <= 3.0:
            if volume_ratio >= 1.3 and rs_20 >= 3:
                return "BULLISH", (
                    f"Within {pct_from_high:.1f}% of 52W high ₹{high_52w:.2f} "
                    f"with {volume_ratio:.1f}x volume and 20-day strength {rs_20:+.1f}% — approaching breakout zone"
                )
            else:
                return "NEUTRAL", (
                    f"Within {pct_from_high:.1f}% of 52W high ₹{high_52w:.2f} — "
                    f"volume {volume_ratio:.1f}x / 20-day strength {rs_20:+.1f}% lack conviction"
                )

        # Well below 52W high
        else:
            return "NEUTRAL", (
                f"Price ₹{cur_price:.2f} is {pct_from_high:.1f}% below 52W high ₹{high_52w:.2f} — "
                "not in breakout territory"
            )

    except Exception as e:
        logger.error(f"52W breakout club check error: {e}")
        return "UNAVAILABLE", "52W breakout club check error"


def check_candlestick_pattern(df: pd.DataFrame) -> tuple[str, str]:
    """
    Additional Signal — Candlestick Pattern Recognition.
    Detect a few high-value daily patterns on the latest candle pair.
    """
    try:
        if df is None or len(df) < 5:
            return "UNAVAILABLE", "Insufficient OHLC data for candlestick patterns"

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        o1, h1, l1, c1 = map(float, [latest["Open"], latest["High"], latest["Low"], latest["Close"]])
        o0, h0, l0, c0 = map(float, [prev["Open"], prev["High"], prev["Low"], prev["Close"]])

        body1 = abs(c1 - o1)
        range1 = max(h1 - l1, 1e-9)
        upper_shadow = h1 - max(c1, o1)
        lower_shadow = min(c1, o1) - l1

        bullish_engulfing = c0 < o0 and c1 > o1 and o1 <= c0 and c1 >= o0
        bearish_engulfing = c0 > o0 and c1 < o1 and o1 >= c0 and c1 <= o0
        hammer = body1 / range1 <= 0.35 and lower_shadow >= body1 * 2 and upper_shadow <= body1
        doji = body1 / range1 <= 0.1

        if bullish_engulfing:
            return "BULLISH", "Bullish engulfing on the latest daily candle — momentum reversal signal"
        if bearish_engulfing:
            return "BEARISH", "Bearish engulfing on the latest daily candle — reversal warning"
        if hammer:
            return "BULLISH", "Hammer-like candle on the latest daily bar — potential support bounce"
        if doji:
            return "INFO", "Doji on the latest daily candle — indecision near current level"
        return "NEUTRAL", "No strong daily candlestick reversal pattern on the latest bar"
    except Exception as e:
        logger.error(f"Candlestick pattern check error: {e}")
        return "UNAVAILABLE", "Candlestick pattern check error"


def run_all_technical_checks(
    df: pd.DataFrame,
    df_1h: pd.DataFrame,
    ticker_info: dict,
) -> list[dict]:
    """
    Run only the 6 scored technical checks.
    """
    checks = [
        (1,  "DMA Position",          check_dma_position(df)),
        (2,  "MACD",                  check_macd(df)),
        (3,  "RSI",                   check_rsi(df)),
        (4,  "Moving Avg Alignment",  check_moving_averages(df)),
        (5,  "52-Week Range",         check_52w_range(ticker_info)),
        (6,  "Breakout Failure Trap", check_breakout_failure_trap(df)),
    ]

    return [
        {
            "check_number": num,
            "category":     "Technical",
            "name":         name,
            "signal":       result[0],
            "detail":       result[1],
        }
        for num, name, result in checks
    ]


def run_additional_technical_signals(
    df: pd.DataFrame,
    ticker_info: dict,
    stock_symbol: str,
) -> list[dict]:
    """
    Run non-scoring technical signals separately from the 21-check core.
    """
    signals = [
        ("Supertrend",           check_supertrend(df)),
        ("Bollinger Squeeze",    check_bollinger_squeeze(df)),
        ("Support & Resistance", check_support_resistance(df)),
        ("Relative Strength",    check_relative_strength(df, stock_symbol)),
        ("VPT Accumulation",     check_vpt(df)),
        ("Candlestick Pattern Recognition", check_candlestick_pattern(df)),
        ("52-Week High Breakout Club", check_52w_breakout_club(df, ticker_info)),
    ]

    return [
        {
            "category": "Additional Signals",
            "name": name,
            "signal": result[0],
            "detail": result[1],
        }
        for name, result in signals
    ]
