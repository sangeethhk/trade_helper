"""
Unit Tests for Economic News Alert & Trade Skipping System
ElderAlpha Trading Helper AI - Codifying Andrew Elder Book 2
"""

import unittest
from risk.news_manager import NewsAlertManager, news_manager
from core.models import TradeSignal, ActionType, PatternType
from execution.paper_broker import PaperBroker

class TestNewsManager(unittest.TestCase):
    def setUp(self):
        self.mgr = NewsAlertManager(lockout_enabled=True, default_blackout_min=30)
        self.broker = PaperBroker(initial_capital=10000.0)

    def test_default_trading_allowed(self):
        # Under standard calm conditions, trading should be permitted
        allowed, reason, active_event = self.mgr.is_trade_allowed("EURUSD=X", "forex")
        self.assertTrue(allowed)
        self.assertIsNone(active_event)

    def test_simulated_news_blackout_blocks_trade(self):
        # Trigger simulated FOMC/NFP shock
        self.mgr.simulate_news_event(title="US Non-Farm Payrolls (NFP) Shock", duration_minutes=15, currency="USD")
        
        # USD pair must be blocked
        allowed, reason, active_event = self.mgr.is_trade_allowed("EURUSD=X", "forex")
        self.assertFalse(allowed)
        self.assertIn("NFP", reason)
        self.assertIsNotNone(active_event)

        # Crypto pair must also be blocked due to USD macro correlation
        allowed_btc, reason_btc, _ = self.mgr.is_trade_allowed("BTC-USD", "crypto")
        self.assertFalse(allowed_btc)

        # Clear event
        self.mgr.clear_simulated_event()
        allowed_after, _, _ = self.mgr.is_trade_allowed("EURUSD=X", "forex")
        self.assertTrue(allowed_after)

    def test_broker_rejects_trade_during_news_blackout(self):
        # Activate news shock
        news_manager.simulate_news_event(title="Federal Reserve Rate Decision", duration_minutes=10, currency="USD")

        sig = TradeSignal(
            symbol="BTC-USD",
            timestamp="2026-09-29 12:00:00",
            action=ActionType.BUY,
            pattern=PatternType.ABCD,
            entry_price=80000.0,
            stop_loss=78000.0,
            target_1=84000.0,
            target_2=88000.0,
            risk_per_trade_usd=25.0,
            position_size=0.0125,
            units_label="Coins",
            confidence=0.88,
            payout_ratio=2.0,
            rationale="Clean ABCD pattern"
        )

        pos = self.broker.open_position_from_signal(sig)
        self.assertIsNone(pos, "Broker must reject trade during active news blackout")

        # Clear simulated event
        news_manager.clear_simulated_event()
        pos_allowed = self.broker.open_position_from_signal(sig)
        self.assertIsNotNone(pos_allowed, "Broker should open position once news blackout is cleared")

    def test_toggle_lockout_switch(self):
        self.mgr.simulate_news_event(title="Test Shock", duration_minutes=10)
        self.mgr.set_lockout_enabled(False)
        allowed, reason, _ = self.mgr.is_trade_allowed("EURUSD=X")
        self.assertTrue(allowed, "When news lockout is toggled OFF, trades must be allowed")

        self.mgr.set_lockout_enabled(True)
        allowed_again, _, _ = self.mgr.is_trade_allowed("EURUSD=X")
        self.assertFalse(allowed_again)
        self.mgr.clear_simulated_event()

if __name__ == '__main__':
    unittest.main()
