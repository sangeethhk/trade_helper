from typing import List, Dict, Any
import pandas as pd
import yfinance as yf
from core.config import config, DEFAULT_ASSETS

SCANNER_UNIVERSE = [
    # Forex
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "XRP-USD", "AVAX-USD"
]

class ApexPredatorScreener:
    """
    Apex Predator Market Scanner based on Andrew Elder's Book (Chapter 24).
    Filters high-velocity assets meeting:
    1. High Relative Volume: RVOL >= 1.5x - 2.0x
    2. High Volatility: Intraday ATR / Price >= dynamic threshold
    3. Strong EMA9 vs EMA20 Momentum
    """
    @staticmethod
    def scan_market(universe: List[str] = SCANNER_UNIVERSE) -> List[Dict[str, Any]]:
        results = []
        for symbol in universe:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5d", interval="15m", auto_adjust=True)
                if df is None or len(df) < 25:
                    continue

                close = df['Close'].iloc[-1]
                high = df['High']
                low = df['Low']
                volume = df['Volume']

                # ATR 14
                tr = pd.concat([high - low, (high - df['Close'].shift()).abs(), (low - df['Close'].shift()).abs()], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().iloc[-1]
                atr_pct = (atr / close) * 100.0

                # Relative Volume (RVOL)
                avg_vol = volume.rolling(20).mean().iloc[-1]
                cur_vol = volume.iloc[-1]
                rvol = (cur_vol / avg_vol) if avg_vol > 0 else 1.0

                # EMA trend
                ema9 = df['Close'].ewm(span=9).mean().iloc[-1]
                ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
                trend_bias = "BULLISH" if ema9 > ema20 else "BEARISH"

                asset_meta = DEFAULT_ASSETS.get(symbol, None)
                asset_name = asset_meta.name if asset_meta else symbol

                score = (rvol * 35.0) + (atr_pct * 30.0) + (15.0 if trend_bias == "BULLISH" else 5.0)

                results.append({
                    "symbol": symbol,
                    "name": asset_name,
                    "price": round(float(close), 4 if close < 10 else 2),
                    "rvol": round(float(rvol), 2),
                    "atr_pct": round(float(atr_pct), 2),
                    "trend_bias": trend_bias,
                    "predator_score": round(float(score), 1),
                    "status": "APEX HIGH VOLATILITY" if score > 70 else ("ACTIVE PLAY" if score > 45 else "QUIET")
                })
            except Exception:
                continue

        # Sort by predator score descending
        results.sort(key=lambda x: x["predator_score"], reverse=True)
        return results
