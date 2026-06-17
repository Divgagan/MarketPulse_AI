"""
ml/regime_detector.py — MarketPulse AI
========================================
Uses a Hidden Markov Model (HMM) to classify the current market into one of
three regimes: Bull, Bear, or Sideways.

WHY HMM FOR REGIME DETECTION?
- Markets have hidden states (bull/bear/sideways) that aren't directly observable
- HMM learns these states from observable signals (returns + volatility)
- The regime is then used as a feature in LightGBM — a bull-regime bullish signal
  is more reliable than the same signal during a bear regime

The regime model is trained on NIFTY 50 index data (^NSEI) — a market-wide
signal. Individual stock models then use this regime as a feature.

Classes:
  - MarketRegimeDetector : HMM wrapper with fit/predict/save/load

Standalone functions:
  - fit_and_save_all_regime_models() : Train and save, update all feature CSVs
"""

import logging
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from hmmlearn.hmm import GaussianHMM

from config.settings import PROCESSED_DIR, MODELS_DIR

# ── Logger ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("regime_detector")

# Regime encoding for ML feature column (numeric)
REGIME_ENCODING = {"bull": 2, "sideways": 1, "bear": 0}


# ── MarketRegimeDetector Class ────────────────────────────────────────────────

class MarketRegimeDetector:
    """
    Hidden Markov Model wrapper for market regime detection.

    Classifies each trading day as one of: "bull", "bear", "sideways"

    The HMM uses two observable features:
      1. Daily return      : captures direction
      2. Rolling volatility: captures risk environment

    Together, these two features allow the HMM to learn:
      - Bull regime  : positive returns, lower-moderate volatility
      - Bear regime  : negative returns, higher volatility
      - Sideways     : near-zero returns, moderate volatility
    """

    def __init__(self, n_states: int = 3):
        """
        Initialize the HMM with 3 hidden states (bull/bear/sideways).

        Args:
            n_states: Number of hidden states (default 3 — do not change)

        GaussianHMM parameters:
          - covariance_type="full" : each state has its own full covariance matrix
            (more flexible than "diag" — captures correlation between features)
          - n_iter=1000 : enough EM iterations for convergence on 10 years of data
        """
        self.n_states = n_states
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=1000,
            random_state=42,  # Reproducibility
        )
        self.state_labels = {}   # Maps HMM state integer → "bull"/"bear"/"sideways"
        self.is_fitted = False

    def _prepare_features(self, price_series: pd.Series) -> np.ndarray:
        """
        Prepare observation features from a price series for HMM.

        Features:
          1. daily_return    : % change day over day (captures direction)
          2. rolling_vol_5d  : 5-day rolling std of returns (captures volatility)

        Returns:
            np.ndarray of shape (n_days, 2) with NaN rows removed
        """
        returns = price_series.pct_change().dropna()

        # 5-day rolling volatility — short enough to capture regime changes quickly
        volatility = returns.rolling(window=5).std().dropna()

        # Align both series (volatility has fewer rows due to rolling)
        returns = returns.loc[volatility.index]

        # Stack into (n_samples, 2) feature matrix
        features = np.column_stack([returns.values, volatility.values])

        # Remove any remaining NaN rows
        valid_mask = ~np.isnan(features).any(axis=1)
        return features[valid_mask]

    def fit(self, price_series: pd.Series) -> None:
        """
        Fit the HMM on a price series to learn the three market regimes.

        After fitting, identifies which HMM state corresponds to which regime:
          - State with HIGHEST mean return  → "bull"
          - State with LOWEST mean return   → "bear"
          - Remaining state                 → "sideways"

        Args:
            price_series: pd.Series of closing prices (Date index)
        """
        logger.info(f"Fitting HMM on {len(price_series)} price observations...")

        features = self._prepare_features(price_series)

        if len(features) < 100:
            raise ValueError(
                f"Not enough data to fit HMM: {len(features)} rows "
                f"(need at least 100). Download more historical data."
            )

        # Fit the Gaussian HMM via Expectation-Maximization algorithm
        self.model.fit(features)

        # ── Identify which state is bull/bear/sideways ────────────────────────
        # The HMM assigns arbitrary integers (0, 1, 2) to states.
        # We identify them by looking at mean return of each state.
        # state_means shape: (n_states, 2) — column 0 is return, column 1 is vol
        state_means = self.model.means_[:, 0]  # Mean return per state

        # Sort states by mean return
        sorted_states = np.argsort(state_means)

        # Lowest mean return → bear, highest → bull, middle → sideways
        self.state_labels = {
            int(sorted_states[0]): "bear",      # Most negative returns
            int(sorted_states[1]): "sideways",  # Near-zero returns
            int(sorted_states[2]): "bull",      # Most positive returns
        }

        self.is_fitted = True

        logger.info("HMM fitted successfully.")
        logger.info("State identification:")
        for state_num, label in self.state_labels.items():
            mean_ret = state_means[state_num] * 100
            logger.info(f"  State {state_num} → {label:8s} (mean daily return: {mean_ret:.4f}%)")

    def predict_regime(self, price_series: pd.Series) -> pd.Series:
        """
        Predict regime label for each day in the price series.

        Args:
            price_series: pd.Series of closing prices

        Returns:
            pd.Series of regime labels ("bull"/"bear"/"sideways") aligned with
            the input index (shorter by ~6 rows due to rolling window)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        features = self._prepare_features(price_series)

        # Predict hidden state sequence
        state_sequence = self.model.predict(features)

        # Map integers to regime labels
        labels = [self.state_labels[s] for s in state_sequence]

        # Reconstruct index alignment
        # features are offset by 6 rows (1 for pct_change + 5 for rolling std)
        # Use the tail of the price_series index to align
        aligned_index = price_series.dropna().index[-len(labels):]

        return pd.Series(labels, index=aligned_index, name="market_regime")

    def get_current_regime(self, price_series: pd.Series) -> str:
        """
        Return the regime label for the MOST RECENT trading day.

        Args:
            price_series: pd.Series of closing prices (must have recent data)

        Returns:
            str: one of "bull", "bear", "sideways"
        """
        regime_series = self.predict_regime(price_series)

        if regime_series.empty:
            logger.warning("Could not determine current regime — returning 'sideways'")
            return "sideways"

        current = regime_series.iloc[-1]
        logger.info(f"Current market regime: {current.upper()}")
        return current

    def save(self, filepath: str) -> None:
        """
        Save the fitted HMM model to disk using joblib.

        Args:
            filepath: Path to save the .pkl file (e.g., data/models/regime_model.pkl)
        """
        if not self.is_fitted:
            raise RuntimeError("Cannot save — model has not been fitted yet.")

        save_data = {
            "model": self.model,
            "state_labels": self.state_labels,
            "n_states": self.n_states,
            "is_fitted": self.is_fitted,
        }
        joblib.dump(save_data, filepath)
        logger.info(f"Regime model saved to {filepath}")

    def load(self, filepath: str) -> None:
        """
        Load a previously saved HMM model from disk.

        Args:
            filepath: Path to the saved .pkl file
        """
        save_data = joblib.load(filepath)
        self.model = save_data["model"]
        self.state_labels = save_data["state_labels"]
        self.n_states = save_data["n_states"]
        self.is_fitted = save_data["is_fitted"]
        logger.info(f"Regime model loaded from {filepath}")
        logger.info(f"State labels: {self.state_labels}")


# ── Standalone: Train and Save All Regime Models ──────────────────────────────

def fit_and_save_all_regime_models() -> None:
    """
    Train one HMM regime model on NIFTY 50 index data and:
      1. Save the model to data/models/regime_model.pkl
      2. Add 'market_regime' column to each stock's _features.csv

    The regime model is MARKET-WIDE (trained on ^NSEI index), not per-stock.
    This is correct because regime reflects macro conditions, not individual stocks.

    Called:
      - Once during initial setup (setup.py)
      - Monthly by retrain pipeline
    """
    logger.info("=" * 60)
    logger.info("Starting regime model training")
    logger.info("=" * 60)

    # ── Step 1: Load NIFTY 50 index data ─────────────────────────────────────
    index_csv = PROCESSED_DIR / "NIFTY50_INDEX.csv"

    if not index_csv.exists():
        logger.error(
            "NIFTY50_INDEX.csv not found! "
            "Run ml/data_collector.py first to download index data."
        )
        return

    logger.info(f"Loading NIFTY 50 index from {index_csv}...")
    index_df = pd.read_csv(index_csv, index_col="Date", parse_dates=True)

    if index_df.empty or "Close" not in index_df.columns:
        logger.error("Index CSV is empty or missing Close column.")
        return

    nifty_close = index_df["Close"].dropna()
    logger.info(f"NIFTY 50 index: {len(nifty_close)} days loaded")

    # ── Step 2: Fit the HMM on index data ────────────────────────────────────
    detector = MarketRegimeDetector(n_states=3)

    try:
        detector.fit(nifty_close)
    except Exception as e:
        logger.error(f"HMM fitting failed: {e}")
        return

    # ── Step 3: Save the model ────────────────────────────────────────────────
    model_path = MODELS_DIR / "regime_model.pkl"
    detector.save(str(model_path))

    # ── Step 4: Predict regime for entire index history ───────────────────────
    regime_series = detector.predict_regime(nifty_close)
    logger.info(f"Regime predictions: {len(regime_series)} days")

    # Distribution of regimes
    regime_counts = regime_series.value_counts()
    logger.info("Regime distribution:")
    for regime, count in regime_counts.items():
        pct = count / len(regime_series) * 100
        logger.info(f"  {regime:10s}: {count} days ({pct:.1f}%)")

    # ── Step 5: Add regime as feature to each stock's features CSV ───────────
    # Encode: bull=2, sideways=1, bear=0 (numeric for LightGBM)
    regime_encoded = regime_series.map(REGIME_ENCODING)

    logger.info("Adding market_regime column to all stock feature CSVs...")
    updated = 0
    skipped = 0

    from config.tickers import ACTIVE_STOCKS

    for ticker in ACTIVE_STOCKS.keys():
        features_csv = PROCESSED_DIR / f"{ticker}_features.csv"

        if not features_csv.exists():
            logger.warning(f"  {ticker}: _features.csv not found — run feature_engineering first")
            skipped += 1
            continue

        try:
            features_df = pd.read_csv(features_csv, index_col="Date", parse_dates=True)

            # Join regime to features (inner join — keeps only dates that exist in both)
            features_df["market_regime"] = regime_encoded.reindex(features_df.index)

            # Fill any missing regime values with "sideways" (1) — safe default
            features_df["market_regime"] = features_df["market_regime"].fillna(1).astype(int)

            features_df.to_csv(features_csv)
            updated += 1

        except Exception as e:
            logger.error(f"  {ticker}: Failed to update — {e}")
            skipped += 1

    logger.info("=" * 60)
    logger.info(f"Regime model training complete.")
    logger.info(f"  Model saved to : {model_path}")
    logger.info(f"  CSVs updated   : {updated}")
    logger.info(f"  CSVs skipped   : {skipped}")
    logger.info("=" * 60)


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test import and basic class instantiation
    # Run from project root as: python -m ml.regime_detector
    # Full training requires NIFTY50_INDEX.csv (run data_collector.py first)

    logger.info("MarketPulse AI -- Regime Detector Module")
    logger.info("Checking if NIFTY50 index data exists...")

    index_csv = PROCESSED_DIR / "NIFTY50_INDEX.csv"

    if index_csv.exists():
        logger.info("Index data found -- running full regime training...")
        fit_and_save_all_regime_models()
    else:
        logger.warning("NIFTY50_INDEX.csv not found.")
        logger.info("Module imports OK.")
        logger.info("Run ml/data_collector.py first to download index data,")
        logger.info("then run this file again to train the regime model.")

        # Quick unit test of the utility functions
        detector = MarketRegimeDetector()
        logger.info(f"MarketRegimeDetector instantiated OK (n_states={detector.n_states})")
        logger.info("HMM model ready to fit once data is available.")
