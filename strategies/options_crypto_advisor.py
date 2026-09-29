from typing import Dict, Any, List
import pandas as pd

class OptionsCryptoAdvisor:
    """
    Derivative, Options & Hedging Advisory Module (Elder Chapters 13, 15, 22, 27, 28).
    Evaluates current asset volatility (ATR ratio, Bollinger Band width, MFI)
    and advises on optimal options/derivatives structure:
    - High Volatility Anticipation: Straddles & Strangles
    - Range-Bound Market: Credit Spreads (Bull Put / Bear Call) or Iron Condors
    - Bullish Trend: Call Options / Synthetic Longs
    - Portfolio Risk Protection: Married Puts / Collar Strategy
    """
    @staticmethod
    def generate_options_guidance(df: pd.DataFrame, symbol: str, current_price: float) -> Dict[str, Any]:
        if len(df) < 20:
            return {"strategy": "Standard Spot/CFD", "recommendation": "Insufficient data"}

        bband_width = df['bband_width'].iloc[-1] if 'bband_width' in df else 0.05
        rsi = df['rsi14'].iloc[-1] if 'rsi14' in df else 50.0
        mfi = df['mfi14'].iloc[-1] if 'mfi14' in df else 50.0
        atr = df['atr14'].iloc[-1] if 'atr14' in df else (current_price * 0.01)

        is_compressed = bband_width < 0.025  # Volatility squeeze
        is_overbought = rsi > 70 or mfi > 75
        is_oversold = rsi < 30 or mfi < 25

        if is_compressed:
            return {
                "structure": "Long Strangle / Long Straddle",
                "bias": "Volatility Expansion Pending",
                "upper_strike": round(current_price + (atr * 1.5), 2 if current_price > 10 else 4),
                "lower_strike": round(current_price - (atr * 1.5), 2 if current_price > 10 else 4),
                "rationale": (
                    "Bollinger Bands show severe volatility compression (squeeze). "
                    "Andrew Elder Ch 15: Straddles & Strangles profit from large directional explosions regardless of side. "
                    "Ideal setup to capture the upcoming breakout."
                ),
                "max_risk": "Limited to total premium paid",
                "rules": "Exit 50% at 100% gain, do not hold through time decay theta cliff."
            }
        elif is_overbought:
            return {
                "structure": "Bear Call Credit Spread / Protective Put",
                "bias": "Exhaustion / Mean Reversion",
                "short_strike": round(current_price + (atr * 0.8), 2 if current_price > 10 else 4),
                "long_strike": round(current_price + (atr * 2.0), 2 if current_price > 10 else 4),
                "rationale": (
                    "MFI and RSI show overbought conditions near resistance. "
                    "Elder Ch 15: Selling out-of-the-money credit spreads generates steady premium with capped downside."
                ),
                "max_risk": "Capped at strike width minus net credit received",
                "rules": "Target 50% max profit; stop out if price breaches short strike."
            }
        elif is_oversold:
            return {
                "structure": "Bull Put Credit Spread / Long Call",
                "bias": "Support Bounce Expected",
                "short_strike": round(current_price - (atr * 0.8), 2 if current_price > 10 else 4),
                "long_strike": round(current_price - (atr * 2.0), 2 if current_price > 10 else 4),
                "rationale": (
                    "Oversold bounce likely near support. "
                    "Elder Ch 28: Slightly OTM or ITM calls provide leverage while strictly capping max loss to premium."
                ),
                "max_risk": "Capped at strike width minus net credit received",
                "rules": "Close before expiration to avoid tail gamma risk."
            }
        else:
            return {
                "structure": "Iron Condor / Range Collar",
                "bias": "Neutral Range Bound",
                "upper_short": round(current_price + (atr * 1.8), 2 if current_price > 10 else 4),
                "lower_short": round(current_price - (atr * 1.8), 2 if current_price > 10 else 4),
                "rationale": (
                    "Asset is oscillating peacefully inside channel. "
                    "Elder Ch 15: Deploy an Iron Condor or Collar around current support and resistance bounds."
                ),
                "max_risk": "Capped to spread width",
                "rules": "Harvest theta decay during calm consolidation periods."
            }
