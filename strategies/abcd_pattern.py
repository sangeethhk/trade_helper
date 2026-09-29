import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from core.models import PatternResult, PatternType, Direction, CalibrationParams
from strategies.base_strategy import BaseStrategy

class ABCDPatternStrategy(BaseStrategy):
    """
    ABCD Pattern Strategy as defined in Andrew Elder's Day Trading Strategies (Book 2, Chapter 11).
    1. A -> B: Strong upward push establishing Point B (Day high / impulse high).
    2. B -> C: Orderly retracement where Point C makes a higher low than Point A (C > A).
               Point C holds support typically between 38.2% and 61.8% Fibonacci retracement.
    3. C -> D: Anticipation of breakout to Point D (prior high B and 1.272-1.618 extension).
    Risk Rules:
    - Buy close to Point C.
    - Stop Loss placed just below Point C.
    - Target 1: Point B / initial D (Sell 50% here and move stop to Breakeven).
    - Target 2: Fibonacci extension of A-B leg.
    """
    def __init__(self):
        super().__init__(name="ABCD Pattern")

    def detect(self, df: pd.DataFrame, symbol: str, timeframe: str, calibration: Optional[CalibrationParams] = None) -> Optional[PatternResult]:
        if len(df) < 30:
            return None

        min_fib = calibration.abcd_min_pullback_fib if calibration else 0.382
        max_fib = calibration.abcd_max_pullback_fib if calibration else 0.650
        atr_mult = calibration.atr_stop_multiplier if calibration else 1.2

        # Look back over recent 30 bars
        window = df.iloc[-30:].reset_index(drop=True)
        highs = window['high'].values
        lows = window['low'].values
        closes = window['close'].values
        timestamps = window['timestamp'].values
        atr = window['atr14'].iloc[-1] if 'atr14' in window else (highs[-1] - lows[-1])

        # Find local high (Point B) in middle portion of window
        b_idx = int(np.argmax(highs[5:-3])) + 5
        b_price = highs[b_idx]
        b_time = timestamps[b_idx]

        # Point A: Lowest low before B
        a_sub = lows[:b_idx]
        if len(a_sub) < 3:
            return None
        a_idx = int(np.argmin(a_sub))
        a_price = lows[a_idx]
        a_time = timestamps[a_idx]

        # Ensure valid initial surge A -> B
        ab_height = b_price - a_price
        if ab_height <= 0 or (ab_height / a_price) < 0.003:  # At least 0.3% move
            return None

        # Point C: Lowest low after B up to current/recent candle
        c_sub = lows[b_idx:]
        if len(c_sub) < 2:
            return None
        c_rel_idx = int(np.argmin(c_sub))
        c_idx = b_idx + c_rel_idx
        c_price = lows[c_idx]
        c_time = timestamps[c_idx]

        # Condition 1: C must be higher than A (Higher Low)
        if c_price <= a_price:
            return None

        # Condition 2: Retracement ratio (B - C) / (B - A)
        retrace = (b_price - c_price) / ab_height
        if not (min_fib <= retrace <= max_fib):
            return None

        # Current bar must be holding C support and beginning upward bounce
        current_close = closes[-1]
        if current_close < c_price:
            return None  # Support failed

        # Entry, Stop Loss, and Targets according to Elder rules
        entry_price = round(current_close, 5)
        stop_buffer = (atr * atr_mult * 0.5)
        stop_loss = round(c_price - stop_buffer, 5)
        risk = entry_price - stop_loss
        if risk <= 0:
            return None

        # Point D (Target 1 is prior high B, Target 2 is extension)
        target_1 = round(b_price, 5)
        target_2 = round(c_price + ab_height, 5)  # 100% measured move D
        rr_ratio = round((target_1 - entry_price) / risk, 2)

        # Minimum reward/risk check from book (prefer >= 1.5 - 2.0)
        if rr_ratio < 1.3:
            return None

        confidence = 0.82 if retrace <= 0.50 else 0.74
        if 'rvol' in window and window['rvol'].iloc[-1] > 1.2:
            confidence = min(0.95, confidence + 0.08)

        return PatternResult(
            pattern_type=PatternType.ABCD,
            symbol=symbol,
            timeframe=timeframe,
            direction=Direction.BULLISH,
            timestamp=str(timestamps[-1]),
            points={
                "A": {"price": round(a_price, 5), "time": a_time, "idx": a_idx},
                "B": {"price": round(b_price, 5), "time": b_time, "idx": b_idx},
                "C": {"price": round(c_price, 5), "time": c_time, "idx": c_idx},
                "D_projected": {"price": target_2, "time": "Projected"}
            },
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_reward_ratio=rr_ratio,
            confidence_score=round(confidence, 2),
            rationale=(
                f"Valid ABCD setup: Impulse A (${a_price:.4f}) to B (${b_price:.4f}) followed by "
                f"{retrace*100:.1f}% Fibonacci pullback holding support at C (${c_price:.4f}). "
                f"Elder Rule: Take 50% profit at D/B (${target_1:.4f}), move stop to breakeven, and trail Target 2 (${target_2:.4f})."
            )
        )
