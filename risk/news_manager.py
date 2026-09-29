"""
Economic Calendar & High-Impact News Alert Engine
ElderAlpha Trading Helper AI - Codifying Andrew Elder: Day Trading Strategies (Book 2)

Andrew Elder Rule (Chapter 4, p. 41 & Chapter 11, p. 13):
"Never trade into high-impact economic news releases (FOMC, NFP, CPI, Central Bank Rate Decisions).
Spreads widen dramatically, liquidity disappears, and slippage will violate calculated risk stops.
Step aside 30 minutes before the release and wait 30-45 minutes after the announcement."
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger("tradinghelper.news")

class EconomicEvent(BaseModel):
    id: str
    title: str
    currency: str  # "USD", "EUR", "GBP", "JPY", "ALL", "CRYPTO"
    impact: str    # "HIGH", "MEDIUM", "LOW"
    scheduled_time: str  # ISO string or "YYYY-MM-DD HH:MM:SS"
    blackout_before_min: int = 30
    blackout_after_min: int = 30
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None

class NewsAlertManager:
    """
    Manages Economic Calendar events, evaluates live blackout windows,
    triggers High-Impact News Alerts, and blocks trade execution.
    """
    def __init__(self, lockout_enabled: bool = True, default_blackout_min: int = 30):
        self.lockout_enabled = lockout_enabled
        self.default_blackout_min = default_blackout_min
        self.simulated_event: Optional[Dict[str, Any]] = None
        self._events: List[EconomicEvent] = []
        self._load_recurring_and_scheduled_events()

    def set_lockout_enabled(self, enabled: bool):
        self.lockout_enabled = enabled
        logger.info(f"News Trade Lockout enabled set to: {self.lockout_enabled}")

    def _load_recurring_and_scheduled_events(self):
        """
        Populates high-impact global macro and crypto calendar schedule.
        Generates upcoming events dynamically for current calendar week.
        """
        now = datetime.now()
        base_date = now.date()

        # Generate realistic upcoming key economic events for the current week
        schedule_templates = [
            # Wednesday FOMC / CPI
            {"day_offset": (2 - now.weekday()) % 7, "hour": 14, "minute": 0, "curr": "USD", "title": "FOMC Interest Rate Decision & Fed Statement", "impact": "HIGH", "before": 45, "after": 45},
            {"day_offset": (2 - now.weekday()) % 7, "hour": 14, "minute": 30, "curr": "USD", "title": "Federal Reserve Chair Press Conference", "impact": "HIGH", "before": 30, "after": 45},
            # Thursday CPI / ECB
            {"day_offset": (3 - now.weekday()) % 7, "hour": 8, "minute": 30, "curr": "USD", "title": "US Core CPI Inflation (MoM & YoY)", "impact": "HIGH", "before": 30, "after": 30},
            {"day_offset": (3 - now.weekday()) % 7, "hour": 8, "minute": 30, "curr": "USD", "title": "US Initial Jobless Claims", "impact": "MEDIUM", "before": 15, "after": 15},
            {"day_offset": (3 - now.weekday()) % 7, "hour": 13, "minute": 15, "curr": "EUR", "title": "ECB Monetary Policy Decision & Deposit Facility Rate", "impact": "HIGH", "before": 30, "after": 30},
            {"day_offset": (3 - now.weekday()) % 7, "hour": 12, "minute": 0, "curr": "GBP", "title": "Bank of England (BoE) Official Bank Rate", "impact": "HIGH", "before": 30, "after": 30},
            # Friday NFP
            {"day_offset": (4 - now.weekday()) % 7, "hour": 8, "minute": 30, "curr": "USD", "title": "US Non-Farm Payrolls (NFP) & Unemployment Rate", "impact": "HIGH", "before": 45, "after": 45},
            # Crypto Macro / Options Expiry
            {"day_offset": (4 - now.weekday()) % 7, "hour": 8, "minute": 0, "curr": "CRYPTO", "title": "Deribit BTC & ETH Options Monthly Expiry Max Pain", "impact": "HIGH", "before": 30, "after": 30},
            {"day_offset": (1 - now.weekday()) % 7, "hour": 10, "minute": 0, "curr": "USD", "title": "US ISM Manufacturing PMI", "impact": "MEDIUM", "before": 20, "after": 20},
            {"day_offset": (4 - now.weekday()) % 7, "hour": 3, "minute": 30, "curr": "JPY", "title": "Bank of Japan (BoJ) Policy Rate & Outlook Report", "impact": "HIGH", "before": 30, "after": 30}
        ]

        events = []
        for i, t in enumerate(schedule_templates):
            event_dt = datetime.combine(base_date + timedelta(days=t["day_offset"]), datetime.min.time()) + timedelta(hours=t["hour"], minutes=t["minute"])
            events.append(EconomicEvent(
                id=f"evt_{i+1}_{t['curr']}",
                title=t["title"],
                currency=t["curr"],
                impact=t["impact"],
                scheduled_time=event_dt.strftime("%Y-%m-%d %H:%M:%S"),
                blackout_before_min=t["before"],
                blackout_after_min=t["after"]
            ))

        # Sort chronologically
        events.sort(key=lambda e: e.scheduled_time)
        self._events = events

    def get_upcoming_events(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Returns formatted upcoming economic calendar events."""
        now = datetime.now()
        results = []
        for ev in self._events:
            try:
                ev_dt = datetime.strptime(ev.scheduled_time, "%Y-%m-%d %H:%M:%S")
                # Include events that happened recently (within 2h) or are in the future
                if ev_dt >= now - timedelta(hours=2):
                    diff_mins = int((ev_dt - now).total_seconds() / 60)
                    if diff_mins > 0:
                        countdown = f"in {diff_mins // 60}h {diff_mins % 60}m" if diff_mins >= 60 else f"in {diff_mins}m"
                    elif diff_mins >= -ev.blackout_after_min:
                        countdown = f"RELEASED {abs(diff_mins)}m ago (BLACKOUT)"
                    else:
                        countdown = f"{abs(diff_mins)}m ago"

                    results.append({
                        "id": ev.id,
                        "title": ev.title,
                        "currency": ev.currency,
                        "impact": ev.impact,
                        "scheduled_time": ev.scheduled_time,
                        "countdown": countdown,
                        "in_blackout": self._is_in_blackout(ev, now)
                    })
            except Exception:
                continue

        return results[:limit]

    def _is_in_blackout(self, event: EconomicEvent, now: datetime) -> bool:
        try:
            ev_dt = datetime.strptime(event.scheduled_time, "%Y-%m-%d %H:%M:%S")
            start_blackout = ev_dt - timedelta(minutes=event.blackout_before_min)
            end_blackout = ev_dt + timedelta(minutes=event.blackout_after_min)
            return start_blackout <= now <= end_blackout
        except Exception:
            return False

    def is_trade_allowed(self, symbol: str, asset_type: str = "forex") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Determines if a trade is permitted or must be SKIPPED due to a news blackout.
        Returns:
            (allowed: bool, reason: str, active_event: Optional[Dict])
        """
        if not self.lockout_enabled:
            return True, "News trade lockout is currently disabled by user.", None

        # 1. Check for manual/simulated news blackout override
        if self.simulated_event:
            expires_at = self.simulated_event.get("expires_at", 0)
            if time.time() < expires_at:
                remaining_sec = int(expires_at - time.time())
                return False, f"Active High-Impact News Blackout: {self.simulated_event['title']} (Simulated, {remaining_sec}s remaining)", self.simulated_event
            else:
                self.simulated_event = None

        # 2. Check scheduled calendar events
        now = datetime.now()
        relevant_currencies = self._get_relevant_currencies(symbol, asset_type)

        for ev in self._events:
            if ev.impact != "HIGH":
                continue

            if ev.currency not in relevant_currencies and ev.currency != "ALL":
                continue

            if self._is_in_blackout(ev, now):
                ev_dt = datetime.strptime(ev.scheduled_time, "%Y-%m-%d %H:%M:%S")
                diff_sec = int((ev_dt - now).total_seconds())
                if diff_sec > 0:
                    status_text = f"Releases in {diff_sec // 60}m"
                else:
                    status_text = f"Released {abs(diff_sec) // 60}m ago (Slippage Buffer)"

                active_dict = {
                    "id": ev.id,
                    "title": ev.title,
                    "currency": ev.currency,
                    "impact": ev.impact,
                    "scheduled_time": ev.scheduled_time,
                    "status": status_text
                }
                reason = f"High-Impact {ev.currency} News Event Active: '{ev.title}' ({status_text}). All trades skipped."
                return False, reason, active_dict

        return True, "No high-impact economic news blackout in progress. Trading permitted.", None

    def _get_relevant_currencies(self, symbol: str, asset_type: str) -> List[str]:
        """Maps an asset symbol to currencies affected by high-impact macro releases."""
        sym = symbol.upper()
        currencies = ["ALL"]

        if "USD" in sym:
            currencies.append("USD")
        if "EUR" in sym:
            currencies.append("EUR")
        if "GBP" in sym:
            currencies.append("GBP")
        if "JPY" in sym:
            currencies.append("JPY")

        if asset_type == "crypto" or "BTC" in sym or "ETH" in sym or "SOL" in sym:
            currencies.append("CRYPTO")
            if "USD" not in currencies:
                currencies.append("USD")

        return currencies

    def simulate_news_event(self, title: str = "US Non-Farm Payrolls (NFP) Shock", duration_minutes: int = 15, currency: str = "USD") -> Dict[str, Any]:
        """Activates a simulated news blackout for testing the trade skipping mechanism."""
        expires_at = time.time() + (duration_minutes * 60)
        self.simulated_event = {
            "id": "simulated_event_live",
            "title": title,
            "currency": currency,
            "impact": "HIGH",
            "scheduled_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expires_at,
            "duration_minutes": duration_minutes,
            "status": f"Simulated Event Active ({duration_minutes}m blackout)"
        }
        logger.info(f"Simulated News Event activated: {title} for {duration_minutes}m")
        return self.simulated_event

    def clear_simulated_event(self):
        """Clears any active simulated news event."""
        self.simulated_event = None
        logger.info("Simulated News Event cleared.")

    def get_status(self, symbol: str = "EURUSD=X", asset_type: str = "forex") -> Dict[str, Any]:
        """Returns the full live news status for the UI HUD and trading engine."""
        allowed, reason, active_ev = self.is_trade_allowed(symbol, asset_type)
        upcoming = self.get_upcoming_events(limit=6)

        return {
            "lockout_enabled": self.lockout_enabled,
            "trade_allowed": allowed,
            "is_blackout": not allowed,
            "reason": reason,
            "active_event": active_ev,
            "is_simulated": self.simulated_event is not None,
            "upcoming_events": upcoming
        }

# Global Singleton
news_manager = NewsAlertManager(lockout_enabled=True, default_blackout_min=30)
