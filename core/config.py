import os
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class AssetProfile(BaseModel):
    symbol: str
    name: str
    asset_type: str  # "forex" or "crypto"
    pip_size: float = 0.0001
    default_lot_or_unit: float = 10000.0  # 0.1 mini lot in Forex or coin unit in Crypto
    price_decimals: int = 4
    typical_spread_pips_or_cents: float = 1.0

DEFAULT_ASSETS: Dict[str, AssetProfile] = {
    "EURUSD=X": AssetProfile(
        symbol="EURUSD=X",
        name="EUR / USD",
        asset_type="forex",
        pip_size=0.0001,
        default_lot_or_unit=10000.0,
        price_decimals=5,
        typical_spread_pips_or_cents=1.2
    ),
    "GBPUSD=X": AssetProfile(
        symbol="GBPUSD=X",
        name="GBP / USD",
        asset_type="forex",
        pip_size=0.0001,
        default_lot_or_unit=10000.0,
        price_decimals=5,
        typical_spread_pips_or_cents=1.5
    ),
    "USDJPY=X": AssetProfile(
        symbol="USDJPY=X",
        name="USD / JPY",
        asset_type="forex",
        pip_size=0.01,
        default_lot_or_unit=10000.0,
        price_decimals=3,
        typical_spread_pips_or_cents=1.2
    ),
    "BTC-USD": AssetProfile(
        symbol="BTC-USD",
        name="Bitcoin / USD",
        asset_type="crypto",
        pip_size=1.0,
        default_lot_or_unit=0.05,
        price_decimals=2,
        typical_spread_pips_or_cents=5.0
    ),
    "ETH-USD": AssetProfile(
        symbol="ETH-USD",
        name="Ethereum / USD",
        asset_type="crypto",
        pip_size=0.1,
        default_lot_or_unit=0.5,
        price_decimals=2,
        typical_spread_pips_or_cents=0.5
    ),
    "SOL-USD": AssetProfile(
        symbol="SOL-USD",
        name="Solana / USD",
        asset_type="crypto",
        pip_size=0.01,
        default_lot_or_unit=5.0,
        price_decimals=2,
        typical_spread_pips_or_cents=0.05
    )
}

class RiskSettings(BaseModel):
    initial_capital: float = 10000.0
    risk_per_trade_pct: float = 0.0025  # 0.25% beginner rule (Andrew Elder Ch 3)
    max_risk_per_trade_pct: float = 0.01   # 1.0% maximum risk
    min_payout_ratio: float = 2.0         # 2:1 Reward to Risk (Andrew Elder Ch 4)
    max_daily_losses_count: int = 3       # Daily loss count cutoff (Elder Ch 3)
    max_weekly_drawdown_pct: float = 0.01 # 1% weekly limit
    max_monthly_drawdown_pct: float = 0.025 # 2.5% monthly limit
    gain_protection_threshold_pct: float = 0.005 # Lock gains when session reaches +0.5%
    gain_protection_retrace_pct: float = 0.0025   # Halt if profits retreat to +0.25%

class AppConfig(BaseModel):
    app_name: str = "ElderAlpha Trading Helper AI"
    version: str = "1.0.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    db_path: str = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "trading_journal.db"))
    risk: RiskSettings = Field(default_factory=RiskSettings)
    assets: Dict[str, AssetProfile] = Field(default_factory=lambda: DEFAULT_ASSETS)
    default_symbol: str = "EURUSD=X"
    default_timeframe: str = "15m"

config = AppConfig()
