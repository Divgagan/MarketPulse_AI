"""
ml/feature_engineering.py — MarketPulse AI
============================================
Takes raw OHLCV data and creates all ML features for LightGBM.

Creates 40+ features across 5 categories:
  1. Price features       : returns, log returns
  2. Technical indicators : RSI, MACD, Bollinger Bands, EMAs, ATR, OBV, etc.
  3. Volume features      : relative volume, volume spikes
  4. Price pattern        : 52-week high/low position, EMA distance
  5. NSE calendar         : F&O expiry proximity, RBI MPC week, result season

Note: Uses `ta` library instead of pandas-ta (pandas-ta is unavailable for
Python 3.11 — developer approved this substitute). All feature outputs are
identical in name and meaning.

Main functions:
  - engineer_features(df, ticker)  : Add all features to one stock's OHLCV df
  - engineer_all_stocks()          : Process and save all 50 stocks' CSVs
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# ta library: technical analysis for Python 3.11
# All the same indicators as pandas-ta, class-based API.
try:
    import ta
    import ta.momentum
    import ta.trend
    import ta.volatility
    import ta.volume
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("ta library not installed. Run: pip install ta")

from config.settings import PROCESSED_DIR
from config.tickers import ACTIVE_STOCKS
from config.sector_knowledge import NSE_CALENDAR_EVENTS

# ── Logger ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("feature_engineering")

# ── RBI MPC Hardcoded Dates (2024-2025) ────────────────────────────────────────
RBI_MPC_DATES = pd.to_datetime(
    NSE_CALENDAR_EVENTS["rbi_mpc"]["scheduled_dates_2024_2025"]
)


# ── Utility: Find Next F&O Expiry Date ────────────────────────────────────────

def _get_last_thursday(year: int, month: int) -> date:
    """Returns the last Thursday of the given month (NSE F&O expiry rule)."""
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    days_to_thursday = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=days_to_thursday)


def _days_to_next_fo_expiry(current_date: date) -> int:
    """Calculate days from current_date to the next F&O expiry."""
    this_month_expiry = _get_last_thursday(current_date.year, current_date.month)
    if current_date <= this_month_expiry:
        return (this_month_expiry - current_date).days
    else:
        if current_date.month == 12:
            next_expiry = _get_last_thursday(current_date.year + 1, 1)
        else:
            next_expiry = _get_last_thursday(current_date.year, current_date.month + 1)
        return (next_expiry - current_date).days


# ── Main Feature Engineering Function ─────────────────────────────────────────

def engineer_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Add all ML features to a raw OHLCV DataFrame.

    Args:
        df     : Raw OHLCV DataFrame with Date as index
        ticker : Ticker symbol used for logging

    Returns:
        pd.DataFrame with 40+ engineered feature columns.
        NaN rows dropped (first ~200 due to EMA-200 lookback).
    """
    if df.empty:
        logger.warning(f"  {ticker}: Empty DataFrame -- skipping")
        return pd.DataFrame()

    df = df.copy()
    df.index = pd.to_datetime(df.index)

    # Standardize column names
    df.columns = [c.strip() for c in df.columns]
    col_map = {c: c.capitalize() for c in df.columns
               if c.lower() in ["open", "high", "low", "close", "volume"]}
    df.rename(columns=col_map, inplace=True)

    logger.info(f"  {ticker}: Engineering features on {len(df)} rows...")

    # ── PRICE FEATURES ──────────────────────────────────────────────────────────

    # daily_return: percentage change from previous close to today's close
    # This is the most basic momentum signal
    df["daily_return"] = df["Close"].pct_change(1) * 100

    # weekly_return: 5-trading-day return (1 trading week)
    df["weekly_return"] = df["Close"].pct_change(5) * 100

    # monthly_return: 21-trading-day return (1 trading month)
    df["monthly_return"] = df["Close"].pct_change(21) * 100

    # log_return: log of (close / prev_close)
    # More statistically well-behaved than % return for ML (less skew)
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))

    # ── TECHNICAL INDICATORS (ta library) ───────────────────────────────────────

    if TA_AVAILABLE:

        # RSI — Relative Strength Index
        df["rsi_14"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
        df["rsi_7"]  = ta.momentum.RSIIndicator(df["Close"], window=7).rsi()

        # MACD — Moving Average Convergence Divergence
        macd_obj = ta.trend.MACD(df["Close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd"]           = macd_obj.macd()
        df["macd_signal"]    = macd_obj.macd_signal()
        df["macd_histogram"] = macd_obj.macd_diff()

        # Bollinger Bands — 20-period, 2 std deviations
        bb_obj = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
        df["bb_lower"]  = bb_obj.bollinger_lband()
        df["bb_middle"] = bb_obj.bollinger_mavg()
        df["bb_upper"]  = bb_obj.bollinger_hband()
        band_range = df["bb_upper"] - df["bb_lower"]
        df["bb_width"]    = band_range / df["bb_middle"]
        df["bb_position"] = np.where(
            band_range > 0,
            (df["Close"] - df["bb_lower"]) / band_range,
            0.5
        )

        # Exponential Moving Averages
        df["ema_9"]   = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
        df["ema_21"]  = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
        df["ema_50"]  = ta.trend.EMAIndicator(df["Close"], window=50).ema_indicator()
        df["ema_200"] = ta.trend.EMAIndicator(df["Close"], window=200).ema_indicator()

        # EMA Crossovers
        df["ema_cross_9_21"]  = (df["ema_9"]  > df["ema_21"]).astype(int)
        df["ema_cross_21_50"] = (df["ema_21"] > df["ema_50"]).astype(int)

        # ATR — Average True Range
        df["atr_14"] = ta.volatility.AverageTrueRange(
            df["High"], df["Low"], df["Close"], window=14
        ).average_true_range()

        # OBV — On Balance Volume
        df["obv"] = ta.volume.OnBalanceVolumeIndicator(
            df["Close"], df["Volume"]
        ).on_balance_volume()
        df["obv_ema"] = ta.trend.EMAIndicator(df["obv"], window=20).ema_indicator()

        # ADX — Average Directional Index
        df["adx_14"] = ta.trend.ADXIndicator(
            df["High"], df["Low"], df["Close"], window=14
        ).adx()

        # CCI — Commodity Channel Index
        df["cci_20"] = ta.trend.CCIIndicator(
            df["High"], df["Low"], df["Close"], window=20
        ).cci()

        # Stochastic Oscillator
        stoch_obj = ta.momentum.StochasticOscillator(
            df["High"], df["Low"], df["Close"], window=14, smooth_window=3
        )
        df["stoch_k"] = stoch_obj.stoch()
        df["stoch_d"] = stoch_obj.stoch_signal()

        # Williams %R
        df["williams_r"] = ta.momentum.WilliamsRIndicator(
            df["High"], df["Low"], df["Close"], lbp=14
        ).williams_r()

        # MFI — Money Flow Index
        df["mfi_14"] = ta.volume.MFIIndicator(
            df["High"], df["Low"], df["Close"], df["Volume"], window=14
        ).money_flow_index()

        # VWAP approximation (rolling 20-day)
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        df["vwap"] = (
            (typical_price * df["Volume"]).rolling(20).sum()
            / df["Volume"].rolling(20).sum()
        )

    else:
        # If ta library not available, fill with NaN (will be handled in predictor)
        ta_columns = [
            "rsi_14", "rsi_7", "macd", "macd_signal", "macd_histogram",
            "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_position",
            "ema_9", "ema_21", "ema_50", "ema_200",
            "ema_cross_9_21", "ema_cross_21_50",
            "atr_14", "obv", "obv_ema", "adx_14", "cci_20",
            "stoch_k", "stoch_d", "williams_r", "mfi_14", "vwap",
        ]
        for col in ta_columns:
            df[col] = np.nan
        logger.warning(f"  {ticker}: pandas_ta missing — TA features set to NaN")

    # ── VOLUME FEATURES ─────────────────────────────────────────────────────────

    # 20-day average volume (baseline)
    df["volume_sma_20"] = df["Volume"].rolling(window=20).mean()

    # Relative volume: today's volume vs average
    # volume_ratio > 1.5 means 50% more volume than usual → significant move
    df["volume_ratio"] = df["Volume"] / df["volume_sma_20"]
    df["volume_ratio"] = df["volume_ratio"].replace([np.inf, -np.inf], np.nan)

    # Volume spike flag: > 2x average volume = high-conviction move
    df["volume_spike"] = (df["volume_ratio"] > 2.0).astype(int)

    # ── PRICE PATTERN FEATURES ──────────────────────────────────────────────────

    # 52-week high and low (252 trading days ≈ 1 year)
    rolling_52w_high = df["Close"].rolling(window=252, min_periods=126).max()
    rolling_52w_low = df["Close"].rolling(window=252, min_periods=126).min()

    # How far is current price from 52-week extremes?
    # price_vs_52w_high = 1.0 means AT the 52-week high
    # price_vs_52w_high = 0.8 means 20% below the 52-week high
    df["price_vs_52w_high"] = df["Close"] / rolling_52w_high
    df["price_vs_52w_low"] = df["Close"] / rolling_52w_low

    # Distance from 200-day EMA: positive = above (bullish), negative = below (bearish)
    # This is one of the most important long-term trend indicators
    if "ema_200" in df.columns:
        df["distance_from_ema200"] = (df["Close"] - df["ema_200"]) / df["ema_200"]
    else:
        df["distance_from_ema200"] = np.nan

    # ── NSE CALENDAR FEATURES ───────────────────────────────────────────────────
    # These capture market-structure effects specific to Indian markets
    # that the technical indicators alone would miss.

    # Calculate days_to_fo_expiry for each row's date
    # F&O expiry = last Thursday of each month (NSE rule)
    df["days_to_fo_expiry"] = df.index.map(
        lambda dt: _days_to_next_fo_expiry(dt.date())
    )

    # is_fo_expiry_week: within 5 trading days of F&O expiry
    # Signals increase intraday volatility during this window
    df["is_fo_expiry_week"] = (df["days_to_fo_expiry"] <= 5).astype(int)

    # is_rbi_week: within 3 days of a known RBI MPC announcement date
    # Banking stocks especially show abnormal volatility around RBI dates
    def _is_near_rbi(dt):
        """Check if date is within 3 days of any RBI MPC date."""
        for rbi_date in RBI_MPC_DATES:
            if abs((dt - rbi_date).days) <= 3:
                return 1
        return 0

    df["is_rbi_week"] = df.index.map(_is_near_rbi)

    # is_budget_month: February = Union Budget month
    # Market uncertainty is high; signals are less reliable
    df["is_budget_month"] = (df.index.month == 2).astype(int)

    # is_result_season: April, July, October, January = quarterly results season
    # Individual stocks show high volatility around result dates
    df["is_result_season"] = df.index.month.isin([1, 4, 7, 10]).astype(int)

    # ── TARGET VARIABLE ─────────────────────────────────────────────────────────
    # What we're predicting: will tomorrow's close be HIGHER than today's?
    # 1 = price goes up, 0 = price stays same or goes down
    #
    # Using shift(-1) means we're looking ONE DAY into the future:
    # target[today] = 1 if close[tomorrow] > close[today]
    #
    # CRITICAL: This shift is why we MUST use TimeSeriesSplit — if we randomly
    # split, future data leaks into training. (Rules 4 & 6 in LLM_INSTRUCTIONS)
    df["target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    # ── CLEANUP ─────────────────────────────────────────────────────────────────
    # Drop rows with NaN values.
    # The first ~200 rows will have NaN due to EMA-200's 200-period lookback.
    # The last row will have NaN in 'target' (no next-day data yet).
    rows_before = len(df)
    df.dropna(inplace=True)
    rows_after = len(df)

    logger.info(
        f"  {ticker}: Features done. "
        f"Dropped {rows_before - rows_after} NaN rows. "
        f"Final: {rows_after} rows, {len(df.columns)} columns."
    )

    return df


# ── Batch Processing: Engineer All 50 Stocks ──────────────────────────────────

def engineer_all_stocks() -> None:
    """
    Read each stock's raw CSV from PROCESSED_DIR, apply feature engineering,
    and save the result as {ticker}_features.csv in the same directory.

    This is called:
    1. Once during initial setup (after fetch_all_nifty50)
    2. Daily by the EOD pipeline (after update_all_stocks_daily)
    """
    logger.info("=" * 60)
    logger.info("Starting feature engineering for all NIFTY 50 stocks")
    logger.info(f"  Reading from/saving to: {PROCESSED_DIR}")
    logger.info("=" * 60)

    success = 0
    failed = 0
    total = len(ACTIVE_STOCKS)

    for idx, ticker in enumerate(ACTIVE_STOCKS.keys(), start=1):
        logger.info(f"[{idx:02d}/{total}] Processing {ticker}...")

        # Read raw CSV
        csv_path = PROCESSED_DIR / f"{ticker}.csv"
        if not csv_path.exists():
            logger.warning(f"  {ticker}: Raw CSV not found at {csv_path}. Skipping.")
            failed += 1
            continue

        try:
            df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
        except Exception as e:
            logger.error(f"  {ticker}: Failed to read CSV — {e}")
            failed += 1
            continue

        # Apply feature engineering
        features_df = engineer_features(df, ticker)

        if features_df.empty:
            logger.warning(f"  {ticker}: Feature engineering returned empty DataFrame")
            failed += 1
            continue

        # Save features as parquet (faster to load in predictor) and CSV backup
        features_path = PROCESSED_DIR / f"{ticker}_features.parquet"
        features_csv  = PROCESSED_DIR / f"{ticker}_features.csv"
        try:
            features_df.to_parquet(features_path)
            features_df.to_csv(features_csv)  # CSV backup for compatibility
            logger.info(f"  Saved {features_path.name} ({len(features_df)} rows, {len(features_df.columns)} cols)")
            success += 1
        except Exception as e:
            logger.error(f"  {ticker}: Failed to save features — {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Feature engineering complete: {success} success, {failed} failed")
    logger.info("=" * 60)


# ── Quick Test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick sanity check — test on one stock if data exists
    # Run: conda activate agentic_env && python ml/feature_engineering.py

    logger.info("MarketPulse AI -- Feature Engineering Test")

    # Test with one stock (RELIANCE.NS) if CSV exists
    test_ticker = "RELIANCE.NS"
    test_csv = PROCESSED_DIR / f"{test_ticker}.csv"

    if test_csv.exists():
        df = pd.read_csv(test_csv, index_col="Date", parse_dates=True)
        logger.info(f"Loaded {test_ticker}: {len(df)} raw rows")

        features_df = engineer_features(df, test_ticker)

        if not features_df.empty:
            logger.info(f"Features shape: {features_df.shape}")
            logger.info(f"Feature columns ({len(features_df.columns)}):")
            for col in sorted(features_df.columns):
                non_null = features_df[col].notna().sum()
                logger.info(f"  {col:30s}: {non_null} non-null values")
        else:
            logger.error("Feature engineering returned empty DataFrame!")
    else:
        logger.warning(f"No data found for {test_ticker}.")
        logger.warning("Run ml/data_collector.py first to download stock data.")
        logger.info("Module imports OK — feature engineering ready to use.")
