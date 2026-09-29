import os
import time
import logging
from typing import Optional, Dict
import pandas as pd
import numpy as np
import yfinance as yf
from core.indicators import compute_all_indicators

logger = logging.getLogger("tradinghelper.dataloader")

# In-memory cache for fast dashboard loading
_CACHE: Dict[str, Tuple_Data] = {}
class Tuple_Data:
    def __init__(self, df: pd.DataFrame, fetch_time: float):
        self.df = df
        self.fetch_time = fetch_time

TIMEFRAME_MAP = {
    "1m": {"period": "2d", "interval": "1m"},
    "5m": {"period": "5d", "interval": "5m"},
    "15m": {"period": "10d", "interval": "15m"},
    "1h": {"period": "30d", "interval": "1h"},
    "1d": {"period": "1y", "interval": "1d"}
}

def load_market_data(symbol: str, timeframe: str = "15m", force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches real-time and historical OHLCV data using yfinance,
    caches for 30 seconds to preserve API quotas, and computes all indicators.
    Falls back to a realistic synthetic generator if API is unreachable.
    """
    cache_key = f"{symbol}_{timeframe}"
    now = time.time()

    if not force_refresh and cache_key in _CACHE:
        cached = _CACHE[cache_key]
        if now - cached.fetch_time < 25.0:  # 25s cache freshness
            return cached.df.copy()

    tf_config = TIMEFRAME_MAP.get(timeframe, {"period": "10d", "interval": "15m"})

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=tf_config["period"], interval=tf_config["interval"], auto_adjust=True)

        if df is not None and len(df) >= 20:
            df = df.reset_index()
            # Normalize column names
            date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
            if date_col in df.columns:
                df['timestamp'] = df[date_col].dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                df['timestamp'] = df.index.astype(str)

            df.columns = [c.lower() for c in df.columns]
            # Standardize
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df = compute_all_indicators(df)
            _CACHE[cache_key] = Tuple_Data(df, now)
            return df
        else:
            logger.warning(f"Insufficient data returned for {symbol}, generating realistic synthetic market stream.")
    except Exception as e:
        logger.warning(f"Error fetching from yfinance for {symbol}: {e}. Falling back to simulation mode.")

    # Graceful Fallback: Generate realistic Forex/Crypto price action
    df_synth = _generate_synthetic_market_data(symbol, timeframe)
    df_synth = compute_all_indicators(df_synth)
    _CACHE[cache_key] = Tuple_Data(df_synth, now)
    return df_synth

def _generate_synthetic_market_data(symbol: str, timeframe: str, bars: int = 150) -> pd.DataFrame:
    """
    Generates realistic geometric brownian motion price series with intraday swings
    mimicking Forex (e.g. 1.0850) or Crypto (e.g. 64,000).
    """
    base_price = 1.0850 if "EUR" in symbol else (64000.0 if "BTC" in symbol else (2700.0 if "ETH" in symbol else 145.0))
    volatility = 0.0003 if "EUR" in symbol else (0.0025 if "BTC" in symbol else 0.0015)

    np.random.seed(int(time.time()) % 10000)
    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=bars, freq="15min")
    
    returns = np.random.normal(0, volatility, bars)
    # Add cyclical trend waves to create ABCD & Bull Flag opportunities
    t = np.linspace(0, 4 * np.pi, bars)
    cycle = 0.001 * np.sin(t)
    price_series = base_price * np.exp(np.cumsum(returns) + cycle)

    opens, highs, lows, closes, volumes = [], [], [], [], []
    for i in range(bars):
        p = price_series[i]
        c_open = p * (1 + np.random.normal(0, volatility * 0.2))
        c_close = p * (1 + np.random.normal(0, volatility * 0.2))
        c_high = max(c_open, c_close) * (1 + abs(np.random.normal(0, volatility * 0.4)))
        c_low = min(c_open, c_close) * (1 - abs(np.random.normal(0, volatility * 0.4)))
        vol = abs(np.random.normal(1500, 400)) * (2.5 if (i % 25 == 0) else 1.0)
        
        opens.append(c_open)
        highs.append(c_high)
        lows.append(c_low)
        closes.append(c_close)
        volumes.append(vol)

    df = pd.DataFrame({
        'timestamp': [ts.strftime('%Y-%m-%d %H:%M:%S') for ts in timestamps],
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })
    return df
