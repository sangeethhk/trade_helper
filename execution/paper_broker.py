import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.models import PaperPosition, Direction, TradeJournalRecord, TradeSignal
from core.config import config
from execution.journal import journal_db
from risk.circuit_breaker import CircuitBreaker
from risk.gain_protector import GainProtector
from risk.news_manager import news_manager

class PaperBroker:
    """
    Paper Trading & Execution Engine.
    Executes Andrew Elder's trade management rules (Chapter 11, p. 13):
    1. Scale-out partial exit: Sells 50% of shares at Target 1.
    2. Breakeven adjustment: Shifts Stop Loss to entry price once Target 1 is achieved.
    3. Dynamic trailing stop: Trails remaining 50% with ATR buffer.
    4. Automatically updates circuit breakers and records into SQLite Trading Journal.
    """
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, PaperPosition] = {}
        self.circuit_breaker = CircuitBreaker(initial_capital)
        self.gain_protector = GainProtector(initial_capital)
        self.session_realized_pnl = 0.0

    def open_position_from_signal(self, signal: TradeSignal) -> Optional[PaperPosition]:
        # Risk Check 1: Circuit Breakers (consecutive losses or drawdown cap)
        if self.circuit_breaker.is_halted:
            return None
        # Risk Check 2: Session Gain Protection Lock
        if self.gain_protector.locked_for_session:
            return None
        # Risk Check 3: High-Impact News Blackout (Elder Rule: Skip trades into major releases)
        allowed, reason, _ = news_manager.is_trade_allowed(signal.symbol)
        if not allowed:
            self.circuit_breaker.halt_reason = reason
            return None

        pos_id = str(uuid.uuid4())[:8]
        pos = PaperPosition(
            id=pos_id,
            symbol=signal.symbol,
            direction=Direction.BULLISH if signal.action == "BUY" else Direction.BEARISH,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_1=signal.target_1,
            target_2=signal.target_2,
            original_size=signal.position_size,
            remaining_size=signal.position_size,
            entry_time=signal.timestamp,
            pattern_name=signal.pattern.value
        )
        self.positions[pos_id] = pos
        return pos

    def on_price_update(self, symbol: str, current_price: float, atr: float) -> List[Dict[str, Any]]:
        events = []
        closed_ids = []

        for pos_id, pos in list(self.positions.items()):
            if pos.symbol != symbol:
                continue

            pos.current_price = current_price

            if pos.direction == Direction.BULLISH:
                # Unrealized PnL
                pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.remaining_size

                # Target 1: Sell 50% & Move Stop to Breakeven
                if not pos.partial_taken and current_price >= pos.target_1:
                    partial_qty = pos.remaining_size * 0.5
                    realized_gain = (pos.target_1 - pos.entry_price) * partial_qty
                    self.current_capital += realized_gain
                    self.session_realized_pnl += realized_gain
                    pos.remaining_size -= partial_qty
                    pos.partial_taken = True
                    pos.stop_loss = pos.entry_price  # Move Stop Loss to Breakeven!
                    pos.breakeven_set = True
                    
                    self.circuit_breaker.record_trade_result(realized_gain)
                    self.gain_protector.update(self.session_realized_pnl, realized_gain)
                    events.append({
                        "type": "PARTIAL_PROFIT",
                        "pos_id": pos_id,
                        "price": current_price,
                        "pnl": realized_gain,
                        "msg": f"Hit Target 1! Closed 50% at ${pos.target_1:.4f}. Stop moved to Breakeven."
                    })

                # Target 2: Close remaining position
                elif current_price >= pos.target_2:
                    final_gain = (pos.target_2 - pos.entry_price) * pos.remaining_size
                    self.current_capital += final_gain
                    self.session_realized_pnl += final_gain
                    closed_ids.append((pos_id, current_price, "TARGET_2_FULL_PROFIT"))
                    events.append({
                        "type": "FULL_EXIT_TARGET_2",
                        "pos_id": pos_id,
                        "price": current_price,
                        "pnl": final_gain,
                        "msg": f"Hit Target 2! Full exit at ${pos.target_2:.4f}."
                    })

                # Stop Loss hit
                elif current_price <= pos.stop_loss:
                    loss_amount = (pos.stop_loss - pos.entry_price) * pos.remaining_size
                    self.current_capital += loss_amount
                    self.session_realized_pnl += loss_amount
                    closed_ids.append((pos_id, current_price, "STOP_LOSS_TRIGGERED"))
                    events.append({
                        "type": "STOP_LOSS",
                        "pos_id": pos_id,
                        "price": current_price,
                        "pnl": loss_amount,
                        "msg": f"Stop loss triggered at ${pos.stop_loss:.4f}."
                    })

                # Trailing ATR stop if already past Target 1
                elif pos.partial_taken:
                    new_trail = current_price - (atr * 1.5)
                    if new_trail > pos.stop_loss:
                        pos.stop_loss = round(new_trail, 5)

            elif pos.direction == Direction.BEARISH:
                pos.unrealized_pnl = (pos.entry_price - pos.current_price) * pos.remaining_size

                # Target 1
                if not pos.partial_taken and current_price <= pos.target_1:
                    partial_qty = pos.remaining_size * 0.5
                    realized_gain = (pos.entry_price - pos.target_1) * partial_qty
                    self.current_capital += realized_gain
                    self.session_realized_pnl += realized_gain
                    pos.remaining_size -= partial_qty
                    pos.partial_taken = True
                    pos.stop_loss = pos.entry_price
                    pos.breakeven_set = True
                    
                    self.circuit_breaker.record_trade_result(realized_gain)
                    self.gain_protector.update(self.session_realized_pnl, realized_gain)
                    events.append({
                        "type": "PARTIAL_PROFIT",
                        "pos_id": pos_id,
                        "price": current_price,
                        "pnl": realized_gain,
                        "msg": f"Hit Target 1 (Short)! Closed 50% at ${pos.target_1:.4f}. Stop at Breakeven."
                    })

                # Target 2
                elif current_price <= pos.target_2:
                    final_gain = (pos.entry_price - pos.target_2) * pos.remaining_size
                    self.current_capital += final_gain
                    self.session_realized_pnl += final_gain
                    closed_ids.append((pos_id, current_price, "TARGET_2_FULL_PROFIT"))

                # Stop loss
                elif current_price >= pos.stop_loss:
                    loss_amount = (pos.entry_price - pos.stop_loss) * pos.remaining_size
                    self.current_capital += loss_amount
                    self.session_realized_pnl += loss_amount
                    closed_ids.append((pos_id, current_price, "STOP_LOSS_TRIGGERED"))

        # Process closed positions
        for p_id, exit_px, exit_reason in closed_ids:
            p = self.positions.pop(p_id)
            total_trade_pnl = ((exit_px - p.entry_price) if p.direction == Direction.BULLISH else (p.entry_price - exit_px)) * p.original_size
            pnl_pct = (total_trade_pnl / self.initial_capital) * 100.0

            self.circuit_breaker.record_trade_result(total_trade_pnl)
            self.gain_protector.update(self.session_realized_pnl, total_trade_pnl)

            # Record in SQLite Journal
            journal_db.record_trade(TradeJournalRecord(
                trade_id=p.id,
                symbol=p.symbol,
                direction=p.direction.value,
                entry_time=p.entry_time,
                exit_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                entry_price=p.entry_price,
                exit_price=exit_px,
                stop_loss=p.stop_loss,
                position_size=p.original_size,
                pnl=round(total_trade_pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                pattern=p.pattern_name,
                reasons_for_entry=f"Elder pattern execution: {p.pattern_name}",
                reasons_for_exit=exit_reason,
                mental_state_entry="Disciplined & Planned",
                mental_state_exit="Objective Evaluation",
                followed_rules=True,
                post_trade_lesson="Exited in adherence to Elder risk and partial-scaling framework."
            ))

        return events

    def get_summary(self) -> Dict[str, Any]:
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return {
            "initial_capital": self.initial_capital,
            "current_capital": round(self.current_capital, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_equity": round(self.current_capital + unrealized, 2),
            "session_realized_pnl": round(self.session_realized_pnl, 2),
            "open_positions": [p.model_dump() for p in self.positions.values()],
            "circuit_breaker": self.circuit_breaker.get_status(),
            "gain_protector": self.gain_protector.get_status(self.session_realized_pnl)
        }

paper_broker = PaperBroker()
