import os
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
import joblib
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from learning.movement_dataset import extract_features, create_training_dataset, FEATURE_NAMES

logger = logging.getLogger("tradinghelper.movement_model")

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

class MovementPredictor:
    """
    Robust Dual-Engine Movement Learner:
    Combines Multi-Layer Perceptron Neural Network (MLP) and Gradient Boosting.
    Learns ticker-specific nuances (Forex tight wicks vs Crypto volatile swings).
    Trains exclusively on Andrew Elder Quality Trades (Volume RVOL >= 1.15, ATR active range,
    clear trend & rejection wicks) to filter out market chop.
    Persists trained weights to disk via joblib.
    """
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.input_dim = len(FEATURE_NAMES)
        self.scaler: Optional[StandardScaler] = None
        self.mlp_net: Optional[MLPClassifier] = None
        self.gb_model: Optional[GradientBoostingClassifier] = None
        self.is_trained = False
        self.training_samples = 0
        self.mean_win_rate = 0.42
        self.quality_trades_only = True
        self.last_trained_at = ""
        self.quantiles = [0.08, 0.12, 0.16, 0.22, 0.30]

        # Auto-load existing saved weights from disk
        self._load_saved_model()

    def _get_model_path(self) -> str:
        os.makedirs(MODELS_DIR, exist_ok=True)
        safe_sym = self.symbol.replace("/", "_").replace("=", "_").replace("^", "_").replace(":", "_")
        return os.path.join(MODELS_DIR, f"{safe_sym}_movement.pkl")

    def _load_saved_model(self) -> bool:
        path = self._get_model_path()
        if os.path.exists(path):
            try:
                data = joblib.load(path)
                self.scaler = data.get("scaler")
                self.mlp_net = data.get("mlp_net")
                self.gb_model = data.get("gb_model")
                self.is_trained = data.get("is_trained", False)
                self.training_samples = data.get("training_samples", 0)
                self.mean_win_rate = data.get("mean_win_rate", 0.42)
                self.quality_trades_only = data.get("quality_trades_only", True)
                self.last_trained_at = data.get("last_trained_at", "")
                self.quantiles = data.get("quantiles", [0.08, 0.12, 0.16, 0.22, 0.30])
                logger.info(f"Loaded trained movement model for {self.symbol} from {path} ({self.training_samples} samples)")
                return True
            except Exception as e:
                logger.warning(f"Could not load saved model for {self.symbol}: {e}")
        return False

    def save_model(self, filepath: Optional[str] = None) -> str:
        path = filepath or self._get_model_path()
        data = {
            "symbol": self.symbol,
            "scaler": self.scaler,
            "mlp_net": self.mlp_net,
            "gb_model": self.gb_model,
            "is_trained": self.is_trained,
            "training_samples": self.training_samples,
            "mean_win_rate": self.mean_win_rate,
            "quality_trades_only": self.quality_trades_only,
            "last_trained_at": self.last_trained_at,
            "quantiles": self.quantiles
        }
        joblib.dump(data, path, compress=3)
        logger.info(f"Saved movement model for {self.symbol} to {path}")
        return path

    def train(self, df: pd.DataFrame, epochs: int = 40, only_quality_trades: bool = True) -> Dict[str, Any]:
        """
        Extracts features and trains the neural network and gradient booster on market data.
        Filters for Andrew Elder Quality Trades only.
        """
        try:
            X, y = create_training_dataset(df, forward_bars=12, target_rr=1.0, only_quality_trades=only_quality_trades)
            if len(X) < 25:
                # If quality filter yielded too few samples, fallback to unfiltered
                X, y = create_training_dataset(df, forward_bars=8, target_rr=1.5, only_quality_trades=False)
                only_quality_trades = False

            if len(X) < 15:
                return {"status": "insufficient_data", "samples": len(X)}

            classes = np.unique(y)
            if len(classes) < 2:
                y[0] = 1.0 - y[0]

            # 1. Feature Standardization for Neural Network
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            self.scaler = scaler

            # 2. Train MLP Neural Network (64 -> 32 -> 1)
            mlp = MLPClassifier(
                hidden_layer_sizes=(64, 32),
                activation='relu',
                solver='adam',
                max_iter=max(epochs, 120),
                random_state=42,
                early_stopping=True if len(X) >= 100 else False,
                n_iter_no_change=10
            )
            mlp.fit(X_scaled, y)
            self.mlp_net = mlp

            # 3. Train Gradient Boosting Classifier
            gb = GradientBoostingClassifier(
                n_estimators=45,
                max_depth=3,
                learning_rate=0.08,
                random_state=42
            )
            gb.fit(X, y)
            self.gb_model = gb

            # 4. Compute empirical distribution for calibrated probabilities
            p_mlp = mlp.predict_proba(X_scaled)[:, 1]
            p_gb = gb.predict_proba(X)[:, 1]
            p_comb = 0.5 * p_mlp + 0.5 * p_gb

            self.quantiles = [
                float(np.percentile(p_comb, 10)),
                float(np.percentile(p_comb, 25)),
                float(np.percentile(p_comb, 50)),
                float(np.percentile(p_comb, 75)),
                float(np.percentile(p_comb, 90))
            ]

            self.is_trained = True
            self.training_samples = len(X)
            self.mean_win_rate = float(np.mean(y))
            self.quality_trades_only = only_quality_trades
            self.last_trained_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Auto persist to disk
            model_path = self.save_model()

            # Win rate for high-confidence predictions
            top25_mask = p_comb >= self.quantiles[3]
            high_conf_win_rate = float(y[top25_mask].mean()) if top25_mask.sum() > 0 else self.mean_win_rate

            return {
                "status": "success",
                "symbol": self.symbol,
                "samples": len(X),
                "quality_trades_only": only_quality_trades,
                "base_win_rate": round(self.mean_win_rate * 100, 1),
                "high_confidence_win_rate": round(high_conf_win_rate * 100, 1),
                "models": "MLP_NeuralNet (64x32) + GradientBoosting (45 trees)",
                "saved_to": model_path,
                "trained_at": self.last_trained_at
            }
        except Exception as e:
            logger.error(f"Training failed gracefully: {e}")
            return {"status": "error", "message": str(e)}

    def predict_continuation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates probability of successful continuation on the most recent bar.
        Calibrated against the empirical quality-trade distribution.
        """
        if len(df) < 5:
            return {"probability": 0.50, "signal_quality": "NEUTRAL", "confidence": "LOW"}

        try:
            feats_raw = extract_features(df).iloc[-1:].values.astype(np.float32)

            probs = []
            if self.mlp_net is not None and self.scaler is not None:
                feats_scaled = self.scaler.transform(feats_raw)
                probs.append(float(self.mlp_net.predict_proba(feats_scaled)[0][1]))
            elif self.mlp_net is not None:
                probs.append(float(self.mlp_net.predict_proba(feats_raw)[0][1]))

            if self.gb_model is not None:
                probs.append(float(self.gb_model.predict_proba(feats_raw)[0][1]))

            if probs:
                raw_prob = float(np.mean(probs))
            else:
                raw_prob = 0.50

            # Calibrate against empirical quantiles [p10, p25, p50, p75, p90]
            # Maps: p50 (median) -> 0.50, p75 -> 0.65, p90 -> 0.78, p10 -> 0.32
            q10, q25, q50, q75, q90 = self.quantiles
            if raw_prob >= q90:
                calibrated_p = 0.75 + min(0.20, (raw_prob - q90) / max(0.01, 1.0 - q90) * 0.15)
            elif raw_prob >= q75:
                calibrated_p = 0.62 + ((raw_prob - q75) / max(0.01, q90 - q75)) * 0.13
            elif raw_prob >= q50:
                calibrated_p = 0.50 + ((raw_prob - q50) / max(0.01, q75 - q50)) * 0.12
            elif raw_prob >= q25:
                calibrated_p = 0.40 + ((raw_prob - q25) / max(0.01, q50 - q25)) * 0.10
            else:
                calibrated_p = max(0.20, 0.40 - ((q25 - raw_prob) / max(0.01, q25)) * 0.20)

            calibrated_p = round(float(np.clip(calibrated_p, 0.15, 0.95)), 3)

            # Determine directional quality based on trend & candle
            is_bullish = bool(df['is_bullish_bar'].iloc[-1]) if 'is_bullish_bar' in df else True
            ema9 = float(df['ema9'].iloc[-1]) if 'ema9' in df else 0.0
            ema20 = float(df['ema20'].iloc[-1]) if 'ema20' in df else 0.0
            trend_bull = ema9 >= ema20

            if calibrated_p >= 0.65:
                rec = "HIGH_CONFIDENCE_BULLISH" if trend_bull else "HIGH_CONFIDENCE_BEARISH"
            elif calibrated_p >= 0.55:
                rec = "MODERATE_BULLISH" if trend_bull else "MODERATE_BEARISH"
            elif calibrated_p <= 0.38:
                rec = "HIGH_PROBABILITY_FAILURE"
            else:
                rec = "CHOPPY_UNCERTAIN"

            return {
                "symbol": self.symbol,
                "continuation_probability": calibrated_p,
                "signal_quality": rec,
                "is_trained": self.is_trained,
                "training_samples": self.training_samples,
                "historical_win_rate": round(self.mean_win_rate * 100, 1),
                "quality_trades_only": self.quality_trades_only,
                "last_trained_at": self.last_trained_at
            }
        except Exception as e:
            logger.warning(f"Predict error: {e}")
            return {
                "symbol": self.symbol,
                "continuation_probability": 0.50,
                "signal_quality": "NEUTRAL",
                "is_trained": self.is_trained,
                "training_samples": self.training_samples
            }

# Global registry of movement models per symbol
_MODELS: Dict[str, MovementPredictor] = {}

def get_or_create_model(symbol: str) -> MovementPredictor:
    if symbol not in _MODELS:
        _MODELS[symbol] = MovementPredictor(symbol)
    return _MODELS[symbol]
