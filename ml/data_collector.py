"""
ml/data_collector.py — MarketPulse AI
========================================
Fetches and stores historical price data for all NIFTY 50 stocks using yfinance.

Key functions:
  - fetch_historical_data()    : Download OHLCV data for one ticker
  - fetch_all_nifty50()        : Download all 50 stocks (one-time initial run)
  - fetch_single_stock_today() : Get latest OHLCV for one stock
  - update_all_stocks_daily()  : Append new rows to existing CSVs (used by EOD pipeline)
  - get_nifty50_index_data()   : Download NIFTY 50 index (^NSEI) for benchmarking

Rule (LLM_INSTRUCTIONS Rule 10): Always use auto_adjust=True and actions=True
with yfinance to avoid false price drops from splits/dividends.
"""

import time
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from config.settings import TRAINING_START_DATE, PROCESSED_DIR
from config.tickers import ACTIVE_STOCKS

# ── Logger setup ───────────────────────────────────────────────────────────────
# Using Python logging module (not print) as required by Blueprint
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_collector")


# ── 1. Fetch Historical Data for One Ticker ────────────────────────────────────

def fetch_historical_data(
    ticker: str,
    start_date: str,
    end_date: str = None,
) -> pd.DataFrame:
    """
    Download historical OHLCV data for a single ticker using yfinance.

    Args:
        ticker     : yfinance ticker symbol (e.g., "RELIANCE.NS")
        start_date : Start date string in "YYYY-MM-DD" format
        end_date   : End date string (default: today)

    Returns:
        pd.DataFrame with columns [Open, High, Low, Close, Volume, ticker]
        and Date as index. Returns empty DataFrame on failure.

    Rule 10 (LLM_INSTRUCTIONS): auto_adjust=True removes dividend/split distortions.
    Without this, a stock split creates a false 50% price drop — killing ML accuracy.
    """
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")

    try:
        logger.info(f"Fetching {ticker} from {start_date} to {end_date}...")

        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            auto_adjust=True,   # Adjust for splits and dividends — MANDATORY
            actions=True,       # Include dividends and stock splits columns
            progress=False,     # Suppress yfinance's own progress bar
        )

        if df.empty:
            logger.warning(f"  No data returned for {ticker}. May be delisted or incorrect ticker.")
            return pd.DataFrame()

        # Flatten MultiIndex columns if present (yfinance sometimes returns them)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Add ticker column for identification when merging multiple stocks
        df["ticker"] = ticker

        # Ensure index is DatetimeIndex (handles string dates from yfinance)
        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"

        # Handle NSE holiday gaps — forward-fill is NOT appropriate for OHLCV
        # Indian markets have ~15 holidays/year; these create natural gaps in data.
        # We keep gaps as-is — the ML model handles this via feature engineering.
        logger.info(f"  {ticker}: {len(df)} rows fetched ({start_date} to {end_date})")
        return df

    except Exception as e:
        logger.warning(f"  FAILED to fetch {ticker}: {type(e).__name__}: {e}")
        return pd.DataFrame()


# ── 2. Fetch All 50 NIFTY Stocks ──────────────────────────────────────────────

def fetch_all_nifty50(start_date: str = TRAINING_START_DATE) -> dict:
    """
    Download historical data for all 50 NIFTY stocks and save as CSV files.

    - Loops through all tickers in ACTIVE_STOCKS
    - Saves each to PROCESSED_DIR/{ticker}.csv
    - Sleeps 2 seconds between fetches to avoid yfinance rate limiting
    - Returns a dict of {ticker: DataFrame}

    This is the one-time initial data download (called from setup.py).
    Subsequent updates use update_all_stocks_daily() instead.
    """
    logger.info("=" * 60)
    logger.info("Starting full NIFTY 50 data download")
    logger.info(f"  Period: {start_date} to {date.today()}")
    logger.info(f"  Saving to: {PROCESSED_DIR}")
    logger.info("=" * 60)

    results = {}
    total = len(ACTIVE_STOCKS)
    success_count = 0
    fail_count = 0

    for idx, ticker in enumerate(ACTIVE_STOCKS.keys(), start=1):
        logger.info(f"[{idx:02d}/{total}] Fetching {ticker}...")

        df = fetch_historical_data(ticker, start_date)

        if df.empty:
            logger.warning(f"  Skipping {ticker} — empty DataFrame")
            fail_count += 1
            continue

        # Save as CSV to processed directory
        # Filename: "RELIANCE.NS.csv" (dot in ticker name is kept)
        csv_path = PROCESSED_DIR / f"{ticker}.csv"
        df.to_csv(csv_path)
        logger.info(f"  Saved to {csv_path.name} ({len(df)} rows)")

        results[ticker] = df
        success_count += 1

        # Sleep 2 seconds between fetches to respect yfinance rate limits
        # NSE data has 50 requests — sleeping avoids HTTP 429 errors
        if idx < total:
            time.sleep(2)

    logger.info("=" * 60)
    logger.info(f"Download complete: {success_count} success, {fail_count} failed")
    logger.info("=" * 60)

    return results


# ── 3. Fetch Latest Data for a Single Stock ────────────────────────────────────

def fetch_single_stock_today(ticker: str) -> pd.Series:
    """
    Fetch the most recent trading day's OHLCV for a single stock.

    Fetches 5 days of data (to handle weekends and holidays) and
    returns the LAST row as a Series. Used during intraday agent runs
    to get current-day context for feature calculation.

    Args:
        ticker: yfinance ticker symbol (e.g., "TCS.NS")

    Returns:
        pd.Series with [Open, High, Low, Close, Volume] for last trading day.
        Returns empty Series on failure.
    """
    # Use 5-day window to account for weekends and Indian market holidays
    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    df = fetch_historical_data(ticker, start_date, end_date)

    if df.empty:
        logger.warning(f"  fetch_single_stock_today: No data for {ticker}")
        return pd.Series()

    # Return the most recent row (last available trading day)
    latest = df.iloc[-1]
    logger.info(f"  Latest data for {ticker}: {df.index[-1].date()} | Close={latest.get('Close', 'N/A'):.2f}")
    return latest


# ── 4. Daily Incremental Update ────────────────────────────────────────────────

def update_all_stocks_daily() -> None:
    """
    Incrementally update all stock CSVs with new data since the last entry.

    For each stock:
      1. Read existing CSV from PROCESSED_DIR
      2. Find the last date in the CSV
      3. Fetch data from (last_date + 1 day) to today
      4. Append new rows, removing any duplicates
      5. Save back to CSV

    Called by the EOD pipeline (pipeline/eod_pipeline.py) every day at 3:45 PM IST.
    Much faster than re-downloading all 10+ years every day.
    """
    logger.info("Starting daily incremental update for all stocks...")

    today = date.today().strftime("%Y-%m-%d")
    updated = 0
    skipped = 0
    failed = 0

    for ticker in ACTIVE_STOCKS.keys():
        csv_path = PROCESSED_DIR / f"{ticker}.csv"

        # If CSV doesn't exist yet, do a full download for this stock
        if not csv_path.exists():
            logger.warning(f"  {ticker}: CSV not found. Running full download...")
            df = fetch_historical_data(ticker, TRAINING_START_DATE, today)
            if not df.empty:
                df.to_csv(csv_path)
                updated += 1
            else:
                failed += 1
            time.sleep(1)
            continue

        try:
            # Read existing data
            existing_df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)

            if existing_df.empty:
                logger.warning(f"  {ticker}: Existing CSV is empty. Skipping.")
                skipped += 1
                continue

            # Find the last date we have data for
            last_date = existing_df.index.max()
            next_fetch_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")

            # Skip if already up to date (last date is today or very recent)
            if last_date.date() >= date.today():
                logger.info(f"  {ticker}: Already up to date (last: {last_date.date()})")
                skipped += 1
                continue

            # Fetch only new data since last entry
            logger.info(f"  {ticker}: Fetching from {next_fetch_date} to {today}...")
            new_df = fetch_historical_data(ticker, next_fetch_date, today)

            if new_df.empty:
                logger.info(f"  {ticker}: No new data available (market may be closed)")
                skipped += 1
                continue

            # Combine old and new data, remove duplicates (by Date index)
            combined_df = pd.concat([existing_df, new_df])
            combined_df = combined_df[~combined_df.index.duplicated(keep="last")]
            combined_df.sort_index(inplace=True)

            # Save updated CSV
            combined_df.to_csv(csv_path)
            new_rows = len(new_df)
            logger.info(f"  {ticker}: Added {new_rows} new rows. Total: {len(combined_df)}")
            updated += 1

        except Exception as e:
            logger.error(f"  {ticker}: Update failed — {type(e).__name__}: {e}")
            failed += 1
            continue

        # Small sleep to avoid rate limiting
        time.sleep(0.5)

    logger.info(f"Daily update complete: {updated} updated, {skipped} skipped, {failed} failed")


# ── 5. NIFTY 50 Index Data (Benchmark) ────────────────────────────────────────

def get_nifty50_index_data(start_date: str = TRAINING_START_DATE) -> pd.DataFrame:
    """
    Download NIFTY 50 Index (^NSEI) data — used as benchmark in backtesting.

    The index data is saved to PROCESSED_DIR/NIFTY50_INDEX.csv.
    vectorbt uses this as the "buy and hold NIFTY" baseline.

    Args:
        start_date: Start date in "YYYY-MM-DD" format

    Returns:
        pd.DataFrame with NIFTY 50 index OHLCV
    """
    logger.info("Fetching NIFTY 50 Index (^NSEI) data...")

    index_ticker = "^NSEI"
    end_date = date.today().strftime("%Y-%m-%d")

    df = fetch_historical_data(index_ticker, start_date, end_date)

    if df.empty:
        logger.error("Failed to fetch NIFTY 50 index data!")
        return pd.DataFrame()

    # Save to processed directory
    csv_path = PROCESSED_DIR / "NIFTY50_INDEX.csv"
    df.to_csv(csv_path)
    logger.info(f"NIFTY 50 Index saved: {len(df)} rows → {csv_path.name}")

    return df


# ── Utility: Load Existing Data ───────────────────────────────────────────────

def load_stock_data(ticker: str) -> pd.DataFrame:
    """
    Load an existing stock CSV from PROCESSED_DIR.
    Used by ml/feature_engineering.py to avoid re-downloading.

    Returns:
        pd.DataFrame or empty DataFrame if file not found.
    """
    csv_path = PROCESSED_DIR / f"{ticker}.csv"

    if not csv_path.exists():
        logger.warning(f"CSV not found for {ticker} at {csv_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
        logger.info(f"Loaded {ticker}: {len(df)} rows from {csv_path.name}")
        return df
    except Exception as e:
        logger.error(f"Failed to load {ticker}: {e}")
        return pd.DataFrame()


def load_all_stocks() -> dict:
    """
    Load all existing stock CSVs into memory.
    Returns dict of {ticker: DataFrame}.
    """
    results = {}
    for ticker in ACTIVE_STOCKS.keys():
        df = load_stock_data(ticker)
        if not df.empty:
            results[ticker] = df
    logger.info(f"Loaded {len(results)}/{len(ACTIVE_STOCKS)} stock CSVs from disk")
    return results


# ── Main Block: One-Time Initial Download ─────────────────────────────────────
# Run this script directly to perform the initial data download:
#   conda activate agentic_env
#   python ml/data_collector.py
#
# This downloads 10+ years of NIFTY 50 data — takes ~5-10 minutes.
# Subsequent updates are done by update_all_stocks_daily() (fast, incremental).

if __name__ == "__main__":
    logger.info("MarketPulse AI — Initial Data Download")
    logger.info(f"Training start date: {TRAINING_START_DATE}")
    logger.info(f"Output directory   : {PROCESSED_DIR}")
    logger.info("")

    # Download all 50 stocks
    data = fetch_all_nifty50(start_date=TRAINING_START_DATE)

    # Also download the NIFTY 50 index for backtesting benchmark
    index_data = get_nifty50_index_data(start_date=TRAINING_START_DATE)

    logger.info("")
    logger.info("Initial download complete.")
    logger.info(f"  Stocks downloaded : {len(data)}")
    logger.info(f"  Index downloaded  : {'YES' if not index_data.empty else 'FAILED'}")
    logger.info("Next step: Run ml/feature_engineering.py")
