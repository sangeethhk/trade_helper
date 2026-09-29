from typing import Dict, Any
from core.config import config

class GainProtector:
    """
    Session Gain Protection Rule (Andrew Elder Chapter 4, p. 40):
    If session gains exceed threshold (default: +0.5% of account),
    a gain-protection lock is activated.
    If subsequent trades give back profits below the lock floor (+0.25%)
    or incur 2 losses, the session is forcibly locked to ensure ending green.
    """
    def __init__(self, starting_capital: float = 10000.0):
        self.starting_capital = starting_capital
        self.high_water_pnl = 0.0
        self.protection_activated = False
        self.locked_for_session = False
        self.lock_reason = ""
        self.post_activation_losses = 0

    def update(self, current_session_pnl: float, last_trade_pnl: float):
        if current_session_pnl > self.high_water_pnl:
            self.high_water_pnl = current_session_pnl

        target_gain = self.starting_capital * config.risk.gain_protection_threshold_pct
        floor_gain = self.starting_capital * config.risk.gain_protection_retrace_pct

        if self.high_water_pnl >= target_gain:
            self.protection_activated = True

        if self.protection_activated:
            if last_trade_pnl < 0:
                self.post_activation_losses += 1

            if current_session_pnl < floor_gain:
                self.locked_for_session = True
                self.lock_reason = (
                    f"Gain Protection Triggered: Session gains retreated from +${self.high_water_pnl:.2f} "
                    f"to +${current_session_pnl:.2f} (below +${floor_gain:.2f} floor). "
                    f"Elder Ch 4: 'Lock in your winning day. Never turn a green day red.'"
                )
            elif self.post_activation_losses >= 2:
                self.locked_for_session = True
                self.lock_reason = (
                    f"Gain Protection Triggered: 2 consecutive losses after hitting session target. "
                    f"Locked in profits of +${current_session_pnl:.2f} for the day."
                )

    def get_status(self, current_session_pnl: float) -> Dict[str, Any]:
        target_gain = self.starting_capital * config.risk.gain_protection_threshold_pct
        floor_gain = self.starting_capital * config.risk.gain_protection_retrace_pct
        return {
            "protection_activated": self.protection_activated,
            "session_high_water_pnl": round(self.high_water_pnl, 2),
            "current_session_pnl": round(current_session_pnl, 2),
            "activation_target": round(target_gain, 2),
            "protected_floor": round(floor_gain, 2),
            "locked_for_session": self.locked_for_session,
            "lock_reason": self.lock_reason
        }
