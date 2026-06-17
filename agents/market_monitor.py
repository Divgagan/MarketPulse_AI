"""
agents/market_monitor.py — MarketPulse AI
==========================================
Blueprint Part 14 File 2: Agent 5 — Market Monitor.

Fetches live prices for all NIFTY 50 stocks, computes daily % changes,
validates previous predictions, and detects F&O expiry days.

Functions (Blueprint-compliant):
  - fetch_current_prices()           : latest close for all 50 stocks
  - calculate_daily_changes(prices)  : % change from yesterday
  - validate_previous_predictions()  : compare predictions vs actuals in SQLite
  - detect_fo_expiry_today()         : is today last Thursday? (F&O expiry)
  - market_monitor_node()            : LangGraph Agent 5 node

Runs in PARALLEL with ML pipeline. Both feed into Agent 6 (Signal Aggregator).
"""

import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import yfinance as yf

from agents.state import MarketPulseState
from config.tickers import ACTIVE_STOCKS
from config.settings import DATA_DIR

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("market_monitor")

# SQLite predictions DB path
PREDICTIONS_DB = DATA_DIR / "predictions" / "predictions.db"


# ── DB Helpers ─────────────────────────────────────────────────────────────────

def _init_predictions_db() -> None:
    """Create predictions SQLite table if it doesn't exist."""
    PREDICTIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PREDICTIONS_DB))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                date                 TEXT NOT NULL,
                ticker               TEXT NOT NULL,
                predicted_direction  TEXT,
                final_confidence     REAL,
                signal_strength      TEXT,
                alert_text           TEXT,
                actual_direction     TEXT,
                actual_change_pct    REAL,
                was_correct          INTEGER,
                created_at           TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON predictions (date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON predictions (ticker)")
        conn.commit()
    finally:
        conn.close()


# ── Function 1: Fetch Current Prices ──────────────────────────────────────────

def fetch_current_prices(tickers: Optional[List[str]] = None) -> Dict[str, float]:
    """
    Fetch latest closing price for all NIFTY 50 tickers using yfinance.

    Args:
        tickers: Optional specific list. Defaults to all 50 stocks.

    Returns:
        Dict: {ticker: current_close_price}
    """
    if tickers is None:
        tickers = list(ACTIVE_STOCKS.keys())

    prices: Dict[str, float] = {}
    logger.info(f"Fetching current prices for {len(tickers)} stocks...")

    try:
        batch   = " ".join(tickers)
        data    = yf.download(batch, period="2d", progress=False, auto_adjust=True)

        if data.empty:
            logger.warning("yfinance returned empty DataFrame")
            return {}

        close = data["Close"] if "Close" in data.columns else data

        for ticker in tickers:
            try:
                if ticker in close.columns:
                    series = close[ticker].dropna()
                    if not series.empty:
                        prices[ticker] = float(series.iloc[-1])
            except Exception as e:
                logger.debug(f"  {ticker}: price extract failed — {e}")

    except Exception as e:
        logger.error(f"Batch price fetch failed: {e}")

    logger.info(f"Fetched prices for {len(prices)}/{len(tickers)} stocks")
    return prices


# ── Function 2: Calculate Daily Changes ───────────────────────────────────────

def calculate_daily_changes(prices: Dict[str, float]) -> Dict[str, float]:
    """
    Calculate today's % price change for each ticker.
    Fetches 2 days of data → computes (today - yesterday) / yesterday * 100.

    Args:
        prices: Dict of current prices from fetch_current_prices()
                (used to cross-validate and fill missing yfinance data)

    Returns:
        Dict: {ticker: pct_change_today}  e.g. {"RELIANCE.NS": 1.23}
    """
    tickers = list(prices.keys()) if prices else list(ACTIVE_STOCKS.keys())
    changes: Dict[str, float] = {}

    try:
        batch = " ".join(tickers)
        data  = yf.download(batch, period="5d", progress=False, auto_adjust=True)

        if data.empty:
            return {}

        close = data["Close"] if "Close" in data.columns else data

        for ticker in tickers:
            try:
                if ticker in close.columns:
                    series = close[ticker].dropna()
                    if len(series) >= 2:
                        today_close     = float(series.iloc[-1])
                        yesterday_close = float(series.iloc[-2])
                        pct_change      = ((today_close - yesterday_close) / yesterday_close) * 100
                        changes[ticker] = round(pct_change, 4)
            except Exception as e:
                logger.debug(f"  {ticker}: change calc failed — {e}")

    except Exception as e:
        logger.error(f"Daily change batch fetch failed: {e}")

    return changes


# ── Function 3: Validate Previous Predictions ──────────────────────────────────

def validate_previous_predictions(current_prices: Dict[str, float]) -> None:
    """
    Load yesterday's predictions from SQLite, compare with actual price
    movements, update the DB with outcomes, and call store_outcome() to
    update ChromaDB RAG memory for future predictions.

    Args:
        current_prices: Dict of today's prices from fetch_current_prices()
    """
    _init_predictions_db()

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        conn = sqlite3.connect(str(PREDICTIONS_DB))
        try:
            cursor = conn.execute(
                "SELECT id, ticker, predicted_direction, final_confidence, alert_text "
                "FROM predictions WHERE date = ? AND actual_direction IS NULL",
                (yesterday,)
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            logger.info(f"No pending predictions from {yesterday} to validate")
            return

        logger.info(f"Validating {len(rows)} predictions from {yesterday}...")
        correct = 0

        # Fetch yesterday and today prices for change calculation
        changes = calculate_daily_changes(current_prices)

        # Load ChromaDB store_outcome function
        try:
            from agents.impact_scorer import store_outcome
            chroma_available = True
        except ImportError:
            chroma_available = False

        for row_id, ticker, predicted_dir, confidence, alert_text in rows:
            actual_change = changes.get(ticker)
            if actual_change is None:
                continue

            actual_direction = "bullish" if actual_change > 0 else "bearish"
            was_correct      = int(predicted_dir == actual_direction)

            if was_correct:
                correct += 1

            outcome_str = f"{actual_change:+.2f}% ({'✓ correct' if was_correct else '✗ wrong'})"

            # Update SQLite record
            conn = sqlite3.connect(str(PREDICTIONS_DB))
            try:
                conn.execute(
                    "UPDATE predictions SET actual_direction=?, actual_change_pct=?, "
                    "was_correct=? WHERE id=?",
                    (actual_direction, actual_change, was_correct, row_id)
                )
                conn.commit()
            finally:
                conn.close()

            # Update ChromaDB RAG memory
            if chroma_available:
                try:
                    store_outcome(
                        headline            = alert_text[:100] if alert_text else f"{ticker} signal",
                        ticker              = ticker,
                        predicted_direction = predicted_dir,
                        actual_outcome      = outcome_str,
                        confidence          = confidence or 0.5,
                    )
                except Exception as e:
                    logger.debug(f"ChromaDB update failed for {ticker}: {e}")

        accuracy = (correct / len(rows) * 100) if rows else 0
        logger.info(
            f"Validation complete: {correct}/{len(rows)} correct "
            f"({accuracy:.1f}% accuracy) — ChromaDB RAG updated"
        )

    except Exception as e:
        logger.error(f"validate_previous_predictions failed: {e}")


# ── Function 4: Detect F&O Expiry ─────────────────────────────────────────────

def detect_fo_expiry_today() -> bool:
    """
    Check if today is F&O (Futures & Options) expiry day.
    NSE F&O expires on the LAST THURSDAY of every month.
    Signals on expiry day have lower reliability due to high intraday volatility.

    Returns:
        True if today is the last Thursday of the month (F&O expiry day)
        False otherwise
    """
    today = datetime.now().date()

    # Must be a Thursday (weekday 3 = Thursday)
    if today.weekday() != 3:
        return False

    # Check if there is another Thursday remaining this month
    # The last Thursday: adding 7 days goes to next month
    next_thursday = today + timedelta(weeks=1)
    is_last_thursday = (next_thursday.month != today.month)

    if is_last_thursday:
        logger.info(f"Today ({today}) is F&O EXPIRY day — signals have lower reliability")
    return is_last_thursday


# ── LangGraph Node Function ────────────────────────────────────────────────────

def market_monitor_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 5 node: Market Monitor.

    Runs in order:
      1. validate_previous_predictions() — learn from yesterday
      2. fetch_current_prices()          — live snapshot
      3. calculate_daily_changes()       — today's % moves
      4. detect_fo_expiry_today()        — add warning if expiry

    Args:
        state: MarketPulseState

    Returns:
        Updated state with current_prices, price_changes_today, and F&O warning.
    """
    logger.info("=" * 55)
    logger.info("Agent 5: Market Monitor — starting")
    logger.info("=" * 55)

    warnings = list(state.get("warnings", []))
    errors   = list(state.get("errors", []))

    # ── Step 1: Validate yesterday's predictions ──────────────────────────────
    try:
        validate_previous_predictions({})  # will fetch prices internally
    except Exception as e:
        msg = f"Agent5: Validation failed (non-fatal) — {e}"
        logger.warning(msg)
        warnings.append(msg)

    # ── Step 2: Fetch current prices ──────────────────────────────────────────
    try:
        current_prices = fetch_current_prices()
    except Exception as e:
        msg = f"Agent5: Price fetch failed — {e}"
        logger.error(msg)
        errors.append(msg)
        current_prices = {}

    # ── Step 3: Calculate daily % changes ────────────────────────────────────
    try:
        price_changes = calculate_daily_changes(current_prices)
    except Exception as e:
        msg = f"Agent5: Daily change calc failed — {e}"
        logger.warning(msg)
        warnings.append(msg)
        price_changes = {}

    # ── Step 4: F&O expiry check ──────────────────────────────────────────────
    try:
        is_expiry = detect_fo_expiry_today()
        if is_expiry:
            fo_warning = (
                "⚠ F&O EXPIRY TODAY — Futures & Options expire today (last Thursday). "
                "Intraday volatility is elevated. ML signals have lower reliability. "
                "Consider reducing signal confidence thresholds."
            )
            warnings.append(fo_warning)
            logger.warning(fo_warning)
    except Exception as e:
        logger.debug(f"F&O expiry check failed: {e}")

    # ── Log market snapshot ───────────────────────────────────────────────────
    if price_changes:
        top_gainers = sorted(price_changes.items(), key=lambda x: x[1], reverse=True)[:3]
        top_losers  = sorted(price_changes.items(), key=lambda x: x[1])[:3]
        logger.info(f"  Top gainers: {top_gainers}")
        logger.info(f"  Top losers : {top_losers}")

    logger.info(
        f"Agent 5 complete: {len(current_prices)} prices, "
        f"{len(price_changes)} daily changes fetched"
    )

    return {
        **state,
        "current_prices":      current_prices,
        "price_changes_today": price_changes,
        "warnings":            warnings,
        "errors":              errors,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m agents.market_monitor
    logger.info("MarketPulse AI -- Market Monitor Module")

    # Test F&O expiry detection
    is_expiry = detect_fo_expiry_today()
    logger.info(f"F&O expiry today: {is_expiry}")

    # Test with a small subset for speed
    test_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

    logger.info("Fetching live prices...")
    prices  = fetch_current_prices(test_tickers)
    changes = calculate_daily_changes(prices)

    logger.info(f"\nPrices fetched: {len(prices)}")
    for ticker in test_tickers:
        price  = prices.get(ticker)
        change = changes.get(ticker)
        if price and change is not None:
            logger.info(f"  {ticker:20s} ₹{price:>10.2f}  {change:+.2f}%")
        else:
            logger.info(f"  {ticker:20s} — not available")

    logger.info("Market Monitor module OK.")
