import math
from typing import Dict, Any
from core.config import config, AssetProfile

class PositionSizer:
    """
    Quantitative Risk & Position Sizing Calculator (Andrew Elder Chapter 2 & 3).
    Formulas:
    Position Risk = Number of Units * |Entry Price - Stop Loss|
    Max Risk Allowed = Account Capital * Risk % (Default 0.25% beginner rule, max 1.0%)
    Position Size = Max Risk Allowed / |Entry Price - Stop Loss|
    """
    def __init__(self, capital: float = 10000.0, risk_pct: float = 0.0025):
        self.capital = capital
        self.risk_pct = risk_pct  # 0.25%

    def calculate_size(self, symbol: str, entry_price: float, stop_loss: float) -> Dict[str, Any]:
        stop_dist = abs(entry_price - stop_loss)
        if stop_dist <= 0:
            return {"units": 0, "lots": 0, "dollar_risk": 0, "error": "Stop loss equals entry price"}

        max_dollar_risk = self.capital * self.risk_pct
        asset_info: AssetProfile = config.assets.get(symbol, config.assets["EURUSD=X"])

        if asset_info.asset_type == "forex":
            # For Forex, stop_dist in pips = stop_dist / pip_size
            stop_pips = stop_dist / asset_info.pip_size
            # In standard lot (100,000 units), 1 pip = $10. In mini lot (10,000 units), 1 pip = $1.
            pip_value_per_unit = 0.0001 if asset_info.pip_size == 0.0001 else 0.01 / entry_price
            raw_units = max_dollar_risk / (stop_pips * 1.0) * 10000  # mini lots
            raw_units = max(100.0, min(1000000.0, raw_units))
            lots = round(raw_units / 100000.0, 2)  # Standard lots
            units = round(raw_units, 0)
            unit_label = f"{lots} Standard Lots ({units:,.0f} units)"
        else:
            # Crypto / Stocks: Size = Dollar Risk / Stop Distance
            raw_units = max_dollar_risk / stop_dist
            units = round(raw_units, 4 if entry_price > 100 else 2)
            lots = units
            unit_label = f"{units} Coins / Units"

        actual_risk_usd = round(raw_units * (stop_dist if asset_info.asset_type != "forex" else (stop_dist * 1.0)), 2)
        pct_of_capital = round((actual_risk_usd / self.capital) * 100, 3)

        return {
            "capital": self.capital,
            "risk_pct_setting": self.risk_pct * 100,
            "max_dollar_risk": round(max_dollar_risk, 2),
            "stop_distance": round(stop_dist, 5),
            "position_size": units,
            "display_label": unit_label,
            "actual_dollar_risk": actual_risk_usd,
            "risk_pct_of_capital": pct_of_capital
        }
