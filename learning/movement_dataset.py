import numpy as np
import pandas as pd
from typing import Tuple, List

FEATURE_NAMES = [
    'body_pct',
    'upper_wick_pct',
    'lower_wick_pct',
    'is_bullish_bar',
    'ema_spread_pct',
    'ema9_slope',
    'atr_norm',
    'bband_width',
    'rsi14_norm',
    'mfi14_norm',
    'rvol'
]

def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts candlestick microstructure and momentum features for movement learning.
    Directly codifies price action nuances from Elder Chapters 5, 8, 13, and 14:
    - Rejection wicks at turning points
    - EMA9 vs EMA20 spread and directional velocity
    - Normalized ATR volatility and Bollinger Band squeeze/expansion
    - Volume surge ratios (RVOL)
    """
    df = df.copy()
    
    close = df['close']
    ema9 = df['ema9'] if 'ema9' in df else close.ewm(span=9).mean()
    ema20 = df['ema20'] if 'ema20' in df else close.ewm(span=20).mean()
    atr = df['atr14'] if 'atr14' in df else (df['high'] - df['low']).rolling(14).mean()

    # Features
    feats = pd.DataFrame(index=df.index)
    feats['body_pct'] = df['body_pct'].fillna(0.5)
    feats['upper_wick_pct'] = df['upper_wick_pct'].fillna(0.2)
    feats['lower_wick_pct'] = df['lower_wick_pct'].fillna(0.2)
    feats['is_bullish_bar'] = df['is_bullish_bar'].astype(float)
    
    feats['ema_spread_pct'] = ((ema9 - ema20) / close.replace(0, 1.0)) * 100.0
    feats['ema9_slope'] = (ema9.diff(2) / close.replace(0, 1.0)) * 100.0
    feats['atr_norm'] = (atr / close.replace(0, 1.0)) * 100.0
    feats['bband_width'] = df['bband_width'].fillna(0.04)
    feats['rsi14_norm'] = (df['rsi14'] / 100.0).fillna(0.5)
    feats['mfi14_norm'] = (df['mfi14'] / 100.0).fillna(0.5)
    feats['rvol'] = df['rvol'].clip(0.1, 10.0).fillna(1.0)

    return feats.fillna(0.0)

def create_training_dataset(
    df: pd.DataFrame,
    forward_bars: int = 12,
    target_rr: float = 1.0,
    only_quality_trades: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates training samples for learning price movements.
    
    When only_quality_trades=True (Elder Quality Filter):
    Filters out dead market chop and only trains on genuine trade candidates satisfying:
    1. Volume confirmation: RVOL >= 1.15 (institutional presence)
    2. Active volatility: Candle range >= 0.5 * ATR-14 (no micro-noise)
    3. Trend alignment & decisive candle anatomy:
       - Bullish: EMA 9 >= EMA 20, with bullish engulfing or (close > EMA 9 and decisive body/lower rejection wick)
       - Bearish: EMA 9 <= EMA 20, with bearish engulfing or (close < EMA 9 and decisive body/upper rejection wick)
    
    Labels each quality setup:
    1 = Price achieves Target 1 (+1.0R / scale-out milestone) or Target 2 (+2.0R payout) before hitting Stop Loss (1.5 * ATR)
    0 = Fails or hits stop loss first
    """
    feats = extract_features(df)
    close = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    atr = df['atr14'].values if 'atr14' in df else (df['high'] - df['low']).values
    ema9 = df['ema9'].values if 'ema9' in df else df['close'].ewm(span=9).mean().values
    ema20 = df['ema20'].values if 'ema20' in df else df['close'].ewm(span=20).mean().values
    rvol = df['rvol'].values if 'rvol' in df else np.ones(len(df))
    body_pct = df['body_pct'].values if 'body_pct' in df else np.full(len(df), 0.5)
    up_wick = df['upper_wick_pct'].values if 'upper_wick_pct' in df else np.full(len(df), 0.2)
    lo_wick = df['lower_wick_pct'].values if 'lower_wick_pct' in df else np.full(len(df), 0.2)
    bull_eng = df['bullish_engulfing'].values if 'bullish_engulfing' in df else np.zeros(len(df), dtype=bool)
    bear_eng = df['bearish_engulfing'].values if 'bearish_engulfing' in df else np.zeros(len(df), dtype=bool)

    has_real_volume = bool((df['volume'] > 0).any()) if 'volume' in df else False

    X_list = []
    y_list = []

    n = len(df) - forward_bars
    for i in range(25, n):
        entry = close[i]
        c_atr = max(atr[i], entry * 0.001)
        risk = c_atr * 1.5

        if only_quality_trades:
            # Elder Quality Trade Criteria:
            # 1. Volume filter (only applicable when volume is reported, e.g. Crypto/Equities)
            if has_real_volume and rvol[i] < 1.15:
                continue

            # 2. Minimum candle volatility
            if (highs[i] - lows[i]) < 0.5 * c_atr:
                continue

            # 3. Decisive candle anatomy & Trend alignment
            is_bull = (ema9[i] >= ema20[i]) and (
                bull_eng[i] or (close[i] > ema9[i] and (body_pct[i] >= 0.30 or lo_wick[i] >= 0.25))
            )
            is_bear = (ema9[i] <= ema20[i]) and (
                bear_eng[i] or (close[i] < ema9[i] and (body_pct[i] >= 0.30 or up_wick[i] >= 0.25))
            )

            if not (is_bull or is_bear):
                continue

            # Directional target calculation
            reward_target_dist = risk * target_rr

            if is_bull:
                tp = entry + reward_target_dist
                sl = entry - risk
                outcome = 0
                for f in range(1, forward_bars + 1):
                    if lows[i + f] <= sl:
                        outcome = 0
                        break
                    if highs[i + f] >= tp:
                        outcome = 1
                        break
            else:
                tp = entry - reward_target_dist
                sl = entry + risk
                outcome = 0
                for f in range(1, forward_bars + 1):
                    if highs[i + f] >= sl:
                        outcome = 0
                        break
                    if lows[i + f] <= tp:
                        outcome = 1
                        break

            X_list.append(feats.iloc[i].values)
            y_list.append(outcome)

        else:
            # Unfiltered baseline: Upward expansion
            reward_target = entry + (risk * target_rr)
            stop_level = entry - risk
            outcome = 0
            for f in range(1, forward_bars + 1):
                cur_high = highs[i + f]
                cur_low = lows[i + f]
                if cur_low <= stop_level:
                    outcome = 0
                    break
                if cur_high >= reward_target:
                    outcome = 1
                    break

            X_list.append(feats.iloc[i].values)
            y_list.append(outcome)

    if len(X_list) == 0:
        return np.empty((0, len(FEATURE_NAMES))), np.empty((0,))

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)
