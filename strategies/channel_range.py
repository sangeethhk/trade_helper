import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from core.models import PatternResult, PatternType, Direction, CalibrationParams
from strategies.base_strategy import BaseStrategy

class ChannelRangeStrategy(BaseStrategy):
    """
    Range and Channel Trading with ATR Volatility Trailing Stops (Andrew Elder Ch 8).
    1. Channel Identification: Price swings between clear support (floor) and resistance (ceiling).
    2. Dynamic ATR Buffer: Prevents being stopped out prematurely on rejection wicks.
    3. Trade Setup: Buy near support targeting channel resistance (or Sell near resistance).
    4. Trailing Rule: Trail stop by k * ATR to capture trend extensions upon breakout.
    """
    def __init__(self):
        super().__init__(name="Range / Channel Trading")

    def detect(self, df: pd.DataFrame, symbol: str, timeframe: str, calibration: Optional[CalibrationParams] = None) -> Optional[PatternResult]:
        if len(df) < 35:
            return None

        atr_stop_mult = calibration.atr_stop_multiplier if calibration else 1.5
        atr_trail_mult = calibration.atr_trail_multiplier if calibration else 2.0

        window = df.iloc[-35:].reset_index(drop=True)
        highs = window['high'].values
        lows = window['low'].values
        closes = window['close'].values
        timestamps = window['timestamp'].values
        atr = window['atr14'].iloc[-1] if 'atr14' in window else (highs[-1] - lows[-1])

        # Calculate quantile bands for support & resistance
        support_level = float(np.percentile(lows[:-2], 12))
        resistance_level = float(np.percentile(highs[:-2], 88))
        range_height = resistance_level - support_level

        if range_height <= (atr * 1.2):
            return None  # Range too compressed to trade profitably

        current_close = float(closes[-1])
        current_low = float(lows[-1])
        current_high = float(highs[-1])

        # Test if current price is testing support (Bullish bounce opportunity)
        distance_to_support = abs(current_low - support_level)
        distance_to_resistance = abs(current_high - resistance_level)

        if distance_to_support < (range_height * 0.25) and current_close > support_level:
            # Bullish bounce from support
            entry_price = round(current_close, 5)
            stop_loss = round(support_level - (atr * atr_stop_mult), 5)
            risk = entry_price - stop_loss
            if risk <= 0:
                return None

            target_1 = round(resistance_level, 5)
            target_2 = round(resistance_level + (range_height * 0.5), 5)
            rr_ratio = round((target_1 - entry_price) / risk, 2)

            if rr_ratio < 1.3:
                return None

            return PatternResult(
                pattern_type=PatternType.CHANNEL_RANGE,
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.BULLISH,
                timestamp=str(timestamps[-1]),
                points={
                    "support": round(support_level, 5),
                    "resistance": round(resistance_level, 5),
                    "channel_height": round(range_height, 5),
                    "atr_trailing_buffer": round(atr * atr_trail_mult, 5)
                },
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                risk_reward_ratio=rr_ratio,
                confidence_score=0.78,
                rationale=(
                    f"Range Bound Bounce: Price tested support ${support_level:.4f} and is rebounding. "
                    f"Target is resistance at ${resistance_level:.4f}. ATR buffer set to {atr_stop_mult}x ATR "
                    f"to prevent premature shakeout (Elder Ch 8)."
                )
            )

        elif distance_to_resistance < (range_height * 0.25) and current_close < resistance_level:
            # Bearish rejection from resistance
            entry_price = round(current_close, 5)
            stop_loss = round(resistance_level + (atr * atr_stop_mult), 5)
            risk = stop_loss - entry_price
            if risk <= 0:
                return None

            target_1 = round(support_level, 5)
            target_2 = round(support_level - (range_height * 0.5), 5)
            rr_ratio = round((entry_price - target_1) / risk, 2)

            if rr_ratio < 1.3:
                return None

            return PatternResult(
                pattern_type=PatternType.CHANNEL_RANGE,
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.BEARISH,
                timestamp=str(timestamps[-1]),
                points={
                    "support": round(support_level, 5),
                    "resistance": round(resistance_level, 5),
                    "channel_height": round(range_height, 5),
                    "atr_trailing_buffer": round(atr * atr_trail_mult, 5)
                },
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                risk_reward_ratio=rr_ratio,
                confidence_score=0.76,
                rationale=(
                    f"Range Bound Rejection: Price tested channel resistance ${resistance_level:.4f} with upper wicks. "
                    f"Shorting back toward support at ${support_level:.4f} with ATR stop buffer."
                )
            )

        return None
