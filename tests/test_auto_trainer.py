"""
Unit Tests for Autonomous Continuous Auto-Training Engine
ElderAlpha Trading Helper AI
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from learning.auto_trainer import AutoTrainerEngine, auto_trainer
from learning.movement_model import get_or_create_model

class TestAutoTrainer(unittest.TestCase):
    def setUp(self):
        self.engine = AutoTrainerEngine(retrain_interval_hours=6.0, enabled=True)

    def test_engine_initialization_and_status(self):
        status = self.engine.get_status()
        self.assertTrue(status["enabled"])
        self.assertFalse(status["is_running"])
        self.assertFalse(status["is_training_now"])
        self.assertIn("models", status)
        self.assertIn("BTC-USD", status["models"])
        self.assertIn("EURUSD=X", status["models"])

    def test_toggle_enabled(self):
        self.engine.set_enabled(False)
        self.assertFalse(self.engine.enabled)
        status = self.engine.get_status()
        self.assertFalse(status["enabled"])

        self.engine.set_enabled(True)
        self.assertTrue(self.engine.enabled)

    def test_should_train_symbol_logic(self):
        # Test an untrained dummy symbol
        test_sym = "DUMMY_TEST_SYM"
        should_train = self.engine.should_train_symbol(test_sym)
        self.assertTrue(should_train)

        # Mock model trained recently
        model = get_or_create_model(test_sym)
        model.is_trained = True
        model.training_samples = 150
        model.last_trained_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.assertFalse(self.engine.should_train_symbol(test_sym))

        # Mock model trained 8 hours ago (exceeding 6h interval)
        past_time = datetime.now() - timedelta(hours=8)
        model.last_trained_at = past_time.strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(self.engine.should_train_symbol(test_sym))

if __name__ == '__main__':
    unittest.main()
