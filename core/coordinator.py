from typing import Dict, Any, Optional, List
import pandas as pd
from core.config import config, DEFAULT_ASSETS
from core.data_loader import load_market_data
from core.models import PatternResult, TradeSignal, ActionType, Direction, PatternType
from strategies.abcd_pattern import ABCDPatternStrategy
from strategies.bull_flag import BullFlagStrategy
from strategies.channel_range import ChannelRangeStrategy
from strategies.consolidation import ConsolidationPatternStrategy
from strategies.pivot_points import PivotPointStrategy
from strategies.options_crypto_advisor import OptionsCryptoAdvisor
from learning.calibrator import calibrator
from learning.movement_model import get_or_create_model
from risk.position_sizer import PositionSizer
from risk.event_lockout import EventLockoutFilter
from execution.paper_broker import paper_broker

class TradingCoordinator:
    """
    Central Orchestrator combining:
    1. Market Data Feed
    2. Asset-Specific Volatility Calibration
    3. Elder Pattern Detection Suite (ABCD, Bull Flag, Channels, Pivots)
    4. Movement Learning AI Model (PyTorch continuation probability)
    5. Quantitative Risk & Position Sizing
    6. Circuit Breakers & Session Gain Protection
    """
    def __init__(self):
        self.strategies = [
            BullFlagStrategy(),
            ABCDPatternStrategy(),
            ChannelRangeStrategy(),
            ConsolidationPatternStrategy(),
            PivotPointStrategy()
        ]
        self.event_filter = EventLockoutFilter()

    def analyze_asset(self, symbol: str, timeframe: str = "15m", capital: float = 10000.0, risk_pct: float = 0.0025) -> Dict[str, Any]:
        # 1. Fetch market data & compute indicators
        df = load_market_data(symbol, timeframe)
        if len(df) < 20:
            return {"status": "error", "message": "Insufficient candlestick data"}

        # 2. Strategy Calibration for this Asset (Use saved calibrated profile if available)
        if symbol in calibrator.profiles and calibrator.profiles[symbol].last_calibrated_at:
            calibration = calibrator.profiles[symbol]
        else:
            calibration = calibrator.calibrate_symbol(df, symbol)

        # 3. Movement Learning Prediction (Dual-Engine: MLP + Gradient Boosting)
        model = get_or_create_model(symbol)
        if not model.is_trained and len(df) >= 35:
            model.train(df, epochs=30, only_quality_trades=True)
        movement_prediction = model.predict_continuation(df)

        # 4. Pattern Detection
        detected_pattern: Optional[PatternResult] = None
        for strat in self.strategies:
            res = strat.detect(df, symbol, timeframe, calibration)
            if res is not None:
                detected_pattern = res
                break  # Prioritize best setup

        # 5. Position Sizing & Quantitative Risk
        current_price = float(df['close'].iloc[-1])
        sizer = PositionSizer(capital=capital, risk_pct=risk_pct)
        risk_calc = {}
        active_signal: Optional[TradeSignal] = None

        if detected_pattern:
            risk_calc = sizer.calculate_size(symbol, detected_pattern.entry_price, detected_pattern.stop_loss)
            
            # Combine pattern confidence with AI movement prediction
            ai_p = movement_prediction.get("continuation_probability", 0.5)
            combined_confidence = round((detected_pattern.confidence_score * 0.6) + (ai_p * 0.4), 2)

            action = ActionType.BUY if detected_pattern.direction == Direction.BULLISH else ActionType.SELL
            active_signal = TradeSignal(
                symbol=symbol,
                timestamp=detected_pattern.timestamp,
                action=action,
                pattern=detected_pattern.pattern_type,
                entry_price=detected_pattern.entry_price,
                stop_loss=detected_pattern.stop_loss,
                target_1=detected_pattern.target_1,
                target_2=detected_pattern.target_2,
                risk_per_trade_usd=risk_calc.get("actual_dollar_risk", capital * risk_pct),
                position_size=risk_calc.get("position_size", 1.0),
                units_label=risk_calc.get("display_label", "Units"),
                confidence=combined_confidence,
                payout_ratio=detected_pattern.risk_reward_ratio,
                rationale=detected_pattern.rationale,
                calibration_applied=True
            )

        # 6. Options / Derivative Advisory
        options_guidance = OptionsCryptoAdvisor.generate_options_guidance(df, symbol, current_price)

        # 7. Economic Event Lockout Check (Andrew Elder Ch 4)
        asset_meta = DEFAULT_ASSETS.get(symbol, DEFAULT_ASSETS["EURUSD=X"])
        event_status = self.event_filter.check_event_status(asset_meta.asset_type, symbol=symbol)

        # Enforce Trade Skipping if High-Impact News Blackout is Active
        if event_status.get("in_blackout") and active_signal:
            active_signal.action = ActionType.HOLD
            active_signal.rationale = f"🚨 TRADE SKIPPED: {event_status.get('action_advice')} (Elder Rule: Protect capital from extreme slippage and wide spreads during high-impact news releases)"

        # 8. Check broker updates for active positions
        current_atr = float(df['atr14'].iloc[-1]) if 'atr14' in df else (current_price * 0.01)
        broker_events = paper_broker.on_price_update(symbol, current_price, current_atr)

        return {
            "symbol": symbol,
            "asset_name": asset_meta.name,
            "asset_type": asset_meta.asset_type,
            "timeframe": timeframe,
            "current_price": current_price,
            "detected_pattern": detected_pattern.model_dump() if detected_pattern else None,
            "trade_signal": active_signal.model_dump() if active_signal else None,
            "position_sizing": risk_calc,
            "calibration": calibration.model_dump(),
            "movement_ai": movement_prediction,
            "options_advisory": options_guidance,
            "event_lockout": event_status,
            "news_alert": event_status,
            "broker_events": broker_events,
            "candles": df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'ema9', 'ema20', 'atr14', 'rsi14', 'rvol']].tail(80).to_dict(orient="records")
        }

coordinator = TradingCoordinator()
