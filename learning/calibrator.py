import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from core.models import CalibrationParams

CALIBRATION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "calibrations.json")

class StrategyCalibrator:
    """
    Dynamic Asset Calibration Engine.
    Adapts trading thresholds and risk multipliers to asset personality and regime:
    - Forex (EUR/USD, GBP/USD, USD/JPY): tight spreads, lower ATR %, requires precise stops.
    - Crypto (BTC/USD, ETH/USD): high intraday volatility, large wicks, requires wider ATR cushion.
    """
    def __init__(self):
        self.profiles: Dict[str, CalibrationParams] = self._load_profiles()

    def _load_profiles(self) -> Dict[str, CalibrationParams]:
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    data = json.load(f)
                    return {k: CalibrationParams(**v) for k, v in data.items()}
            except Exception:
                pass
        return {}

    def _save_profiles(self):
        with open(CALIBRATION_FILE, "w") as f:
            data = {k: v.model_dump() for k, v in self.profiles.items()}
            json.dump(data, f, indent=2)

    def get_calibration(self, symbol: str) -> CalibrationParams:
        if symbol in self.profiles:
            return self.profiles[symbol]
        # Return sensible default and calibrate
        default_params = CalibrationParams(symbol=symbol)
        self.profiles[symbol] = default_params
        return default_params

    def calibrate_symbol(self, df: pd.DataFrame, symbol: str) -> CalibrationParams:
        """
        Learns optimal strategy parameters from historical candles.
        Analyzes:
        - Volatility profile (ATR / Price ratio)
        - Wick noise (rejection false breakout rate)
        - Volume distribution
        """
        if len(df) < 30:
            return self.get_calibration(symbol)

        close = df['close']
        high = df['high']
        low = df['low']
        atr = df['atr14'] if 'atr14' in df else (high - low).rolling(14).mean().bfill()
        
        # 1. Volatility coefficient
        atr_pct = (atr / close).mean() * 100.0  # e.g. 0.08% for EURUSD, 0.23% for BTC 15m

        # 2. Wick noise ratio
        wick_noise = ((df['upper_wick_pct'] + df['lower_wick_pct']) / 2.0).mean()

        # 3. Dynamic RVOL threshold (85th percentile of volume surge, clamped between 1.5 and 2.5)
        if 'rvol' in df:
            rvol_p85 = float(df['rvol'].quantile(0.85))
            rvol_thresh = max(1.5, min(2.5, round(rvol_p85, 2)))
        else:
            rvol_thresh = 1.8

        # 4. Dynamic ATR Multipliers & Strategy Parameters
        # High wick noise or crypto volatility requires wider buffer to avoid premature shakeouts (Elder Ch 8)
        is_crypto = any(c in symbol.upper() for c in ["BTC", "ETH", "SOL"]) or atr_pct > 0.4
        if is_crypto:
            # Crypto profile: dynamic stop widened by wick rejection noise
            atr_stop = 1.8 + min(0.6, wick_noise * 1.2)
            atr_trail = 2.4 + min(0.5, wick_noise * 0.8)
            min_fib = 0.382
            max_fib = 0.650
            flag_bars = 9
            flag_pole_pct = max(0.008, round(float(atr_pct * 3.5 / 100.0), 4))
        else:
            # Forex profile (EURUSD, GBPUSD, etc.)
            atr_stop = 1.2 + min(0.4, wick_noise * 0.8)
            atr_trail = 1.8
            min_fib = 0.400
            max_fib = 0.618
            flag_bars = 6
            flag_pole_pct = 0.0035
            rvol_thresh = max(1.4, min(1.8, rvol_thresh))

        params = CalibrationParams(
            symbol=symbol,
            atr_stop_multiplier=round(float(atr_stop), 2),
            atr_trail_multiplier=round(float(atr_trail), 2),
            abcd_min_pullback_fib=round(float(min_fib), 3),
            abcd_max_pullback_fib=round(float(max_fib), 3),
            bull_flag_max_consolidation_bars=int(flag_bars),
            bull_flag_min_pole_pct=round(float(flag_pole_pct), 4),
            rvol_threshold=round(float(rvol_thresh), 2),
            learned_win_rate_weight=1.0,
            last_calibrated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        self.profiles[symbol] = params
        self._save_profiles()
        return params

calibrator = StrategyCalibrator()
