"""
ml/chronos_forecaster.py — MarketPulse AI
==========================================
Blueprint Part 8: Amazon Chronos zero-shot time series forecaster.

WHY CHRONOS?
  Chronos is a pre-trained probabilistic time series model from Amazon Research
  (HuggingFace: amazon/chronos-t5-small). It requires NO training on our data —
  it runs zero-shot on any price series.

  This is the "differentiator" in our ML stack. LightGBM learns patterns from
  features. Chronos learns temporal patterns directly from raw price trajectories.
  Their signals are complementary and combining them improves overall accuracy.

HOW IT WORKS:
  1. Feed last 60 days of closing prices as "context"
  2. Chronos predicts next 5 days of price trajectories (20 samples = probabilistic)
  3. Median of 20 samples = most likely trajectory
  4. If day-5 price > today's price → bullish signal
  5. Spread of 20 samples = confidence (tight = confident, wide = uncertain)

USAGE IN PIPELINE:
  - Runs once per day at EOD (takes ~30-60 sec total for all 50 stocks on CPU)
  - Output fed into signal_combiner.py alongside LightGBM predictions
  - Weight in final ensemble: 30% (Blueprint spec)

Classes:
  - ChronosForecaster : full forecasting class

Standalone functions:
  - forecast_all_stocks(price_data) : batch forecast all 50 stocks
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

import torch

from config.settings import PROCESSED_DIR
from config.tickers import ACTIVE_STOCKS

# ── Logger ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chronos_forecaster")

# ── Lazy import Chronos (avoids crash if not installed) ───────────────────────
try:
    from chronos import ChronosPipeline
    CHRONOS_AVAILABLE = True
except ImportError:
    CHRONOS_AVAILABLE = False
    logger.warning(
        "chronos-forecasting not installed. "
        "Run: pip install chronos-forecasting"
    )


# ── ChronosForecaster Class ────────────────────────────────────────────────────

class ChronosForecaster:
    """
    Zero-shot time series forecaster using Amazon Chronos-T5-Small.

    No training needed — the model is pre-trained on a large corpus of
    real-world time series data from multiple domains.

    Usage:
        forecaster = ChronosForecaster()
        result = forecaster.forecast_direction(price_series, "RELIANCE.NS")
        # result = {"chronos_direction": "bullish", "chronos_confidence": 0.72, ...}
    """

    def __init__(self):
        """
        Load Chronos T5-Small model.

        Model choice: chronos-t5-small (not tiny/base/large)
          - tiny : fastest, least accurate
          - small: good balance — loads in ~5 sec, 30-60 sec for 50 stocks
          - base : 2x slower, marginal improvement for daily data
          - large: too slow for real-time use on CPU

        torch_dtype=bfloat16: halves memory usage vs float32.
        device_map="cpu":     no GPU required.
        """
        if not CHRONOS_AVAILABLE:
            self.pipeline = None
            logger.error("Chronos not available. Install: pip install chronos-forecasting")
            return

        logger.info("Loading Chronos T5-Small model (first run downloads ~300MB)...")

        try:
            self.pipeline = ChronosPipeline.from_pretrained(
                "amazon/chronos-t5-small",
                device_map="cpu",
                dtype=torch.bfloat16,  # torch_dtype deprecated in v2.x
            )
            logger.info("Chronos model loaded successfully.")
        except Exception as e:
            self.pipeline = None
            logger.error(f"Failed to load Chronos model: {e}")

        # Forecast configuration
        self.prediction_horizon = 5   # Predict next 5 trading days
        self.context_length     = 60  # Use last 60 days as context
        self.num_samples        = 20  # Probabilistic samples (spread = uncertainty)
        self.neutral_threshold  = 0.005  # Within 0.5% = "neutral" (not bullish/bearish)

    # ── Single Stock Forecast ──────────────────────────────────────────────────

    def forecast_direction(self, price_series: pd.Series, ticker: str) -> dict:
        """
        Forecast next 5-day price direction for one stock.

        Args:
            price_series : pd.Series of closing prices (Date index, recent last)
            ticker       : Ticker symbol (for logging and return dict)

        Returns:
            dict: {
                ticker               : str,
                chronos_direction    : "bullish" / "bearish" / "neutral",
                chronos_confidence   : float 0.0–1.0,
                forecast_horizon_days: 5,
                predicted_change_pct : float (% change from today to day-5 median),
                current_price        : float,
                median_day5_price    : float,
            }

        Returns a "neutral" fallback dict if Chronos unavailable or forecast fails.
        """
        if self.pipeline is None:
            return self._fallback_result(ticker, "Chronos model not loaded")

        if len(price_series) < self.context_length:
            logger.warning(
                f"  {ticker}: Only {len(price_series)} rows, need {self.context_length}. "
                f"Using all available."
            )

        # ── Step 1: Prepare context window ────────────────────────────────────
        # Take last context_length prices, drop NaN, convert to float32 tensor
        context_prices = price_series.dropna().tail(self.context_length).values.astype("float32")
        current_price  = float(context_prices[-1])

        context_tensor = torch.tensor(context_prices).unsqueeze(0)  # Shape: (1, context_len)

        # ── Step 2: Run Chronos forecast ──────────────────────────────────────
        try:
            with torch.no_grad():
                # Chronos v2.x: context is a positional argument (not keyword)
                forecast = self.pipeline.predict(
                    context_tensor,               # positional — must not use context=
                    self.prediction_horizon,       # prediction_length positional
                    num_samples=self.num_samples,
                )
            # forecast shape: (1, num_samples, prediction_horizon)
            forecast_samples = forecast[0].numpy()  # (num_samples, 5)

        except Exception as e:
            logger.warning(f"  {ticker}: Chronos prediction failed — {e}")
            return self._fallback_result(ticker, str(e))

        # ── Step 3: Calculate direction from median trajectory ─────────────────
        # Median across 20 probabilistic samples → most likely trajectory
        median_trajectory = np.median(forecast_samples, axis=0)  # Shape: (5,)
        median_day5_price = float(median_trajectory[-1])

        predicted_change_pct = (median_day5_price - current_price) / current_price

        if predicted_change_pct > self.neutral_threshold:
            direction = "bullish"
        elif predicted_change_pct < -self.neutral_threshold:
            direction = "bearish"
        else:
            direction = "neutral"

        # ── Step 4: Calculate confidence from sample spread ───────────────────
        # Low spread (samples agree) → high confidence
        # High spread (samples disagree) → low confidence
        # Confidence = 1 - (std of day-5 predictions / current_price)
        # Clipped to [0.1, 0.95] range
        day5_std          = float(np.std(forecast_samples[:, -1]))
        relative_spread   = day5_std / (current_price + 1e-9)

        # Inverse relationship: more spread = less confidence
        # Scale: 0.05 relative spread = 0.5 confidence, 0.02 = 0.8 confidence
        confidence = float(np.clip(1.0 - (relative_spread * 10), 0.10, 0.95))

        result = {
            "ticker":                ticker,
            "chronos_direction":     direction,
            "chronos_confidence":    round(confidence, 4),
            "forecast_horizon_days": self.prediction_horizon,
            "predicted_change_pct":  round(predicted_change_pct * 100, 4),
            "current_price":         round(current_price, 2),
            "median_day5_price":     round(median_day5_price, 2),
        }

        logger.info(
            f"  {ticker}: {direction.upper()} | "
            f"change={predicted_change_pct * 100:+.2f}% | "
            f"confidence={confidence:.2f} | "
            f"price: {current_price:.2f} → {median_day5_price:.2f}"
        )
        return result

    # ── Batch Forecast All Stocks ──────────────────────────────────────────────

    def forecast_all_stocks(self, price_data: dict) -> dict:
        """
        Forecast direction for a batch of stocks.

        Args:
            price_data: dict of {ticker: pd.Series of closing prices}

        Returns:
            dict of {ticker: forecast_result_dict}

        Note: Errors per stock are caught individually — one failure does not
              crash the whole pipeline. Failed stocks return neutral fallback.
        """
        if self.pipeline is None:
            logger.error("Chronos model not loaded — returning neutral fallbacks for all stocks")
            return {ticker: self._fallback_result(ticker, "Model not loaded")
                    for ticker in price_data}

        logger.info(f"Running Chronos forecasts for {len(price_data)} stocks...")
        results = {}
        bullish = bearish = neutral = errors = 0

        for idx, (ticker, price_series) in enumerate(price_data.items(), start=1):
            try:
                result = self.forecast_direction(price_series, ticker)
                results[ticker] = result

                d = result["chronos_direction"]
                if d == "bullish":   bullish += 1
                elif d == "bearish": bearish += 1
                else:                neutral += 1

            except Exception as e:
                logger.error(f"  [{idx}] {ticker}: Unexpected error — {e}")
                results[ticker] = self._fallback_result(ticker, str(e))
                errors += 1

        logger.info(
            f"Chronos complete: "
            f"Bullish={bullish} | Bearish={bearish} | Neutral={neutral} | Errors={errors}"
        )
        return results

    # ── Fallback Result ────────────────────────────────────────────────────────

    @staticmethod
    def _fallback_result(ticker: str, reason: str = "") -> dict:
        """
        Return a neutral fallback dict when Chronos fails for a stock.
        Pipeline continues normally — neutral means no Chronos adjustment.
        """
        logger.debug(f"  {ticker}: Returning neutral fallback ({reason})")
        return {
            "ticker":                ticker,
            "chronos_direction":     "neutral",
            "chronos_confidence":    0.0,
            "forecast_horizon_days": 5,
            "predicted_change_pct":  0.0,
            "current_price":         0.0,
            "median_day5_price":     0.0,
        }


# ── Standalone: Load Price Data + Forecast All 50 ────────────────────────────

def forecast_all_stocks(price_data: Optional[dict] = None) -> dict:
    """
    Standalone function to forecast all NIFTY 50 stocks.
    Called by EOD pipeline once per day.

    Args:
        price_data: Optional dict of {ticker: pd.Series of closing prices}.
                    If None, loads from processed CSVs automatically.

    Returns:
        dict of {ticker: forecast_result}
    """
    # ── Load price data from CSVs if not provided ─────────────────────────────
    if price_data is None:
        logger.info("Loading price data from processed CSVs...")
        price_data = {}

        for ticker in ACTIVE_STOCKS.keys():
            csv_path = PROCESSED_DIR / f"{ticker}.csv"

            if not csv_path.exists():
                logger.warning(f"  {ticker}: Raw CSV not found — skipping Chronos")
                continue

            try:
                df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
                if "Close" in df.columns:
                    price_data[ticker] = df["Close"].dropna()
                else:
                    logger.warning(f"  {ticker}: No Close column in CSV")
            except Exception as e:
                logger.error(f"  {ticker}: Failed to load CSV — {e}")

        logger.info(f"Loaded price data for {len(price_data)} stocks")

    # ── Run Chronos forecasts ──────────────────────────────────────────────────
    forecaster = ChronosForecaster()
    return forecaster.forecast_all_stocks(price_data)


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m ml.chronos_forecaster
    logger.info("MarketPulse AI -- Chronos Forecaster Module")

    if not CHRONOS_AVAILABLE:
        logger.error("chronos-forecasting not installed.")
        logger.info("Install: pip install chronos-forecasting")
    else:
        # Quick smoke test with synthetic data (no real data needed)
        logger.info("Running smoke test with synthetic price series...")

        np.random.seed(42)
        # Simulate 100 days of trending price data
        prices = pd.Series(
            1000 + np.cumsum(np.random.randn(100) * 10),
            name="Close"
        )

        forecaster = ChronosForecaster()

        if forecaster.pipeline is not None:
            result = forecaster.forecast_direction(prices, "TEST.NS")
            logger.info(f"Smoke test result: {result}")
            logger.info("Chronos forecaster module OK.")
        else:
            logger.error("Chronos pipeline failed to load.")
