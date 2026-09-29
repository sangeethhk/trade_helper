import sqlite3
import os
from typing import List, Optional
from datetime import datetime
from core.models import TradeJournalRecord
from core.config import config

class JournalDatabase:
    """
    SQLite Trade Journal Database (Andrew Elder Chapter 4, p. 43).
    Records: Date, Instrument, Entry, Stop, Distance, Size, Reasons, Exit, P/L, Mental State.
    """
    def __init__(self, db_path: str = config.db_path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    symbol TEXT,
                    direction TEXT,
                    entry_time TEXT,
                    exit_time TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    stop_loss REAL,
                    position_size REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    pattern TEXT,
                    reasons_for_entry TEXT,
                    reasons_for_exit TEXT,
                    mental_state_entry TEXT,
                    mental_state_exit TEXT,
                    followed_rules BOOLEAN,
                    post_trade_lesson TEXT
                )
            """)
            conn.commit()

    def record_trade(self, trade: TradeJournalRecord) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO trade_journal (
                    trade_id, symbol, direction, entry_time, exit_time,
                    entry_price, exit_price, stop_loss, position_size,
                    pnl, pnl_pct, pattern, reasons_for_entry, reasons_for_exit,
                    mental_state_entry, mental_state_exit, followed_rules, post_trade_lesson
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id, trade.symbol, trade.direction, trade.entry_time, trade.exit_time,
                trade.entry_price, trade.exit_price, trade.stop_loss, trade.position_size,
                trade.pnl, trade.pnl_pct, trade.pattern, trade.reasons_for_entry, trade.reasons_for_exit,
                trade.mental_state_entry, trade.mental_state_exit, trade.followed_rules, trade.post_trade_lesson
            ))
            conn.commit()
            return cursor.lastrowid

    def get_all_trades(self) -> List[TradeJournalRecord]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trade_journal ORDER BY id DESC")
            rows = cursor.fetchall()
            trades = []
            for r in rows:
                trades.append(TradeJournalRecord(
                    id=r['id'],
                    trade_id=r['trade_id'],
                    symbol=r['symbol'],
                    direction=r['direction'],
                    entry_time=r['entry_time'],
                    exit_time=r['exit_time'],
                    entry_price=r['entry_price'],
                    exit_price=r['exit_price'],
                    stop_loss=r['stop_loss'],
                    position_size=r['position_size'],
                    pnl=r['pnl'],
                    pnl_pct=r['pnl_pct'],
                    pattern=r['pattern'],
                    reasons_for_entry=r['reasons_for_entry'],
                    reasons_for_exit=r['reasons_for_exit'],
                    mental_state_entry=r['mental_state_entry'],
                    mental_state_exit=r['mental_state_exit'],
                    followed_rules=bool(r['followed_rules']),
                    post_trade_lesson=r['post_trade_lesson']
                ))
            return trades

journal_db = JournalDatabase()
