"""
Autonomous Background Continuous Learning & Training Engine
ElderAlpha Trading Helper AI - Codifying Andrew Elder: Day Trading Strategies (Book 2)

Autonomously trains and adapts the AI Movement Learner and Strategy Auto-Calibrator:
1. Detects untrained or stale assets and trains them in the background.
2. Periodically retrains on updated market regimes (default every 6 hours).
3. Extracts Elder Quality Trades (RVOL >= 1.15, ATR active volatility, trend alignment, decisive wicks).
4. Persists updated neural network and gradient boosting weights to disk.
5. Operates in a non-blocking daemon thread with zero disruption to live market feeds.
"""

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import yfinance as yf

from core.config import config, DEFAULT_ASSETS
from core.indicators import compute_all_indicators
from learning.calibrator import calibrator
from learning.movement_model import get_or_create_model
from learning.movement_dataset import create_training_dataset

logger = logging.getLogger("tradinghelper.autotrainer")

class AutoTrainerEngine:
    """
    Autonomous Continuous Auto-Training Service.
    Monitors assets, auto-trains untrained models, and periodically refreshes
    calibrated parameters and machine learning weights on fresh market data.
    """
    def __init__(
        self,
        retrain_interval_hours: float = 6.0,
        enabled: bool = True,
        lookback_period: str = "60d",
        interval: str = "15m"
    ):
        self.retrain_interval_hours = retrain_interval_hours
        self.enabled = enabled
        self.lookback_period = lookback_period
        self.interval = interval
        self.is_running = False
        self.is_training_now = False
        self.current_symbol_training: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.last_trained_summary: Dict[str, Dict[str, Any]] = {}
        self.training_history: List[Dict[str, Any]] = []

    def start(self, poll_interval_sec: float = 60.0):
        """Starts the background autonomous training supervisor thread."""
        with self._lock:
            if self.is_running:
                return
            self.is_running = True
            self._thread = threading.Thread(
                target=self._supervision_loop,
                args=(poll_interval_sec,),
                daemon=True,
                name="AutoTrainerDaemon"
            )
            self._thread.start()
            logger.info(f"Auto-Trainer started (Interval: {self.retrain_interval_hours}h, Poll: {poll_interval_sec}s)")

    def stop(self):
        """Stops the autonomous training loop gracefully."""
        with self._lock:
            self.is_running = False
        logger.info("Auto-Trainer stopped.")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        logger.info(f"Auto-Training enabled set to: {self.enabled}")

    def _supervision_loop(self, poll_sec: float):
        """Periodic background supervisor that checks asset staleness and triggers training."""
        # Initial wait to allow application and live feed to initialize smoothly
        time.sleep(5.0)

        while self.is_running:
            try:
                if self.enabled and not self.is_training_now:
                    self._check_and_train_stale_assets()
            except Exception as e:
                logger.error(f"Error in Auto-Trainer loop: {e}")

            time.sleep(poll_sec)

    def _check_and_train_stale_assets(self):
        """Iterates through watched assets and trains any untrained or stale models."""
        symbols = list(DEFAULT_ASSETS.keys())

        for symbol in symbols:
            if not self.is_running or not self.enabled:
                break

            if self.should_train_symbol(symbol):
                logger.info(f"Auto-Trainer: Triggering autonomous training for {symbol}...")
                self.train_symbol(symbol)
                # Brief breather between asset training to avoid API throttling
                time.sleep(4.0)

    def should_train_symbol(self, symbol: str) -> bool:
        """Determines if an asset requires training based on training state and age."""
        model = get_or_create_model(symbol)

        # 1. Never trained
        if not model.is_trained or model.training_samples == 0:
            return True

        # 2. Check age against retrain_interval_hours
        last_str = model.last_trained_at
        if not last_str:
            return True

        try:
            last_dt = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
            age_hours = (datetime.now() - last_dt).total_seconds() / 3600.0
            if age_hours >= self.retrain_interval_hours:
                return True
        except Exception:
            return True

        return False

    def train_symbol(self, symbol: str, force: bool = False) -> Dict[str, Any]:
        """
        Executes an end-to-end autonomous training cycle for a symbol:
        1. Downloads historical candlesticks (up to 60 days).
        2. Computes Elder indicator suite.
        3. Runs Auto-Calibrator (ATR stop multipliers, Fib pullback bounds, RVOL thresholds).
        4. Trains Movement Learner exclusively on Elder Quality Trades.
        5. Persists weights to disk.
        """
        with self._lock:
            if self.is_training_now and not force:
                return {"status": "busy", "message": f"Training already in progress for {self.current_symbol_training}"}
            self.is_training_now = True
            self.current_symbol_training = symbol

        start_time = time.time()
        try:
            period = "60d" if ("BTC" in symbol or "ETH" in symbol or "SOL" in symbol) else "30d"
            ticker = yf.Ticker(symbol)
            raw_df = ticker.history(period=period, interval=self.interval, auto_adjust=True)

            if raw_df is None or len(raw_df) < 30:
                logger.warning(f"Auto-Trainer: Insufficient history returned for {symbol}")
                return {"status": "error", "message": "Insufficient data"}

            raw_df = raw_df.reset_index()
            date_col = 'Datetime' if 'Datetime' in raw_df.columns else 'Date'
            raw_df['timestamp'] = raw_df[date_col].dt.strftime('%Y-%m-%d %H:%M:%S')
            raw_df.columns = [c.lower() for c in raw_df.columns]
            df = raw_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()

            # 1. Technical Indicators
            df = compute_all_indicators(df)

            # 2. Dynamic Auto-Calibration
            calib = calibrator.calibrate_symbol(df, symbol)

            # 3. Movement Model Training on ONLY Quality Trades
            model = get_or_create_model(symbol)
            train_res = model.train(df, epochs=45, only_quality_trades=True)

            duration = round(time.time() - start_time, 2)
            summary = {
                "status": "success",
                "symbol": symbol,
                "samples": train_res.get("samples", 0),
                "quality_trades_only": train_res.get("quality_trades_only", True),
                "base_win_rate": train_res.get("base_win_rate", 0.0),
                "high_confidence_win_rate": train_res.get("high_confidence_win_rate", 0.0),
                "atr_stop_multiplier": calib.atr_stop_multiplier,
                "atr_trail_multiplier": calib.atr_trail_multiplier,
                "rvol_threshold": calib.rvol_threshold,
                "trained_at": model.last_trained_at,
                "duration_seconds": duration
            }

            self.last_trained_summary[symbol] = summary
            self.training_history.insert(0, summary)
            if len(self.training_history) > 30:
                self.training_history = self.training_history[:30]

            logger.info(
                f"Auto-Trainer: Successfully trained {symbol} on {summary['samples']} Quality Trades "
                f"(Base: {summary['base_win_rate']}%, Top-Tier AI Win: {summary['high_confidence_win_rate']}%) in {duration}s"
            )
            return summary

        except Exception as e:
            logger.error(f"Auto-Trainer: Training failed for {symbol}: {e}")
            return {"status": "error", "symbol": symbol, "message": str(e)}

        finally:
            with self._lock:
                self.is_training_now = False
                self.current_symbol_training = None

    def train_all_assets_async(self, force: bool = False):
        """Triggers an asynchronous training round for all assets in the background."""
        def _worker():
            symbols = list(DEFAULT_ASSETS.keys())
            for s in symbols:
                if not self.enabled and not force:
                    break
                self.train_symbol(s, force=force)
                time.sleep(3.0)

        t = threading.Thread(target=_worker, daemon=True, name="AutoTrainAllWorker")
        t.start()

    def get_status(self) -> Dict[str, Any]:
        """Returns the live status of the auto-trainer service for UI HUD display."""
        models_status = {}
        for sym in DEFAULT_ASSETS.keys():
            m = get_or_create_model(sym)
            models_status[sym] = {
                "symbol": sym,
                "is_trained": m.is_trained,
                "samples": m.training_samples,
                "win_rate": round(m.mean_win_rate * 100, 1),
                "last_trained_at": m.last_trained_at or "Never"
            }

        return {
            "enabled": self.enabled,
            "is_running": self.is_running,
            "is_training_now": self.is_training_now,
            "current_symbol": self.current_symbol_training,
            "retrain_interval_hours": self.retrain_interval_hours,
            "models": models_status,
            "last_summary": self.last_trained_summary,
            "recent_runs": self.training_history[:5]
        }

# Global Singleton Instance
auto_trainer = AutoTrainerEngine(retrain_interval_hours=6.0, enabled=True)
