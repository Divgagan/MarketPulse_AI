"""
ml/drift_monitor.py — MarketPulse AI
========================================
Improvement #2: Evidently AI Data Drift Detection

Compares the TRAINING distribution of each feature against the
LIVE (last 30 days) distribution. If features drift significantly,
the model is operating on data it has never seen before — predictions
become unreliable.

Outputs:
  - data/drift_reports/YYYY-MM-DD_drift_summary.json  (machine-readable)
  - data/drift_reports/YYYY-MM-DD_drift_report.html   (visual report)
  - Logs a WARNING if any feature drifts above threshold

Called:
  - Monthly from GitHub Actions (same job as retraining)
  - Can be run manually: python -m ml.drift_monitor

Usage:
    monitor = DriftMonitor()
    results = monitor.run_drift_check("RELIANCE.NS")
    monitor.run_all_stocks()
"""

import logging
import json
import warnings
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

logger = logging.getLogger("drift_monitor")

try:
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset
    from evidently.metrics import DatasetDriftMetric
    EVIDENTLY_AVAILABLE = True
except ImportError:
    EVIDENTLY_AVAILABLE = False
    logger.warning(
        "evidently not installed — drift detection disabled. "
        "Run: pip install evidently"
    )

from config.settings import PROCESSED_DIR, DATA_DIR
from config.tickers import ACTIVE_STOCKS

# ── Drift Reports Directory ───────────────────────────────────────────────────
DRIFT_REPORTS_DIR = DATA_DIR / "drift_reports"
DRIFT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Drift threshold — if more than 30% of features drift, flag a WARNING
DRIFT_THRESHOLD_FEATURES_PCT = 0.30

# How many recent days to use as the "live" reference window
LIVE_WINDOW_DAYS = 30

# Core numerical features to monitor (exclude binary indicators and categories)
MONITORED_FEATURES = [
    "daily_return", "weekly_return", "monthly_return", "log_return",
    "rsi_14", "rsi_7",
    "macd", "macd_histogram",
    "bb_width", "bb_position",
    "atr_14", "volume_ratio",
    "price_vs_52w_high", "distance_from_ema200",
    "adx_14", "cci_20",
    "stoch_k", "williams_r", "mfi_14",
]


class DriftMonitor:
    """
    Monitors whether live stock feature distributions have drifted
    away from the training data distribution.

    How it works:
      1. Load the full historical feature CSV for a stock
      2. Split into REFERENCE (all data before the last 30 days)
         and CURRENT (last 30 trading days)
      3. Run Evidently's DataDrift report comparing the two
      4. Save HTML + JSON results
      5. Return a drift severity score (GREEN / YELLOW / RED)
    """

    def __init__(self):
        self.today_str = datetime.now().strftime("%Y-%m-%d")

    def run_drift_check(self, ticker: str) -> dict:
        """
        Run a full drift check for one stock.

        Returns:
            dict: {
                ticker, drift_score, severity, drifted_features,
                total_features, drift_pct, report_path
            }
        """
        features_csv = PROCESSED_DIR / f"{ticker}_features.csv"

        if not features_csv.exists():
            logger.warning(f"  {ticker}: Features CSV not found — skipping drift check")
            return self._fallback(ticker, "CSV not found")

        # ── Load data ─────────────────────────────────────────────────────────
        df = pd.read_csv(features_csv, index_col="Date", parse_dates=True)
        df = df.sort_index()

        # Select only monitored numerical features that exist in this file
        available = [f for f in MONITORED_FEATURES if f in df.columns]
        if len(available) < 5:
            logger.warning(f"  {ticker}: Too few features available ({len(available)}) — skipping")
            return self._fallback(ticker, "Insufficient features")

        df = df[available].dropna()

        # ── Split: Reference (training) vs Current (live) ─────────────────────
        cutoff = df.index.max() - timedelta(days=LIVE_WINDOW_DAYS)
        reference = df[df.index <= cutoff]
        current   = df[df.index > cutoff]

        if len(reference) < 100 or len(current) < 10:
            logger.warning(
                f"  {ticker}: Insufficient data — "
                f"reference={len(reference)}, current={len(current)}"
            )
            return self._fallback(ticker, "Insufficient data for split")

        logger.info(
            f"  {ticker}: Drift check — "
            f"reference={len(reference)} rows, current={len(current)} rows"
        )

        # ── Fallback if evidently not available ───────────────────────────────
        if not EVIDENTLY_AVAILABLE:
            return self._manual_drift_check(ticker, reference, current, available)

        # ── Run Evidently Drift Report ─────────────────────────────────────────
        try:
            report = Report(metrics=[DataDriftPreset()])
            report.run(reference_data=reference, current_data=current)

            # Save HTML report
            html_path = DRIFT_REPORTS_DIR / f"{self.today_str}_{ticker}_drift.html"
            report.save_html(str(html_path))

            # Extract JSON results
            report_dict = report.as_dict()
            drift_results = report_dict.get("metrics", [{}])[0].get("result", {})

            drift_score     = drift_results.get("dataset_drift", False)
            share_drifted   = drift_results.get("share_of_drifted_columns", 0.0)
            drifted_cols    = [
                col for col, stats in drift_results.get("drift_by_columns", {}).items()
                if stats.get("drift_detected", False)
            ]

        except Exception as e:
            logger.warning(f"  {ticker}: Evidently report failed — {e}. Using manual check.")
            return self._manual_drift_check(ticker, reference, current, available)

        # ── Determine severity ─────────────────────────────────────────────────
        severity = self._severity(share_drifted)
        if severity == "RED":
            logger.warning(
                f"  {ticker}: 🔴 HIGH DRIFT — {share_drifted:.0%} of features drifted! "
                f"Retraining recommended. Drifted: {drifted_cols}"
            )
        elif severity == "YELLOW":
            logger.warning(
                f"  {ticker}: 🟡 MODERATE DRIFT — {share_drifted:.0%} of features drifted. "
                f"Monitor closely."
            )
        else:
            logger.info(f"  {ticker}: 🟢 LOW DRIFT — {share_drifted:.0%} features drifted. OK.")

        result = {
            "ticker":           ticker,
            "checked_at":       self.today_str,
            "drift_detected":   drift_score,
            "drift_pct":        round(share_drifted, 4),
            "severity":         severity,
            "drifted_features": drifted_cols,
            "total_features":   len(available),
            "reference_rows":   len(reference),
            "current_rows":     len(current),
            "report_path":      str(html_path),
        }
        return result

    def _manual_drift_check(
        self, ticker: str, reference: pd.DataFrame,
        current: pd.DataFrame, features: list
    ) -> dict:
        """
        Fallback drift check using Population Stability Index (PSI).
        PSI > 0.2 per feature = significant drift.
        Used when Evidently is not installed.
        """
        drifted = []
        for col in features:
            try:
                ref_vals = reference[col].dropna().values
                cur_vals = current[col].dropna().values
                psi = self._psi(ref_vals, cur_vals)
                if psi > 0.20:
                    drifted.append(col)
            except Exception:
                pass

        share_drifted = len(drifted) / max(len(features), 1)
        severity = self._severity(share_drifted)

        if severity in ("RED", "YELLOW"):
            logger.warning(
                f"  {ticker}: [{severity}] Manual drift check — "
                f"{share_drifted:.0%} features drifted (PSI > 0.2): {drifted}"
            )

        return {
            "ticker":           ticker,
            "checked_at":       self.today_str,
            "drift_detected":   share_drifted > DRIFT_THRESHOLD_FEATURES_PCT,
            "drift_pct":        round(share_drifted, 4),
            "severity":         severity,
            "drifted_features": drifted,
            "total_features":   len(features),
            "method":           "PSI_manual",
            "report_path":      None,
        }

    @staticmethod
    def _psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
        """
        Population Stability Index (PSI).
        Measures how much a distribution has shifted.
        PSI < 0.1  → stable
        PSI 0.1-0.2 → moderate shift
        PSI > 0.2  → significant drift
        """
        ref_min = min(reference.min(), current.min())
        ref_max = max(reference.max(), current.max())
        if ref_min == ref_max:
            return 0.0

        bin_edges = np.linspace(ref_min, ref_max, bins + 1)
        ref_hist, _ = np.histogram(reference, bins=bin_edges)
        cur_hist, _ = np.histogram(current,   bins=bin_edges)

        ref_pct = ref_hist / (ref_hist.sum() + 1e-9) + 1e-9
        cur_pct = cur_hist / (cur_hist.sum() + 1e-9) + 1e-9

        psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
        return float(psi)

    @staticmethod
    def _severity(share_drifted: float) -> str:
        if share_drifted >= 0.40:
            return "RED"
        elif share_drifted >= 0.20:
            return "YELLOW"
        return "GREEN"

    @staticmethod
    def _fallback(ticker: str, reason: str) -> dict:
        return {
            "ticker":           ticker,
            "checked_at":       datetime.now().strftime("%Y-%m-%d"),
            "drift_detected":   False,
            "drift_pct":        0.0,
            "severity":         "UNKNOWN",
            "drifted_features": [],
            "total_features":   0,
            "error":            reason,
        }

    def run_all_stocks(self, save_summary: bool = True) -> dict:
        """
        Run drift checks for all 50 NIFTY stocks.
        Saves a master JSON summary to drift_reports/.

        Returns:
            dict of {ticker: drift_result}
        """
        logger.info("=" * 60)
        logger.info("MarketPulse AI — Running Data Drift Check (All Stocks)")
        logger.info(f"  Method: {'Evidently AI' if EVIDENTLY_AVAILABLE else 'PSI Manual'}")
        logger.info(f"  Live window: last {LIVE_WINDOW_DAYS} days")
        logger.info(f"  Reports dir: {DRIFT_REPORTS_DIR}")
        logger.info("=" * 60)

        all_results = {}
        red_count = yellow_count = green_count = 0

        for ticker in ACTIVE_STOCKS.keys():
            result = self.run_drift_check(ticker)
            all_results[ticker] = result

            sev = result.get("severity", "UNKNOWN")
            if sev == "RED":     red_count += 1
            elif sev == "YELLOW": yellow_count += 1
            elif sev == "GREEN":  green_count += 1

        # ── Summary ───────────────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info(
            f"Drift Summary: 🔴 RED={red_count} | 🟡 YELLOW={yellow_count} | "
            f"🟢 GREEN={green_count}"
        )

        if red_count > 0:
            red_tickers = [t for t, r in all_results.items() if r.get("severity") == "RED"]
            logger.warning(f"  RETRAINING RECOMMENDED for: {red_tickers}")

        if save_summary:
            summary_path = DRIFT_REPORTS_DIR / f"{self.today_str}_drift_summary.json"
            with open(summary_path, "w") as f:
                json.dump(all_results, f, indent=2)
            logger.info(f"  Summary saved → {summary_path}")

        logger.info("=" * 60)
        return all_results


# ── Standalone Runner ─────────────────────────────────────────────────────────
def run_weekly_drift_check() -> dict:
    """
    Entry point for GitHub Actions monthly drift job.
    Called from: .github/workflows/agent_pipeline.yml
    """
    monitor = DriftMonitor()
    return monitor.run_all_stocks(save_summary=True)


# ── Main Block ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("MarketPulse AI — Drift Monitor")
    logger.info(f"Evidently available: {EVIDENTLY_AVAILABLE}")

    monitor = DriftMonitor()

    # Run on a single stock first for quick validation
    import sys
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
    result = monitor.run_drift_check(test_ticker)
    logger.info(f"Result: {result}")
