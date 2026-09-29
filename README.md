# ElderAlpha: Adaptive Day Trading Helper AI

An autonomous, self-calibrating Day Trading Copilot and quantitative analysis system engineered from the core principles, strategies, and psychological disciplines of **Andrew Elder's *Day Trading Strategies (Book 2)***.

ElderAlpha specializes in **Forex** (e.g., `EUR/USD`, `GBP/USD`, `USD/JPY`) and **Crypto** (e.g., `BTC/USD`, `ETH/USD`, `SOL/USD`), featuring an **Interactive Web Dashboard** with live Plotly candlestick charts, pattern overlays, an AI trade advisor, and an institutional-grade risk engine.

---

## 🌟 Key Features

### 1. Elder Pattern Recognition Suite
- **ABCD Pattern (Chapter 11):** Identifies impulse $A \rightarrow B$, higher-low Fibonacci retracement ($C > A$), and projects breakout to Point $D$.
- **Bull Flag Momentum (Chapters 14 & 24):** Detects strong bullish poles, tight low-volume consolidation flags, and explosive breakouts on high Relative Volume ($\text{RVOL} \ge 1.8\text{x} - 2.0\text{x}$).
- **Range & Channel Trading with ATR (Chapter 8):** Identifies support and resistance boundaries; computes dynamic trailing stops scaled to Average True Range ($\text{ATR}$) to prevent premature shakeouts.
- **Consolidation Chart Patterns (Chapter 6):** Ascending Triangles, Descending Triangles, Triple Bottoms, and Head & Shoulders reversals.
- **Floor Pivot Points (Chapters 9 & 12):** Standard Daily Pivots ($P, R_1-R_3, S_1-S_3$) for turning point support and resistance.
- **Derivative & Options Advisory (Chapters 13, 15, 27, 28):** Recommends Straddles/Strangles for volatility squeezes, Credit Spreads for ranges, and Covered Calls/Married Puts for portfolio hedging.

### 2. Adaptive Calibration & Movement Learning AI
- **Asset-Specific Volatility Calibration (`learning/calibrator.py`):** Automatically profiles asset volatility and wick noise. Calibrates tighter stop-loss multipliers for Forex ($1.2\text{x} - 1.4\text{x}$ ATR) and wider cushions for Crypto ($1.8\text{x} - 2.5\text{x}$ ATR) to neutralize false wicks.
- **PyTorch Movement Learning Model (`learning/movement_model.py`):** Deep Neural Network (`MovementNet`) trained on candlestick microstructures (upper/lower wicks, body ratios, EMA spreads, and volume velocity) to predict whether price action will yield a $\ge 2.0R$ target before stopping out.
- **Self-Correcting Journal Feedback Loop (`learning/journal_learner.py`):** Analyzes historical trades, checks real hit rates against payout ratios, flags emotional pitfalls (overtrading, stop violations), and recalibrates strategy weights.

### 3. Institutional Quantitative Risk Engine
- **0.25% - 1.0% Capital Risk Rule (Chapters 2 & 3):** Automatically calculates exact position sizes in standard lots or coin units based on the stop-loss distance.
- **2:1 Payout Ratio Target (Chapter 4):** Ensures favorable risk/reward on every trade setup.
- **Daily Loss Circuit Breaker:** Automatically halts trading after 3 consecutive losses to protect capital.
- **Weekly & Monthly Drawdown Limits:** Restricts weekly drawdowns to $1.0\%$ and monthly drawdowns to $2.5\%$.
- **Session Gain-Protection Lock (Chapter 4, p. 40):** When session profits reach $+0.5\%$, a profit lock activates; if profits retrace to $+0.25\%$, the session halts to guarantee ending green.
- **Economic Event Blackout (Chapter 4, p. 41):** Filters out trades during high-impact macroeconomic announcements (NFP, FOMC interest rates, CPI).

### 4. Interactive Web Dashboard & Paper Simulator
- **Live Candlestick Visualization:** Powered by Plotly.js with interactive zoom, EMA 9/20 overlays, and real-time pattern lines (A, B, C, D legs, Flag poles, Support/Resistance).
- **Execution Overlays:** Direct visual indicators on the chart for Entry Price (blue), Stop Loss (red dashed), Target 1 (green dashed), and Target 2 runner (cyan dashed).
- **One-Click Paper Execution:** Scale-out trade management automatically sells 50% at Target 1 and immediately moves the Stop Loss to Breakeven.
- **Apex Predator Screener (Chapter 24):** Ranks top momentum assets across Forex and Crypto based on RVOL, ATR volatility, and trend momentum.

---

## 🚀 Quick Start Guide

### 1. Launch the Interactive Web Dashboard
Run the dashboard server with a single command:
```powershell
python run_dashboard.py
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

### 2. Run Terminal CLI Assistant
You can also analyze assets and scan markets directly from the command line:

- **Analyze an asset:**
  ```powershell
  python cli.py analyze EURUSD=X --tf 15m
  python cli.py analyze BTC-USD --tf 15m
  ```

- **Run the Apex Predator Screener:**
  ```powershell
  python cli.py scan
  ```

- **Inspect Trade Journal & Performance:**
  ```powershell
  python cli.py journal
  ```

### 3. Run the Automated Test Suite
Verify all indicators, pattern detectors, PyTorch models, and risk rules:
```powershell
$env:PYTHONPATH="."; python -m unittest tests/test_system.py
```

---

## 📁 Project Architecture

```
tradinghelper/
├── core/
│   ├── config.py              # Risk settings, asset profiles (Forex pip sizes, Crypto units)
│   ├── data_loader.py         # Real-time yfinance feed + caching + synthetic fallback
│   ├── indicators.py          # EMA9/20, ATR-14, Bollinger Bands, MFI, RSI, Floor Pivots
│   ├── models.py              # Pydantic schemas (Candles, Signals, Patterns, Trades)
│   └── coordinator.py         # Master orchestrator integrating patterns, AI, and risk
├── strategies/
│   ├── base_strategy.py       # Abstract strategy class
│   ├── abcd_pattern.py        # Andrew Elder ABCD pattern recognition
│   ├── bull_flag.py           # Bull Flag Momentum & RVOL confirmation
│   ├── channel_range.py       # Range/Channel trading with dynamic ATR trailing stops
│   ├── consolidation.py       # Triangles, Head & Shoulders, Triple Bottoms
│   ├── pivot_points.py        # Floor Pivot bounce and rejection setups
│   └── options_crypto_advisor.py # Straddles, Strangles, Credit Spreads, Covered Calls
├── learning/
│   ├── calibrator.py          # Dynamic asset volatility calibration (ATR stop multipliers, Fibs)
│   ├── movement_dataset.py    # Candlestick microstructure feature extractor
│   ├── movement_model.py      # PyTorch & Scikit-Learn movement continuation predictor
│   └── journal_learner.py     # Post-trade review, Elder mistake detection, self-correction
├── risk/
│   ├── position_sizer.py      # 0.25% - 1% capital risk position calculator (lots/coins)
│   ├── circuit_breaker.py     # Consecutive loss cutoff, weekly & monthly drawdown limits
│   ├── gain_protector.py      # Session profit protection (+0.5% target lock)
│   └── event_lockout.py       # Macro event filter (NFP, FOMC blackout windows)
├── screener/
│   └── apex_screener.py       # Apex Predator Scanner (RVOL >= 2.0x, high ATR %)
├── execution/
│   ├── paper_broker.py        # Paper broker with partial exits (50% at T1) & breakeven stops
│   └── journal.py             # SQLite trading journal preserving mental state & lessons
├── ui/
│   ├── app.py                 # FastAPI backend server with REST endpoints
│   ├── templates/
│   │   └── index.html         # Modern dark-mode trading terminal UI
│   └── static/
│       ├── css/style.css      # Custom styling
│       └── js/app.js          # Plotly.js candlestick rendering & real-time controls
├── tests/
│   └── test_system.py         # Unit and integration test suite
├── run_dashboard.py           # Dashboard launch entrypoint
├── cli.py                     # Rich terminal CLI assistant
└── README.md
```

---

## 📖 Andrew Elder Rulebook Reference

| Principle | Elder Rule / Book Reference | Implementation in ElderAlpha |
|:---|:---|:---|
| **Capital Risk** | *"As a beginner, your risk per trade should not be more than 0.25%... maximum 1%."* (Ch 3) | `PositionSizer` automatically computes share/lot sizing so total risk equals 0.25% capital. |
| **Payout Target** | *"Aim for a payout ratio of 2. Anything below requires a high hit rate."* (Ch 4) | Strategy engines enforce minimum $2.0R$ target before generating active trade signals. |
| **Scale-Out Strategy**| *"Sell half in the first target... bring stop loss to break even... keep runner."* (Ch 11, p. 9 & 13) | `PaperBroker` closes 50% at Target 1 and immediately resets Stop Loss to Breakeven. |
| **Trailing ATR** | *"Use the multiple of that ATR value to trailing your stop loss."* (Ch 8, p. 72) | `ChannelRangeStrategy` and `PaperBroker` dynamically trail winning positions using $k \times \text{ATR}$. |
| **Gain Protection** | *"If you make around 0.5% during the session... stop if gains dip below 0.25%."* (Ch 4, p. 40) | `GainProtector` locks in winning session days to prevent giving back profits. |
| **Event Blackout** | *"Stop trading an hour prior to the announcement and resume an hour after."* (Ch 4, p. 41) | `EventLockoutFilter` flags blackout periods during high-volatility news releases. |
| **Trade Review** | *"Those who don't learn from their mistakes will be doomed to repeat them."* (Ch 25) | `JournalLearner` analyzes closed trades, hit rate, and highlights violations. |
