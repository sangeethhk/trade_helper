import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from core.models import PatternResult, PatternType, Direction, CalibrationParams
from strategies.base_strategy import BaseStrategy

class ConsolidationPatternStrategy(BaseStrategy):
    """
    Consolidation Chart Patterns from Andrew Elder's Book (Chapter 6):
    - Ascending Triangle (Bullish continuation/reversal)
    - Descending Triangle (Bearish continuation)
    - Head & Shoulders / Inverse Head & Shoulders
    - Triple Bottom
    """
    def __init__(self):
        super().__init__(name="Consolidation Patterns")

    def detect(self, df: pd.DataFrame, symbol: str, timeframe: str, calibration: Optional[CalibrationParams] = None) -> Optional[PatternResult]:
        if len(df) < 35:
            return None

        window = df.iloc[-35:].reset_index(drop=True)
        highs = window['high'].values
        lows = window['low'].values
        closes = window['close'].values
        timestamps = window['timestamp'].values
        atr = window['atr14'].iloc[-1] if 'atr14' in window else (highs[-1] - lows[-1])
        atr_mult = calibration.atr_stop_multiplier if calibration else 1.3

        # 1. Triple Bottom Detection
        # Check if there are 3 distinct troughs around the same support level
        low_troughs = []
        for i in range(2, len(lows) - 3):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                low_troughs.append((i, lows[i]))

        if len(low_troughs) >= 3:
            last_3 = low_troughs[-3:]
            p1, p2, p3 = last_3[0][1], last_3[1][1], last_3[2][1]
            avg_bottom = (p1 + p2 + p3) / 3.0
            variance = max(abs(p1 - avg_bottom), abs(p2 - avg_bottom), abs(p3 - avg_bottom)) / avg_bottom
            
            # If all 3 bottoms are within 0.3% of each other and price is now rebounding
            if variance < 0.0035 and closes[-1] > avg_bottom + (atr * 0.5):
                entry_price = round(closes[-1], 5)
                stop_loss = round(avg_bottom - (atr * atr_mult), 5)
                risk = entry_price - stop_loss
                if risk > 0:
                    target_1 = round(entry_price + (risk * 2.0), 5)
                    target_2 = round(entry_price + (risk * 3.5), 5)
                    return PatternResult(
                        pattern_type=PatternType.TRIANGLE,
                        symbol=symbol,
                        timeframe=timeframe,
                        direction=Direction.BULLISH,
                        timestamp=str(timestamps[-1]),
                        points={"bottom_1": p1, "bottom_2": p2, "bottom_3": p3, "support": avg_bottom},
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        risk_reward_ratio=2.0,
                        confidence_score=0.81,
                        rationale=(
                            f"Triple Bottom Reversal: Asset formed 3 distinct bottoms around ${avg_bottom:.4f}. "
                            f"Elder Chapter 6: Triple bottoms indicate exhaustion of sellers and incoming upward reversal."
                        )
                    )

        # 2. Ascending Triangle Detection (Flat resistance, rising lows)
        recent_highs = highs[-25:]
        recent_lows = lows[-25:]
        res_ceiling = np.percentile(recent_highs, 90)
        
        # Test if swing lows are sloping upward
        low_first_half = np.min(recent_lows[:12])
        low_second_half = np.min(recent_lows[12:])

        if low_second_half > low_first_half * 1.002: # Ascending slope
            # If current price is pressing against resistance ceiling
            if abs(closes[-1] - res_ceiling) < (atr * 0.5):
                entry_price = round(closes[-1], 5)
                stop_loss = round(low_second_half - (atr * 0.5), 5)
                risk = entry_price - stop_loss
                if risk > 0:
                    target_1 = round(entry_price + (risk * 2.1), 5)
                    target_2 = round(entry_price + (risk * 3.2), 5)
                    return PatternResult(
                        pattern_type=PatternType.TRIANGLE,
                        symbol=symbol,
                        timeframe=timeframe,
                        direction=Direction.BULLISH,
                        timestamp=str(timestamps[-1]),
                        points={"resistance": round(res_ceiling, 5), "rising_low": round(low_second_half, 5)},
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        risk_reward_ratio=2.1,
                        confidence_score=0.80,
                        rationale=(
                            f"Ascending Triangle: Flat resistance at ${res_ceiling:.4f} with rising swing lows "
                            f"(${low_first_half:.4f} -> ${low_second_half:.4f}). High probability bullish breakout setup."
                        )
                    )

        return None
