from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class PatternType(str, Enum):
    ABCD = "ABCD Pattern"
    BULL_FLAG = "Bull Flag Momentum"
    CHANNEL_RANGE = "Range / Channel"
    BREAKOUT = "Structure Breakout"
    TRIANGLE = "Consolidation Triangle"
    HEAD_AND_SHOULDERS = "Head & Shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "Inverse Head & Shoulders"
    PIVOT_REVERSAL = "Floor Pivot Reversal"
    OPTIONS_HEDGING = "Options / Deriv Strangle & Collar"

class Candle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

class IndicatorSnapshot(BaseModel):
    ema9: Optional[float] = None
    ema20: Optional[float] = None
    atr14: Optional[float] = None
    rsi14: Optional[float] = None
    mfi14: Optional[float] = None
    rvol: Optional[float] = None
    bband_upper: Optional[float] = None
    bband_middle: Optional[float] = None
    bband_lower: Optional[float] = None
    pivot: Optional[float] = None
    r1: Optional[float] = None
    r2: Optional[float] = None
    s1: Optional[float] = None
    s2: Optional[float] = None

class PatternResult(BaseModel):
    pattern_type: PatternType
    symbol: str
    timeframe: str
    direction: Direction
    timestamp: str
    points: Dict[str, Any] = Field(default_factory=dict)
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    confidence_score: float  # 0.0 to 1.0
    rationale: str

class CalibrationParams(BaseModel):
    symbol: str
    atr_stop_multiplier: float = 1.5
    atr_trail_multiplier: float = 2.0
    abcd_min_pullback_fib: float = 0.382
    abcd_max_pullback_fib: float = 0.618
    bull_flag_max_consolidation_bars: int = 8
    bull_flag_min_pole_pct: float = 0.006
    rvol_threshold: float = 1.8
    learned_win_rate_weight: float = 1.0
    last_calibrated_at: Optional[str] = None

class TradeSignal(BaseModel):
    symbol: str
    timestamp: str
    action: ActionType
    pattern: PatternType
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_per_trade_usd: float
    position_size: float
    units_label: str  # "Units" or "Lots" or "Coins"
    confidence: float
    payout_ratio: float
    rationale: str
    calibration_applied: bool = True

class PaperPosition(BaseModel):
    id: str
    symbol: str
    direction: Direction
    entry_price: float
    current_price: float
    stop_loss: float
    target_1: float
    target_2: float
    original_size: float
    remaining_size: float
    entry_time: str
    partial_taken: bool = False
    breakeven_set: bool = False
    unrealized_pnl: float = 0.0
    pattern_name: str

class TradeJournalRecord(BaseModel):
    id: Optional[int] = None
    trade_id: str
    symbol: str
    direction: str
    entry_time: str
    exit_time: Optional[str] = None
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: float
    position_size: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    pattern: str
    reasons_for_entry: str
    reasons_for_exit: Optional[str] = None
    mental_state_entry: str = "Calm & Focused"
    mental_state_exit: Optional[str] = None
    followed_rules: bool = True
    post_trade_lesson: Optional[str] = None
