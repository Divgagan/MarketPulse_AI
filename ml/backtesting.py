"""
ml/backtesting.py — MarketPulse AI
=====================================
Blueprint Part 9: Professional backtesting using vectorbt.

Tests how well historical predictions would have performed vs 5 baselines.

Key design decisions:
  - Only trade signals with confidence > CONFIDENCE_THRESHOLD (0.55)
  - Long-only strategy (no shorting — for SEBI compliance)
  - Equal weight across all active positions, rebalanced daily
  - Transaction cost: 0.1% per side (realistic for NSE delivery trades)

5 Baselines for honest comparison:
  1. always_up       : Always predict bullish — naive long-only benchmark
  2. momentum        : Buy if yesterday rose, sell if yesterday fell
  3. mean_reversion  : Opposite of momentum (buy dips, sell rallies)
  4. buy_and_hold    : Hold NIFTY 50 index — the classic benchmark
  5. random          : Random signals (reproducible with seed=42)
"""

import logging
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

try:
    import vectorbt as vbt
    VBT_AVAILABLE = True
except ImportError:
    VBT_AVAILABLE = False

from config.settings import TRANSACTION_COST, CONFIDENCE_THRESHOLD, PROCESSED_DIR

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backtesting")

# Annualization factor for NSE (trading days per year)
TRADING_DAYS_PER_YEAR = 252


# ── Helper: Calculate metrics from returns series ─────────────────────────────

def _calc_metrics(returns: pd.Series, name: str = "strategy") -> dict:
    """
    Calculate key performance metrics from a daily returns series.

    Args:
        returns: pd.Series of daily percentage returns (e.g. 0.012 = 1.2%)
        name:    Label for logging

    Returns:
        dict: {sharpe, max_drawdown, cagr, win_rate, total_return}
    """
    if returns.empty or returns.isna().all():
        return {
            "sharpe": 0.0, "max_drawdown": 0.0,
            "cagr": 0.0, "win_rate": 0.0, "total_return": 0.0
        }

    returns = returns.dropna()
    n_days  = len(returns)

    # Total return
    total_return = float((1 + returns).prod() - 1)

    # CAGR (Compound Annual Growth Rate)
    years = n_days / TRADING_DAYS_PER_YEAR
    cagr  = float((1 + total_return) ** (1 / max(years, 0.001)) - 1) if years > 0 else 0.0

    # Sharpe ratio (annualized, risk-free rate = 6% for India)
    rf_daily = 0.06 / TRADING_DAYS_PER_YEAR
    excess   = returns - rf_daily
    sharpe   = float(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) \
               if excess.std() > 0 else 0.0

    # Maximum drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown    = (cumulative - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min())

    # Win rate
    win_rate = float((returns > 0).mean())

    logger.info(
        f"  {name}: total={total_return:.2%} | cagr={cagr:.2%} | "
        f"sharpe={sharpe:.2f} | maxDD={max_drawdown:.2%} | winrate={win_rate:.2%}"
    )

    return {
        "sharpe":       round(sharpe, 4),
        "max_drawdown": round(max_drawdown, 4),
        "cagr":         round(cagr, 4),
        "win_rate":     round(win_rate, 4),
        "total_return": round(total_return, 4),
    }


# ── Core Backtest Function ────────────────────────────────────────────────────

def run_backtest(
    predictions_df: pd.DataFrame,
    price_df: pd.DataFrame,
    nifty_index: Optional[pd.Series] = None,
) -> dict:
    """
    Run full strategy backtest + 5 baselines using vectorbt.

    Args:
        predictions_df: DataFrame with columns:
                        [date, ticker, predicted_direction, confidence]
        price_df:       DataFrame with daily closing prices,
                        columns = ticker symbols, index = Date
        nifty_index:    Optional pd.Series of NIFTY 50 index prices for B&H baseline.
                        If None, loads from processed/NIFTY50_INDEX.csv

    Returns:
        dict: {
            strategy_metrics      : {sharpe, max_drawdown, cagr, win_rate, total_return},
            baselines             : {always_up, momentum, mean_reversion, buy_and_hold, random},
            beats_all_baselines   : bool,
            best_performing_stocks : list of top 5 tickers by accuracy,
            worst_performing_stocks: list of bottom 5 tickers by accuracy,
        }
    """
    logger.info("=" * 60)
    logger.info("MarketPulse AI -- Running Backtest")
    logger.info(f"  Predictions: {len(predictions_df)} rows")
    logger.info(f"  Price data : {price_df.shape} (dates x tickers)")
    logger.info(f"  Confidence threshold: {CONFIDENCE_THRESHOLD}")
    logger.info(f"  Transaction cost    : {TRANSACTION_COST:.1%} per side")
    logger.info("=" * 60)

    # ── Step 0: Validate inputs ───────────────────────────────────────────────
    required_cols = {"date", "ticker", "predicted_direction", "confidence"}
    if not required_cols.issubset(predictions_df.columns):
        missing = required_cols - set(predictions_df.columns)
        raise ValueError(f"predictions_df missing columns: {missing}")

    predictions_df = predictions_df.copy()
    predictions_df["date"] = pd.to_datetime(predictions_df["date"])
    price_df.index = pd.to_datetime(price_df.index)

    # ── Step 1: Build signal matrix ───────────────────────────────────────────
    # Matrix: rows=dates, cols=tickers, values=1 (buy) / 0 (flat)
    # Only include high-confidence signals above threshold
    high_conf = predictions_df[
        predictions_df["confidence"] >= CONFIDENCE_THRESHOLD
    ].copy()

    signal_matrix = high_conf.pivot_table(
        index="date",
        columns="ticker",
        values="predicted_direction",
        aggfunc="first",
    )
    # Convert "bullish"→1, "bearish"→0
    signal_matrix = (signal_matrix == "bullish").astype(float)
    signal_matrix = signal_matrix.reindex(price_df.index, fill_value=0)
    signal_matrix = signal_matrix.reindex(columns=price_df.columns, fill_value=0)

    # ── Step 2: Calculate daily returns of price_df ───────────────────────────
    daily_returns = price_df.pct_change().fillna(0)

    # ── Step 3: Strategy returns (equal-weight active positions) ──────────────
    # Each day: average return of all stocks with "buy" signal
    # Apply transaction costs on position changes
    position_changes = signal_matrix.diff().abs().sum(axis=1)
    tc_drag          = position_changes * TRANSACTION_COST * 2  # both sides

    strategy_daily = (signal_matrix.shift(1) * daily_returns).mean(axis=1)
    strategy_daily = strategy_daily - tc_drag.shift(1).fillna(0)

    logger.info("Strategy returns calculated")
    strategy_metrics = _calc_metrics(strategy_daily, "OUR STRATEGY")

    # ── Step 4: Baseline 1 — Always Up (long all stocks always) ──────────────
    always_up_returns = daily_returns.mean(axis=1)
    b1 = _calc_metrics(always_up_returns, "B1-AlwaysUp")

    # ── Step 5: Baseline 2 — Momentum (buy if rose yesterday) ────────────────
    momentum_signals   = (daily_returns.shift(1) > 0).astype(float)
    momentum_returns   = (momentum_signals * daily_returns).mean(axis=1)
    b2 = _calc_metrics(momentum_returns, "B2-Momentum")

    # ── Step 6: Baseline 3 — Mean Reversion (buy if fell yesterday) ──────────
    reversion_signals  = (daily_returns.shift(1) < 0).astype(float)
    reversion_returns  = (reversion_signals * daily_returns).mean(axis=1)
    b3 = _calc_metrics(reversion_returns, "B3-MeanReversion")

    # ── Step 7: Baseline 4 — Buy and Hold NIFTY 50 ───────────────────────────
    if nifty_index is None:
        nifty_csv = PROCESSED_DIR / "NIFTY50_INDEX.csv"
        if nifty_csv.exists():
            nifty_df    = pd.read_csv(nifty_csv, index_col="Date", parse_dates=True)
            nifty_index = nifty_df["Close"]
        else:
            # Fallback: use average of all stocks
            nifty_index = price_df.mean(axis=1)
            logger.warning("NIFTY50_INDEX.csv not found — using portfolio average as B&H baseline")

    nifty_returns = nifty_index.pct_change().reindex(price_df.index).fillna(0)
    b4 = _calc_metrics(nifty_returns, "B4-BuyAndHold")

    # ── Step 8: Baseline 5 — Random signals (seed=42 for reproducibility) ────
    np.random.seed(42)
    random_signals  = pd.DataFrame(
        np.random.randint(0, 2, size=signal_matrix.shape),
        index=signal_matrix.index,
        columns=signal_matrix.columns,
    ).astype(float)
    random_returns  = (random_signals.shift(1) * daily_returns).mean(axis=1)
    b5 = _calc_metrics(random_returns, "B5-Random")

    # ── Step 9: Per-stock accuracy ────────────────────────────────────────────
    stock_accuracy = _calculate_per_stock_accuracy(high_conf, daily_returns)
    sorted_stocks  = sorted(stock_accuracy.items(), key=lambda x: x[1], reverse=True)
    best_stocks    = [t for t, _ in sorted_stocks[:5]]
    worst_stocks   = [t for t, _ in sorted_stocks[-5:]]

    # ── Step 10: Does our strategy beat ALL baselines? ────────────────────────
    our_sharpe  = strategy_metrics["sharpe"]
    base_sharpes = [b1["sharpe"], b2["sharpe"], b3["sharpe"], b4["sharpe"], b5["sharpe"]]
    beats_all   = all(our_sharpe > b for b in base_sharpes)

    # ── Vectorbt detailed simulation (if available) ───────────────────────────
    if VBT_AVAILABLE:
        try:
            _run_vectorbt_simulation(signal_matrix, price_df)
        except Exception as e:
            logger.warning(f"vectorbt detailed simulation failed: {e} — using manual metrics")

    # ── Final summary ─────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Beats all baselines: {beats_all}")
    logger.info(f"Best stocks  : {best_stocks}")
    logger.info(f"Worst stocks : {worst_stocks}")
    logger.info("=" * 60)

    return {
        "strategy_metrics": strategy_metrics,
        "baselines": {
            "always_up":       b1,
            "momentum":        b2,
            "mean_reversion":  b3,
            "buy_and_hold":    b4,
            "random":          b5,
        },
        "beats_all_baselines":    beats_all,
        "best_performing_stocks": best_stocks,
        "worst_performing_stocks": worst_stocks,
        "per_stock_accuracy":     stock_accuracy,
    }


def _calculate_per_stock_accuracy(
    predictions_df: pd.DataFrame,
    daily_returns: pd.DataFrame,
) -> dict:
    """
    Calculate directional accuracy per stock.

    Accuracy = fraction of predictions where predicted_direction matches
               actual next-day return direction.
    """
    accuracy = {}

    for ticker in predictions_df["ticker"].unique():
        if ticker not in daily_returns.columns:
            continue

        stock_preds = predictions_df[predictions_df["ticker"] == ticker].copy()
        stock_preds = stock_preds.set_index("date")

        # Align with actual returns
        actual = daily_returns[ticker].reindex(stock_preds.index)

        correct = 0
        total   = 0
        for date, row in stock_preds.iterrows():
            if date not in actual.index or pd.isna(actual[date]):
                continue
            actual_up   = actual[date] > 0
            predicted_up = row["predicted_direction"] == "bullish"
            if actual_up == predicted_up:
                correct += 1
            total += 1

        if total > 0:
            accuracy[ticker] = round(correct / total, 4)

    return accuracy


def _run_vectorbt_simulation(
    signal_matrix: pd.DataFrame,
    price_df: pd.DataFrame,
) -> None:
    """
    Run vectorbt portfolio simulation for detailed stats.
    Logs results — does not return (used for additional validation).
    """
    # Entry: go long when signal=1
    entries = signal_matrix.astype(bool)
    exits   = (~signal_matrix.astype(bool)).shift(-1).fillna(False)

    pf = vbt.Portfolio.from_signals(
        price_df.reindex(signal_matrix.index),
        entries,
        exits,
        fees=TRANSACTION_COST,
        freq="1D",
    )

    stats = pf.stats()
    logger.info(f"vectorbt — Total Return: {stats.get('Total Return [%]', 'N/A'):.2f}%")
    logger.info(f"vectorbt — Sharpe Ratio: {stats.get('Sharpe Ratio', 'N/A'):.3f}")
    logger.info(f"vectorbt — Max Drawdown: {stats.get('Max Drawdown [%]', 'N/A'):.2f}%")


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m ml.backtesting
    logger.info("MarketPulse AI -- Backtesting Module")
    logger.info(f"vectorbt available: {VBT_AVAILABLE}")

    # Quick smoke test with synthetic data
    np.random.seed(42)
    n_days    = 500
    tickers   = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
    dates     = pd.date_range("2023-01-01", periods=n_days, freq="B")

    # Synthetic prices
    price_data = {t: 1000 + np.cumsum(np.random.randn(n_days) * 10)
                  for t in tickers}
    price_df   = pd.DataFrame(price_data, index=dates)

    # Synthetic predictions
    preds = []
    for t in tickers:
        for d in dates[::2]:  # predict every other day
            preds.append({
                "date": d,
                "ticker": t,
                "predicted_direction": np.random.choice(["bullish", "bearish"]),
                "confidence": np.random.uniform(0.4, 0.9),
            })
    preds_df = pd.DataFrame(preds)

    result = run_backtest(preds_df, price_df)
    logger.info(f"Strategy Sharpe : {result['strategy_metrics']['sharpe']:.3f}")
    logger.info(f"Beat baselines  : {result['beats_all_baselines']}")
    logger.info("backtesting module OK.")
