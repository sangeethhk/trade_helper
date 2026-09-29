from typing import Dict, Any
from risk.news_manager import news_manager

class EventLockoutFilter:
    """
    Economic Event Lockout Safety Filter (Andrew Elder Chapter 4, p. 41).
    Halts trading before and after major macroeconomic and crypto events:
    - US Non-Farm Payrolls (NFP)
    - Federal Reserve FOMC Interest Rate Decisions
    - CPI / Inflation reports
    - ECB / BoE / BoJ rate decisions
    - Deribit / Crypto monthly options expiration
    """
    def __init__(self):
        self.lockout_minutes = news_manager.default_blackout_min

    def check_event_status(self, asset_type: str = "forex", symbol: str = "EURUSD=X") -> Dict[str, Any]:
        """
        Determines if current time is within the blackout window of a scheduled event.
        Delegates to the centralized NewsAlertManager.
        """
        allowed, reason, active_event = news_manager.is_trade_allowed(symbol, asset_type)
        return {
            "in_blackout": not allowed,
            "upcoming_event": active_event["title"] if active_event else "None",
            "active_event": active_event,
            "lockout_buffer_minutes": self.lockout_minutes,
            "action_advice": reason if not allowed else "Market environment clear for pattern setups."
        }
