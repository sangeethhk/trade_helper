import unittest
import numpy as np
import pandas as pd
from core.data_loader import load_market_data
from core.indicators import compute_all_indicators, calculate_floor_pivot_points
from strategies.abcd_pattern import ABCDPatternStrategy
from strategies.bull_flag import BullFlagStrategy
from strategies.channel_range import ChannelRangeStrategy
from learning.calibrator import calibrator
from learning.movement_model import get_or_create_model
from risk.position_sizer import PositionSizer
from risk.circuit_breaker import CircuitBreaker
from risk.gain_protector import GainProtector
from execution.paper_broker import paper_broker

class TestElderAlphaAI(unittest.TestCase):
    def setUp(self):
        self.symbol = "EURUSD=X"
        self.df = load_market_data(self.symbol, "15m")

    def test_indicators_computation(self):
        self.assertGreater(len(self.df), 15)
        self.assertIn("ema9", self.df.columns)
        self.assertIn("ema20", self.df.columns)
        self.assertIn("atr14", self.df.columns)
        self.assertIn("rsi14", self.df.columns)
        self.assertIn("rvol", self.df.columns)
        self.assertIn("body_pct", self.df.columns)

    def test_dynamic_calibration(self):
        # Calibrate for Forex
        forex_cal = calibrator.calibrate_symbol(self.df, "EURUSD=X")
        self.assertIsNotNone(forex_cal)
        self.assertGreater(forex_cal.atr_stop_multiplier, 1.0)
        self.assertLess(forex_cal.atr_stop_multiplier, 2.0)

        # Calibrate for Crypto (BTC)
        df_btc = load_market_data("BTC-USD", "15m")
        crypto_cal = calibrator.calibrate_symbol(df_btc, "BTC-USD")
        self.assertGreater(crypto_cal.atr_stop_multiplier, forex_cal.atr_stop_multiplier)
        print(f"\n[Test] Forex ATR Stop: {forex_cal.atr_stop_multiplier}x vs Crypto ATR Stop: {crypto_cal.atr_stop_multiplier}x")

    def test_movement_learning_model(self):
        model = get_or_create_model("EURUSD=X")
        res = model.train(self.df, epochs=5)
        self.assertIn(res["status"], ["success", "insufficient_data"])

        pred = model.predict_continuation(self.df)
        self.assertIn("continuation_probability", pred)
        self.assertGreaterEqual(pred["continuation_probability"], 0.0)
        self.assertLessEqual(pred["continuation_probability"], 1.0)
        print(f"[Test] Learned Movement Win Probability: {pred['continuation_probability']*100:.1f}%")

    def test_position_sizing_elder_rule(self):
        # 0.25% risk on $10,000 capital = $25 max loss
        sizer = PositionSizer(capital=10000.0, risk_pct=0.0025)
        entry = 1.0850
        stop = 1.0825  # 25 pips
        res = sizer.calculate_size("EURUSD=X", entry, stop)
        self.assertEqual(res["max_dollar_risk"], 25.0)
        self.assertGreater(res["position_size"], 0)
        print(f"[Test] Calculated Size for 25-pip stop: {res['display_label']}")

    def test_circuit_breaker(self):
        cb = CircuitBreaker(10000.0)
        self.assertFalse(cb.is_halted)
        # Simulate 3 consecutive losses
        cb.record_trade_result(-25.0)
        cb.record_trade_result(-25.0)
        cb.record_trade_result(-25.0)
        self.assertTrue(cb.is_halted)
        self.assertIn("Daily Circuit Breaker Triggered", cb.halt_reason)
        print(f"[Test] Circuit Breaker successfully halted after 3 consecutive losses.")

    def test_gain_protection(self):
        gp = GainProtector(10000.0)
        # Session reaches +$60 (+0.6%, above 0.5% threshold)
        gp.update(60.0, 60.0)
        self.assertTrue(gp.protection_activated)
        # Gives back profit to +$20 (below $25 floor)
        gp.update(20.0, -40.0)
        self.assertTrue(gp.locked_for_session)
        print(f"[Test] Gain protection successfully locked profit.")

if __name__ == "__main__":
    unittest.main()
