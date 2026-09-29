import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators specified in Andrew Elder's Day Trading Guide:
    - EMA 9 and EMA 20 (Chapter 5)
    - ATR 14 for dynamic volatility and trailing stops (Chapter 8)
    - Bollinger Bands 20, 2-std (Chapter 5 & 14)
    - RSI 14 and MFI 14 (Chapter 13)
    - Relative Volume (RVOL) against 20-period moving average (Chapter 24)
    - Candlestick body and wick ratios (Chapter 5 & 14)
    """
    df = df.copy()
    if len(df) < 5:
        return df

    # Ensure required columns exist
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns and col.capitalize() in df.columns:
            df[col] = df[col.capitalize()]

    # 1. Exponential Moving Averages (EMA 9, EMA 20)
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_cross_bullish'] = (df['ema9'] > df['ema20']) & (df['ema9'].shift(1) <= df['ema20'].shift(1))
    df['ema_cross_bearish'] = (df['ema9'] < df['ema20']) & (df['ema9'].shift(1) >= df['ema20'].shift(1))

    # 2. Average True Range (ATR 14)
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['tr'] = true_range
    df['atr14'] = true_range.rolling(window=14).mean().bfill()

    # 3. Bollinger Bands (20 periods, 2 standard deviations)
    df['bband_middle'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['bband_upper'] = df['bband_middle'] + (2.0 * std)
    df['bband_lower'] = df['bband_middle'] - (2.0 * std)
    df['bband_width'] = (df['bband_upper'] - df['bband_lower']) / df['bband_middle']

    # 4. Relative Strength Index (RSI 14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi14'] = 100 - (100 / (1 + rs))
    df['rsi14'] = df['rsi14'].fillna(50.0)

    # 5. Relative Volume (RVOL)
    df['volume_sma20'] = df['volume'].rolling(window=20).mean().replace(0, np.nan)
    df['rvol'] = df['volume'] / df['volume_sma20']
    df['rvol'] = df['rvol'].fillna(1.0)

    # 6. Money Flow Index (MFI 14) - Elder Chapter 13
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    raw_money_flow = typical_price * df['volume']
    tp_diff = typical_price.diff()
    pos_flow = raw_money_flow.where(tp_diff > 0, 0).rolling(14).sum()
    neg_flow = raw_money_flow.where(tp_diff < 0, 0).rolling(14).sum()
    mfi_ratio = pos_flow / neg_flow.replace(0, np.nan)
    df['mfi14'] = 100 - (100 / (1 + mfi_ratio))
    df['mfi14'] = df['mfi14'].fillna(50.0)

    # 7. Candlestick Anatomy Microstructure (Chapter 5 & 14)
    candle_range = (df['high'] - df['low']).replace(0, 1e-6)
    df['body_pct'] = (df['close'] - df['open']).abs() / candle_range
    df['upper_wick_pct'] = (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range
    df['lower_wick_pct'] = (df[['open', 'close']].min(axis=1) - df['low']) / candle_range
    df['is_bullish_bar'] = df['close'] >= df['open']

    # Bullish and Bearish Engulfing Detection
    prev_open = df['open'].shift(1)
    prev_close = df['close'].shift(1)
    df['bullish_engulfing'] = (
        (prev_close < prev_open) &
        (df['close'] > df['open']) &
        (df['close'] >= prev_open) &
        (df['open'] <= prev_close)
    )
    df['bearish_engulfing'] = (
        (prev_close > prev_open) &
        (df['close'] < df['open']) &
        (df['close'] <= prev_open) &
        (df['open'] >= prev_close)
    )

    return df

def calculate_floor_pivot_points(high: float, low: float, close: float) -> Dict[str, float]:
    """
    Standard Floor Pivot Points (Chapter 9 & 12)
    P: Pivot
    R1, R2, R3: Resistances
    S1, S2, S3: Supports
    """
    p = (high + low + close) / 3.0
    r1 = (2.0 * p) - low
    s1 = (2.0 * p) - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    r3 = high + (2.0 * (p - low))
    s3 = low - (2.0 * (high - p))

    return {
        "pivot": round(p, 5),
        "r1": round(r1, 5),
        "s1": round(s1, 5),
        "r2": round(r2, 5),
        "s2": round(s2, 5),
        "r3": round(r3, 5),
        "s3": round(s3, 5)
    }
