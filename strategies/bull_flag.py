import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from core.models import PatternResult, PatternType, Direction, CalibrationParams
from strategies.base_strategy import BaseStrategy

class BullFlagStrategy(BaseStrategy):
    """
    Bull Flag Momentum Strategy as defined in Andrew Elder's Book (Chapters 14, 24).
    1. Bullish Flag Pole: Rapid, aggressive price advance with above-average candle bodies.
    2. Consolidation Flag: Tight sideways or slightly descending channel with decreasing volume.
    3. Breakout: Decisive bar pushing above flag resistance line on high relative volume (RVOL >= threshold).
    4. Sizing & Exits: Stop loss under flag base; take 50% profit at measured pole extension, exit on extension bar or red candle reversal.
    """
    def __init__(self):
        super().__init__(name="Bull Flag Momentum")

    def detect(self, df: pd.DataFrame, symbol: str, timeframe: str, calibration: Optional[CalibrationParams] = None) -> Optional[PatternResult]:
        if len(df) < 25:
            return None

        max_flag_bars = calibration.bull_flag_max_consolidation_bars if calibration else 8
        rvol_thresh = calibration.rvol_threshold if calibration else 1.8
        atr_mult = calibration.atr_stop_multiplier if calibration else 1.2

        window = df.iloc[-25:].reset_index(drop=True)
        closes = window['close'].values
        highs = window['high'].values
        lows = window['low'].values
        opens = window['open'].values
        volumes = window['volume'].values
        timestamps = window['timestamp'].values
        atr = window['atr14'].iloc[-1] if 'atr14' in window else (highs[-1] - lows[-1])

        # Step 1: Detect pole - look for strong impulsive bars 6 to 14 bars ago
        # Find highest high of the pole
        pole_search_start = 5
        pole_search_end = len(window) - 3
        pole_peak_idx = int(np.argmax(highs[pole_search_start:pole_search_end])) + pole_search_start
        pole_peak_price = highs[pole_peak_idx]

        # Base of pole: lowest low before pole peak
        pole_base_sub = lows[:pole_peak_idx]
        if len(pole_base_sub) < 3:
            return None
        pole_base_idx = int(np.argmin(pole_base_sub))
        pole_base_price = lows[pole_base_idx]
        pole_height = pole_peak_price - pole_base_price

        if pole_height <= 0 or (pole_height / pole_base_price) < 0.005:  # Minimum 0.5% impulse
            return None

        # Step 2: Flag consolidation phase between pole_peak_idx and current bar
        flag_bars_count = len(window) - 1 - pole_peak_idx
        if flag_bars_count < 2 or flag_bars_count > max_flag_bars:
            return None

        flag_highs = highs[pole_peak_idx:-1]
        flag_lows = lows[pole_peak_idx:-1]
        flag_vols = volumes[pole_peak_idx:-1]

        flag_min = np.min(flag_lows)
        flag_max = np.max(flag_highs)

        # Retracement should not exceed 50% of the pole (tight flag)
        if (pole_peak_price - flag_min) > (0.50 * pole_height):
            return None

        # Step 3: Check volume drying up during flag (Elder Ch 6, p. 58)
        avg_flag_vol = np.mean(flag_vols) if len(flag_vols) > 0 else 1.0
        pole_vol = np.mean(volumes[pole_base_idx:pole_peak_idx+1]) if pole_peak_idx > pole_base_idx else 1.0
        volume_contracted = avg_flag_vol < (pole_vol * 1.1)

        # Step 4: Breakout bar (Current Bar)
        current_close = closes[-1]
        current_rvol = window['rvol'].iloc[-1] if 'rvol' in window else 1.5

        # Must close near or above flag resistance
        is_breaking_out = (current_close >= flag_max * 0.999) and (current_close > opens[-1])

        if not is_breaking_out:
            return None

        entry_price = round(current_close, 5)
        stop_buffer = (atr * atr_mult * 0.4)
        stop_loss = round(flag_min - stop_buffer, 5)
        risk = entry_price - stop_loss
        if risk <= 0:
            return None

        # Target 1: Measured move = pole height added to breakout level
        target_1 = round(entry_price + (pole_height * 0.8), 5)
        target_2 = round(entry_price + (pole_height * 1.5), 5)
        rr_ratio = round((target_1 - entry_price) / risk, 2)

        if rr_ratio < 1.4:
            return None

        confidence = 0.85 if (current_rvol >= rvol_thresh and volume_contracted) else 0.75

        return PatternResult(
            pattern_type=PatternType.BULL_FLAG,
            symbol=symbol,
            timeframe=timeframe,
            direction=Direction.BULLISH,
            timestamp=str(timestamps[-1]),
            points={
                "pole_base": {"price": round(pole_base_price, 5), "time": timestamps[pole_base_idx]},
                "pole_peak": {"price": round(pole_peak_price, 5), "time": timestamps[pole_peak_idx]},
                "flag_low": {"price": round(flag_min, 5), "time": timestamps[pole_peak_idx]},
                "flag_high": {"price": round(flag_max, 5), "time": timestamps[pole_peak_idx]},
                "breakout": {"price": entry_price, "time": timestamps[-1]}
            },
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_reward_ratio=rr_ratio,
            confidence_score=round(confidence, 2),
            rationale=(
                f"Bull Flag Momentum breakout: Impulsive pole (+{pole_height/pole_base_price*100:.2f}%) with a {flag_bars_count}-bar "
                f"tight consolidation flag. Breakout confirmed at ${entry_price:.4f} with RVOL {current_rvol:.2f}x. "
                f"Elder Rule: Take 50% profit at measured target ${target_1:.4f} and exit quickly if red candle reversal or extension bar appears."
            )
        )
