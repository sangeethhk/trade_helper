"""
ElderAlpha Trading Helper AI - Bitcoin 2-Month Training & Auto-Calibration Script
Codifying Andrew Elder: Day Trading Strategies (Book 2)

Fetches 60 days of 15-minute intraday BTC data (~5,700+ bars),
runs the Auto Calibrator, and trains the Movement Learner exclusively
on Quality Trades (RVOL >= 1.15, ATR volatility, trend alignment, decisive wicks).
Persists the trained model and calibration parameters to disk.
"""

import os
import sys
import logging
import yfinance as yf
import pandas as pd
import numpy as np

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.indicators import compute_all_indicators
from learning.calibrator import calibrator
from learning.movement_model import get_or_create_model
from learning.movement_dataset import create_training_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrainBTC")

def run_btc_training(period: str = "60d", interval: str = "15m"):
    print("=" * 75)
    print(f" ELDERALPHA: TRAINING BITCOIN ({period}, {interval}) ON QUALITY TRADES")
    print(" Andrew Elder Day Trading Strategies (Book 2)")
    print("=" * 75)

    # 1. Fetch Historical 2-Month Market Data
    print(f"\n[1/4] Downloading {period} of {interval} data for BTC-USD from Yahoo Finance...")
    ticker = yf.Ticker("BTC-USD")
    raw_df = ticker.history(period=period, interval=interval, auto_adjust=True)

    if raw_df is None or len(raw_df) < 50:
        print("[ERROR] Failed to download sufficient market data for BTC-USD.")
        return False

    raw_df = raw_df.reset_index()
    date_col = 'Datetime' if 'Datetime' in raw_df.columns else 'Date'
    raw_df['timestamp'] = raw_df[date_col].dt.strftime('%Y-%m-%d %H:%M:%S')
    raw_df.columns = [c.lower() for c in raw_df.columns]
    df = raw_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()

    start_date = df['timestamp'].iloc[0]
    end_date = df['timestamp'].iloc[-1]
    print(f" -> Fetched {len(df):,} candlesticks ({start_date} to {end_date})")

    # 2. Compute Full Andrew Elder Technical Indicator Suite
    print("\n[2/4] Computing Technical Indicators (EMA 9/20, ATR-14, Bollinger Bands, MFI, RSI, RVOL, Candlestick Wicks)...")
    df = compute_all_indicators(df)
    print(f" -> Computed {len(df.columns)} indicators across {len(df):,} candles.")

    # 3. Auto Calibrator Execution
    print("\n[3/4] Running Strategy Auto-Calibrator for Bitcoin...")
    calib = calibrator.calibrate_symbol(df, "BTC-USD")
    print(" -> Auto-Calibration Complete:")
    print(f"    - ATR Stop Loss Multiplier:   {calib.atr_stop_multiplier}x")
    print(f"    - ATR Trailing Multiplier:    {calib.atr_trail_multiplier}x")
    print(f"    - Fibonacci Pullback Range:   {calib.abcd_min_pullback_fib} - {calib.abcd_max_pullback_fib}")
    print(f"    - RVOL Momentum Trigger:      {calib.rvol_threshold}x (85th percentile volume)")
    print(f"    - Bull Flag Max Bars:         {calib.bull_flag_max_consolidation_bars} bars")
    print(f"    - Bull Flag Min Pole Size:    {round(calib.bull_flag_min_pole_pct * 100, 2)}%")
    print(f"    - Saved to:                   calibrations.json")

    # 4. Movement Learner: Train on ONLY Quality Trades
    print("\n[4/4] Extracting Quality Trades and Training Movement Learner (Dual Engine: MLP + GB)...")
    X_q, y_q = create_training_dataset(df, forward_bars=12, target_rr=1.0, only_quality_trades=True)
    n_quality = len(X_q)
    n_wins = int(np.sum(y_q))
    base_win_rate = (n_wins / n_quality * 100) if n_quality > 0 else 0

    print(f" -> Filtered {len(df):,} raw bars down to {n_quality:,} ELDER QUALITY TRADES")
    print(f"    (Filters applied: RVOL >= 1.15, Range >= 0.5*ATR, EMA 9/20 trend alignment, rejection wicks/engulfing)")
    print(f" -> Quality Setup Base Win Rate (Target 1 / 1.0R reached before 1.5*ATR stop): {base_win_rate:.1f}% ({n_wins}/{n_quality})")

    model = get_or_create_model("BTC-USD")
    train_res = model.train(df, epochs=50, only_quality_trades=True)

    print("\n" + "=" * 75)
    print(" TRAINING SUMMARY & METRICS")
    print("=" * 75)
    print(f" Status:                  {train_res.get('status')}")
    print(f" Symbol:                  BTC-USD")
    print(f" Training Horizon:        {period} ({len(df):,} 15m candles)")
    print(f" Quality Trade Setups:    {train_res.get('samples'):,} setups")
    print(f" Quality Trades Only:     {train_res.get('quality_trades_only')}")
    print(f" Base Setup Win Rate:     {train_res.get('base_win_rate')}%")
    print(f" High Confidence Win Rate:{train_res.get('high_confidence_win_rate')}% (Top 25% AI signals)")
    print(f" Architecture:            {train_res.get('models')}")
    print(f" Model Saved To:          {train_res.get('saved_to')}")
    print(f" Trained At:              {train_res.get('trained_at')}")

    # 5. Live Test on Most Recent Candle
    recent_pred = model.predict_continuation(df)
    print("\n" + "-" * 75)
    print(" REAL-TIME PREDICTION TEST ON LATEST BITCOIN CANDLE:")
    print(f" Current Timestamp:       {df['timestamp'].iloc[-1]}")
    print(f" Current Close Price:     ${df['close'].iloc[-1]:,.2f}")
    print(f" Continuation Prob:       {round(recent_pred['continuation_probability'] * 100, 1)}%")
    print(f" Signal Quality:          {recent_pred['signal_quality']}")
    print(f" Training Samples:        {recent_pred['training_samples']}")
    print("-" * 75)
    print("\n[SUCCESS] Bitcoin Movement Learner & Auto-Calibrator trained and persisted successfully!\n")
    return True

if __name__ == "__main__":
    run_btc_training()
