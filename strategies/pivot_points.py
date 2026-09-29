import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from core.models import PatternResult, PatternType, Direction, CalibrationParams
from core.indicators import calculate_floor_pivot_points
from strategies.base_strategy import BaseStrategy

class PivotPointStrategy(BaseStrategy):
    """
    Floor Pivot Points Strategy (Andrew Elder Ch 9 & 12).
    Uses daily high, low, close to plot:
    P, R1, R2, R3, S1, S2, S3.
    Triggers bounce/rejection signals when intraday price tests these structural levels.
    """
    def __init__(self):
        super().__init__(name="Pivot Points")

    def detect(self, df: pd.DataFrame, symbol: str, timeframe: str, calibration: Optional[CalibrationParams] = None) -> Optional[PatternResult]:
        if len(df) < 20:
            return None

        # Compute prior day/session High, Low, Close
        lookback = min(len(df), 40)
        session_high = float(df['high'].iloc[-lookback:].max())
        session_low = float(df['low'].iloc[-lookback:].min())
        session_close = float(df['close'].iloc[-1])
        timestamps = df['timestamp'].values
        atr = float(df['atr14'].iloc[-1]) if 'atr14' in df else (session_high - session_low) * 0.1

        pivots = calculate_floor_pivot_points(session_high, session_low, session_close)
        current_close = float(df['close'].iloc[-1])
        current_low = float(df['low'].iloc[-1])
        current_high = float(df['high'].iloc[-1])

        # Test bounce from S1 support
        s1 = pivots['s1']
        if abs(current_low - s1) < (atr * 0.3) and current_close > s1:
            entry_price = round(current_close, 5)
            stop_loss = round(s1 - (atr * 0.8), 5)
            risk = entry_price - stop_loss
            if risk > 0:
                target_1 = round(pivots['pivot'], 5)
                target_2 = round(pivots['r1'], 5)
                rr = round((target_1 - entry_price) / risk, 2)
                if rr >= 1.4:
                    return PatternResult(
                        pattern_type=PatternType.PIVOT_REVERSAL,
                        symbol=symbol,
                        timeframe=timeframe,
                        direction=Direction.BULLISH,
                        timestamp=str(timestamps[-1]),
                        points=pivots,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        risk_reward_ratio=rr,
                        confidence_score=0.79,
                        rationale=(
                            f"Floor Pivot Rebound: Price tested S1 Support at ${s1:.4f} with lower rejection wicks. "
                            f"Targeting Central Pivot P at ${pivots['pivot']:.4f} and R1 at ${pivots['r1']:.4f}."
                        )
                    )

        # Test rejection from R1 resistance
        r1 = pivots['r1']
        if abs(current_high - r1) < (atr * 0.3) and current_close < r1:
            entry_price = round(current_close, 5)
            stop_loss = round(r1 + (atr * 0.8), 5)
            risk = stop_loss - entry_price
            if risk > 0:
                target_1 = round(pivots['pivot'], 5)
                target_2 = round(pivots['s1'], 5)
                rr = round((entry_price - target_1) / risk, 2)
                if rr >= 1.4:
                    return PatternResult(
                        pattern_type=PatternType.PIVOT_REVERSAL,
                        symbol=symbol,
                        timeframe=timeframe,
                        direction=Direction.BEARISH,
                        timestamp=str(timestamps[-1]),
                        points=pivots,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        risk_reward_ratio=rr,
                        confidence_score=0.77,
                        rationale=(
                            f"Floor Pivot Rejection: Price tested R1 Resistance at ${r1:.4f} and rejected downward. "
                            f"Targeting Central Pivot P at ${pivots['pivot']:.4f} and S1 at ${pivots['s1']:.4f}."
                        )
                    )

        return None
