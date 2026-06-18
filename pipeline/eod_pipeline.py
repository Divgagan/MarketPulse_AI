"""
pipeline/eod_pipeline.py — MarketPulse AI
==========================================
Blueprint Part 17 File 1: EOD Pipeline.

Runs every day at 3:45 PM IST (15 minutes after market close).
Executes the full ML pipeline first, then passes ML results to agents.

Pipeline steps:
  1. Update price data (yfinance → SQLite)
  2. Re-engineer features (OHLCV → 50+ technical indicators)
  3. Detect market regime (HMM model)
  4. LightGBM/CatBoost predictions for all 50 stocks
  5. Chronos zero-shot forecasts for all 50 stocks
  6. Combine ML signals (60/30/10 weight ensemble)
  7. Run LangGraph agent pipeline with ML signals
  8. (Monthly) Retrain models on 1st of month

Also exposes run_monthly_retrain() for the scheduler.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.tickers import ACTIVE_STOCKS
from config.settings import DATA_DIR, MODELS_DIR, PROCESSED_DIR, RAW_DIR
from pipeline.send_alerts import send_email_alert

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("eod_pipeline")


# ── Helper: Load NIFTY Index close series ────────────────────────────────────

def _load_nifty_close():
    """
    Load NIFTY 50 index (^NSEI) close prices from processed data.
    Used by regime detector.

    Returns:
        pandas.Series of close prices indexed by date, or None if unavailable.
    """
    try:
        import pandas as pd
        nifty_path = PROCESSED_DIR / "^NSEI_features.parquet"
        if not nifty_path.exists():
            # Try to fetch on the fly
            import yfinance as yf
            df = yf.download("^NSEI", period="2y", progress=False, auto_adjust=True)
            if not df.empty:
                return df["Close"]
        else:
            df = pd.read_parquet(nifty_path)
            if "close" in df.columns:
                return df["close"]
            elif "Close" in df.columns:
                return df["Close"]
    except Exception as e:
        logger.warning(f"Could not load NIFTY close series: {e}")
    return None


# ── Step Functions ────────────────────────────────────────────────────────────

def _step1_update_price_data() -> None:
    """Step 1: Fetch latest OHLCV data from yfinance → SQLite."""
    try:
        from ml.data_collector import update_all_stocks_daily
        logger.info("Step 1: Updating price data (yfinance → SQLite)...")
        update_all_stocks_daily()
        logger.info("Step 1 complete.")
    except Exception as e:
        logger.error(f"Step 1 FAILED: {e}")
        raise


def _step2_engineer_features() -> None:
    """Step 2: Compute 50+ technical indicators for all stocks."""
    try:
        from ml.feature_engineering import engineer_all_stocks
        logger.info("Step 2: Engineering features (50+ indicators)...")
        engineer_all_stocks()
        logger.info("Step 2 complete.")
    except Exception as e:
        logger.error(f"Step 2 FAILED: {e}")
        raise


def _step3_get_regime() -> str:
    """Step 3: Detect current market regime using HMM model."""
    try:
        from ml.regime_detector import MarketRegimeDetector
        logger.info("Step 3: Detecting market regime...")

        regime_model = MarketRegimeDetector()
        regime_path  = MODELS_DIR / "regime_model.pkl"

        nifty_close = _load_nifty_close()

        if regime_path.exists() and nifty_close is not None:
            regime_model.load(str(regime_path))
            current_regime = regime_model.get_current_regime(nifty_close)
        else:
            logger.warning("  Regime model or NIFTY data missing — defaulting to 'unknown'")
            current_regime = "unknown"

        logger.info(f"Step 3 complete: regime = {current_regime}")
        return current_regime

    except Exception as e:
        logger.warning(f"Step 3 FAILED (non-fatal): {e} — defaulting to 'unknown'")
        return "unknown"


def _step4_lgbm_predictions(current_regime: str) -> list:
    """Step 4: LightGBM/CatBoost ensemble predictions for all 50 stocks."""
    try:
        from ml.predictor import predict_all_stocks
        logger.info("Step 4: Running LightGBM/CatBoost predictions...")
        predictions = predict_all_stocks(current_regime=current_regime)
        logger.info(f"Step 4 complete: {len(predictions)} predictions")
        return predictions
    except Exception as e:
        logger.error(f"Step 4 FAILED: {e}")
        return []


def _step5_chronos_forecasts() -> dict:
    """Step 5: Chronos zero-shot time-series forecasts for all 50 stocks."""
    try:
        import pandas as pd
        from ml.chronos_forecaster import ChronosForecaster
        logger.info("Step 5: Running Chronos zero-shot forecasts...")

        # Load price data for all stocks
        price_data_dict = {}
        for ticker in ACTIVE_STOCKS:
            try:
                path = PROCESSED_DIR / f"{ticker}_features.parquet"
                if path.exists():
                    df = pd.read_parquet(path)
                    col = "close" if "close" in df.columns else "Close"
                    if col in df.columns:
                        price_data_dict[ticker] = df[col]
            except Exception:
                pass

        if not price_data_dict:
            logger.warning("  No processed price data found — skipping Chronos")
            return {}

        forecaster     = ChronosForecaster()
        chronos_preds  = forecaster.forecast_all_stocks(price_data_dict)
        logger.info(f"Step 5 complete: {len(chronos_preds)} Chronos forecasts")
        return chronos_preds

    except Exception as e:
        logger.warning(f"Step 5 FAILED (non-fatal): {e}")
        return {}


def _step6_combine_signals(lgbm_preds: list, chronos_preds: dict, regime: str) -> list:
    """Step 6: Combine ML signals using 60/30/10 ensemble weights."""
    try:
        from ml.signal_combiner import combine_signals
        logger.info("Step 6: Combining ML signals (ensemble)...")

        ml_signals = []
        for pred in lgbm_preds:
            ticker       = pred.get("ticker", "")
            chronos_pred = chronos_preds.get(ticker, {})
            combined     = combine_signals(pred, chronos_pred, regime)
            ml_signals.append(combined)

        logger.info(f"Step 6 complete: {len(ml_signals)} combined signals")
        return ml_signals

    except Exception as e:
        logger.error(f"Step 6 FAILED: {e}")
        return lgbm_preds  # Fallback to raw LGBM predictions


def _step7_run_agents(ml_signals: list) -> dict:
    """Step 7: Run LangGraph agent pipeline with ML signals."""
    try:
        from agents.graph import run_pipeline
        logger.info("Step 7: Running LangGraph agent pipeline...")
        result = run_pipeline(run_type="eod_full", ml_predictions=ml_signals)
        n_signals = len(result.get("final_signals", []))
        logger.info(f"Step 7 complete: {n_signals} final signals generated")
        return result
    except Exception as e:
        logger.error(f"Step 7 FAILED: {e}")
        return {}


# ── Main EOD Pipeline ─────────────────────────────────────────────────────────

def run_eod_pipeline() -> dict:
    """
    Full End-of-Day pipeline. Run at 3:45 PM IST after market close.

    Returns:
        Final state dict from agent pipeline (or empty dict on fatal failure)
    """
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"=== EOD Pipeline Started: {start_time.isoformat()} ===")
    logger.info("=" * 60)

    from config.settings import SUPABASE_URL, SUPABASE_KEY
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("=" * 60)
        logger.error("CRITICAL WARNING: SUPABASE CREDENTIALS MISSING IN ENVIRONMENT!")
        logger.error("The pipeline will run and send emails, but data WILL NOT be saved to the cloud.")
        logger.error("Please add SUPABASE_URL and SUPABASE_KEY to GitHub Repository Secrets.")
        logger.error("=" * 60)

    try:
        _step1_update_price_data()
        _step2_engineer_features()
        current_regime = _step3_get_regime()
        lgbm_preds     = _step4_lgbm_predictions(current_regime)
        chronos_preds  = _step5_chronos_forecasts()
        ml_signals     = _step6_combine_signals(lgbm_preds, chronos_preds, current_regime)
        result         = _step7_run_agents(ml_signals)

        elapsed = (datetime.now(timezone.utc) - start_time).seconds
        n_final = len(result.get("final_signals", []))
        logger.info("=" * 60)
        logger.info(
            f"=== EOD Pipeline Complete: {n_final} signals in {elapsed}s ==="
        )
        logger.info("=" * 60)

        # ── Step 8: Send email alert ─────────────────────────────────────────
        try:
            import pandas as pd
            signals = result.get("final_signals", [])
            if signals:
                df_signals = pd.DataFrame([
                    {
                        "ticker":               s.get("ticker"),
                        "predicted_direction":  s.get("final_direction"),
                        "final_confidence":     s.get("final_confidence"),
                        "signal_strength":      s.get("signal_strength"),
                        "alert_text":           s.get("alert_text", ""),
                    }
                    for s in signals
                ])
                logger.info("Step 8: Sending email alert...")
                send_email_alert(df_signals)
            else:
                logger.info("Step 8: No signals to email — sending empty report...")
                send_email_alert(None)
        except Exception as e:
            logger.error(f"Step 8 (email) FAILED: {e}")

        return result

    except Exception as e:
        elapsed = (datetime.now(timezone.utc) - start_time).seconds
        logger.error(f"=== EOD Pipeline FAILED after {elapsed}s: {e} ===")
        return {}


# ── Monthly Retraining ────────────────────────────────────────────────────────

def run_monthly_retrain() -> None:
    """
    Monthly model retraining — runs on 1st of every month at 8 PM IST.
    Retrains regime detector and ensemble ML models on fresh data.
    """
    logger.info("=" * 60)
    logger.info("=== Monthly Retraining Started ===")
    logger.info("=" * 60)

    try:
        from ml.predictor import train_all_models
        from ml.regime_detector import fit_and_save_all_regime_models

        logger.info("Retraining regime detector (HMM)...")
        fit_and_save_all_regime_models()

        logger.info("Retraining ensemble models (optimize=False for speed)...")
        train_all_models(optimize=False)

        logger.info("=== Monthly Retraining Complete ===")

    except Exception as e:
        logger.error(f"=== Monthly Retraining FAILED: {e} ===")


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m pipeline.eod_pipeline
    logger.info("MarketPulse AI -- EOD Pipeline Module")
    logger.info("This runs the full 7-step EOD pipeline.")
    logger.info("Importing dependencies check...")

    # Lightweight import check (no actual execution)
    checks = [
        ("ml.data_collector",     "update_all_stocks_daily"),
        ("ml.feature_engineering","engineer_all_stocks"),
        ("ml.regime_detector",    "MarketRegimeDetector"),
        ("ml.predictor",          "predict_all_stocks"),
        ("ml.chronos_forecaster", "ChronosForecaster"),
        ("ml.signal_combiner",    "combine_signals"),
        ("agents.graph",          "run_pipeline"),
    ]

    all_ok = True
    for module, attr in checks:
        try:
            mod = __import__(module, fromlist=[attr])
            getattr(mod, attr)
            logger.info(f"  ✅ {module}.{attr}")
        except Exception as e:
            logger.warning(f"  ❌ {module}.{attr}: {e}")
            all_ok = False

    if all_ok:
        logger.info("All imports OK — Starting EOD pipeline execution...")
        run_eod_pipeline()
    else:
        logger.warning("Some imports failed — check dependencies above before running.")
