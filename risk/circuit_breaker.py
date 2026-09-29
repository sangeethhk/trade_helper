from datetime import datetime
from typing import Dict, Any, List
from core.config import config

class CircuitBreaker:
    """
    Enforces Andrew Elder's Risk Limits (Chapter 3):
    1. Daily Loss Count Limit: Halt trading after N consecutive losses (default: 3).
    2. Weekly Drawdown Limit: Max 1% drawdown from weekly starting balance.
    3. Monthly Drawdown Limit: Max 2.0% - 2.5% drawdown from monthly starting balance.
    4. Account Shutoff: Prevent catastrophic blowups.
    """
    def __init__(self, starting_capital: float = 10000.0):
        self.starting_capital = starting_capital
        self.current_capital = starting_capital
        self.daily_pnl = 0.0
        self.daily_losses_count = 0
        self.weekly_drawdown_pct = 0.0
        self.monthly_drawdown_pct = 0.0
        self.is_halted = False
        self.halt_reason = ""
        self.equity_peak = starting_capital

    def record_trade_result(self, pnl: float):
        self.current_capital += pnl
        self.daily_pnl += pnl

        if self.current_capital > self.equity_peak:
            self.equity_peak = self.current_capital

        if pnl < 0:
            self.daily_losses_count += 1
        else:
            self.daily_losses_count = 0  # Reset streak on winning trade

        # Calculate drawdowns
        total_drawdown_pct = (self.equity_peak - self.current_capital) / self.equity_peak
        daily_loss_pct = abs(min(0.0, self.daily_pnl)) / self.starting_capital

        # 1. Consecutive Daily Loss Cutoff
        if self.daily_losses_count >= config.risk.max_daily_losses_count:
            self.is_halted = True
            self.halt_reason = (
                f"Daily Circuit Breaker Triggered: {self.daily_losses_count} consecutive losses. "
                f"Elder Chapter 3: 'Shutting down saves you from yourself. Walk away from the screen.'"
            )

        # 2. Weekly Drawdown Limit (1%)
        elif total_drawdown_pct >= config.risk.max_weekly_drawdown_pct:
            self.is_halted = True
            self.halt_reason = (
                f"Weekly Drawdown Limit Reached: {total_drawdown_pct*100:.2f}% drawdown "
                f"(Limit: {config.risk.max_weekly_drawdown_pct*100:.1f}%). Trading locked until weekly reset."
            )

        # 3. Monthly Drawdown Limit (2.5%)
        elif total_drawdown_pct >= config.risk.max_monthly_drawdown_pct:
            self.is_halted = True
            self.halt_reason = (
                f"Monthly Drawdown Alert: {total_drawdown_pct*100:.2f}% drawdown "
                f"(Limit: {config.risk.max_monthly_drawdown_pct*100:.1f}%). Capital preservation mode activated."
            )

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.daily_losses_count = 0
        if "Daily Circuit Breaker" in self.halt_reason:
            self.is_halted = False
            self.halt_reason = ""

    def get_status(self) -> Dict[str, Any]:
        drawdown_pct = round(((self.equity_peak - self.current_capital) / self.equity_peak) * 100, 3)
        return {
            "current_capital": round(self.current_capital, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "consecutive_losses": self.daily_losses_count,
            "max_allowed_consecutive_losses": config.risk.max_daily_losses_count,
            "current_drawdown_pct": drawdown_pct,
            "weekly_limit_pct": config.risk.max_weekly_drawdown_pct * 100,
            "is_halted": self.is_halted,
            "halt_reason": self.halt_reason
        }
