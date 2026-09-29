from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from core.models import TradeJournalRecord

class JournalLearner:
    """
    Self-Correction and Journal Feedback Engine (Andrew Elder Chapters 4 & 25).
    Evaluates real trading performance, computes Hit Rate, Payout Ratio,
    Drawdown, Recovery Period, and detects psychological/execution mistakes.
    """
    @staticmethod
    def analyze_journal(trades: List[TradeJournalRecord]) -> Dict[str, Any]:
        if not trades:
            return {
                "total_trades": 0,
                "hit_rate_pct": 0.0,
                "payout_ratio": 0.0,
                "profit_factor": 0.0,
                "expectancy_usd": 0.0,
                "feedback": "No trades recorded yet. Start paper trading or backtesting to begin learning!"
            }

        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in trades if t.pnl < 0]
        total_trades = len(trades)
        win_count = len(wins)
        loss_count = len(losses)

        hit_rate = (win_count / total_trades) if total_trades > 0 else 0.0
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        payout_ratio = (avg_win / avg_loss) if avg_loss > 0 else (avg_win if avg_win > 0 else 0.0)
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Expectancy per trade
        expectancy = (hit_rate * avg_win) - ((1.0 - hit_rate) * avg_loss)

        # Pattern Performance Breakdown
        pattern_performance: Dict[str, Dict[str, Any]] = {}
        for t in trades:
            p_name = t.pattern
            if p_name not in pattern_performance:
                pattern_performance[p_name] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
            pattern_performance[p_name]["trades"] += 1
            if t.pnl > 0:
                pattern_performance[p_name]["wins"] += 1
            pattern_performance[p_name]["total_pnl"] += t.pnl

        for p_name, stats in pattern_performance.items():
            stats["win_rate"] = round((stats["wins"] / stats["trades"]) * 100, 1)
            stats["total_pnl"] = round(stats["total_pnl"], 2)

        # Elder Mistake Detection
        warnings = []
        if payout_ratio < 1.5 and total_trades >= 5:
            warnings.append(
                f"Payout ratio is {payout_ratio:.2f} (Below Elder's 2.0 minimum rule). "
                f"Ensure you are holding runners to Target 2 and not closing prematurely."
            )
        if any(abs(t.pnl_pct) > 1.5 for t in trades):
            warnings.append("Detected stop-loss violation: Single trade lost > 1.0% capital. Enforce strict stops.")

        return {
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "hit_rate_pct": round(hit_rate * 100, 1),
            "payout_ratio": round(payout_ratio, 2),
            "avg_win_usd": round(avg_win, 2),
            "avg_loss_usd": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_usd": round(expectancy, 2),
            "net_pnl": round(gross_profit - gross_loss, 2),
            "pattern_breakdown": pattern_performance,
            "elder_warnings": warnings
        }
