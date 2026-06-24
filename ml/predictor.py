"""
ml/predictor.py — MarketPulse AI
===================================
Blueprint Part 7: Core ML prediction engine.

- StockPredictor class: train LightGBM per stock, predict, SHAP explain
- Optuna hyperparameter tuning (50 trials, optional)
- predict_all_stocks(): daily EOD pipeline prediction for all 50 stocks
- train_all_models(): one-time / monthly training run

Architecture note:
  model_trainer.py  → trains LightGBM + CatBoost ENSEMBLE (approved upgrade)
  predictor.py      → Blueprint-specified predictor with SHAP + Optuna + pipeline API
                      Uses ensemble from model_trainer when models exist,
                      falls back to standalone LightGBM if not.
"""

import json
import logging
import warnings
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore", category=UserWarning)

import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, roc_auc_score

import shap
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)  # Silence optuna noise

from config.settings import PROCESSED_DIR, MODELS_DIR, CONFIDENCE_THRESHOLD
from config.tickers import ACTIVE_STOCKS

# ── Logger ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("predictor")

# ── Feature columns (same as model_trainer.py) ────────────────────────────────
FEATURE_COLUMNS = [
    "daily_return", "weekly_return", "monthly_return", "log_return",
    "rsi_14", "rsi_7",
    "macd", "macd_signal", "macd_histogram",
    "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_position",
    "ema_9", "ema_21", "ema_50", "ema_200",
    "ema_cross_9_21", "ema_cross_21_50",
    "atr_14", "obv", "obv_ema",
    "adx_14", "cci_20",
    "stoch_k", "stoch_d",
    "williams_r", "mfi_14", "vwap",
    "volume_sma_20", "volume_ratio", "volume_spike",
    "price_vs_52w_high", "price_vs_52w_low", "distance_from_ema200",
    "days_to_fo_expiry", "is_fo_expiry_week",
    "is_rbi_week", "is_budget_month", "is_result_season",
    "market_regime",
]

TARGET_COLUMN = "target"
MIN_ROWS = 500

# Default LightGBM params (used when Optuna is not run)
DEFAULT_LGB_PARAMS = {
    "num_leaves": 63,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "min_child_samples": 20,
    "objective": "binary",
    "metric": "binary_logloss",
    "class_weight": "balanced",
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}


# ── StockPredictor Class ───────────────────────────────────────────────────────

class StockPredictor:
    """
    LightGBM predictor for one NIFTY 50 stock.

    Provides:
      - train()             : TimeSeriesSplit CV + optional Optuna tuning
      - predict()           : probability_up, direction, confidence, signal_strength
      - explain_prediction(): SHAP-based feature attribution (top N reasons)
    """

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.model = None
        self.feature_columns = FEATURE_COLUMNS
        self.model_path = MODELS_DIR / f"{ticker}_lgb_predictor.pkl"
        self.best_params = DEFAULT_LGB_PARAMS.copy()

    # ── Train ──────────────────────────────────────────────────────────────────

    def train(self, df: pd.DataFrame, optimize_hyperparams: bool = False) -> dict:
        """
        Train LightGBM using TimeSeriesSplit(n_splits=5).
        Optionally run Optuna for 50 trials to find best hyperparameters.

        Args:
            df                 : Feature-engineered DataFrame
            optimize_hyperparams: Run Optuna tuning (slow but better accuracy)

        Returns:
            dict: {accuracy, auc, n_samples, ticker, trained_at}
        """
        # ── Prepare data ─────────────────────────────────────────────────────
        available_features = [c for c in self.feature_columns if c in df.columns]
        X = df[available_features].values
        y = df[TARGET_COLUMN].values

        if len(X) < MIN_ROWS:
            raise ValueError(f"{self.ticker}: Only {len(X)} rows, need {MIN_ROWS}+")

        logger.info(f"  {self.ticker}: Training on {len(X)} rows, {len(available_features)} features")

        # ── Optional: Optuna Hyperparameter Optimization ──────────────────────
        if optimize_hyperparams:
            logger.info(f"  {self.ticker}: Running Optuna (50 trials)...")
            self.best_params = self._run_optuna(X, y, n_trials=50)
            logger.info(f"  {self.ticker}: Optuna best params: {self.best_params}")

        # ── TimeSeriesSplit Cross-Validation ──────────────────────────────────
        tscv = TimeSeriesSplit(n_splits=5)
        oof_preds   = np.zeros(len(X))
        oof_proba   = np.zeros(len(X))
        train_accs  = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X), start=1):
            X_tr, X_val = X[train_idx], X[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]

            model = lgb.LGBMClassifier(**self.best_params)
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                callbacks=[
                    lgb.early_stopping(50, verbose=False),
                    lgb.log_evaluation(period=-1),
                ],
            )

            fold_proba = model.predict_proba(X_val)[:, 1]
            fold_pred  = (fold_proba >= 0.5).astype(int)
            oof_proba[val_idx]  = fold_proba
            oof_preds[val_idx]  = fold_pred
            train_accs.append(accuracy_score(y_tr, (model.predict_proba(X_tr)[:, 1] >= 0.5).astype(int)))

            logger.info(
                f"    Fold {fold}: acc={accuracy_score(y_val, fold_pred):.3f} "
                f"| auc={roc_auc_score(y_val, fold_proba):.3f}"
            )

        # ── OOF Metrics ───────────────────────────────────────────────────────
        # Only evaluate on indices that were in the validation set
        val_mask = oof_proba > 0  # avoids first fold's zeros
        cv_accuracy = float(accuracy_score(y[val_mask], oof_preds[val_mask]))
        try:
            cv_auc = float(roc_auc_score(y[val_mask], oof_proba[val_mask]))
        except Exception:
            cv_auc = 0.5

        train_accuracy = float(np.mean(train_accs))
        overfit_gap    = train_accuracy - cv_accuracy

        if overfit_gap > 0.15:
            logger.warning(f"  {self.ticker}: HIGH overfit gap {overfit_gap:.3f} — train={train_accuracy:.3f} cv={cv_accuracy:.3f}")
        elif overfit_gap > 0.10:
            logger.warning(f"  {self.ticker}: Moderate overfit gap {overfit_gap:.3f}")
        else:
            logger.info(f"  {self.ticker}: Overfit gap {overfit_gap:.3f} — OK")

        # ── Train Final Model on ALL Data ─────────────────────────────────────
        split_idx = int(len(X) * 0.8)
        self.model = lgb.LGBMClassifier(**self.best_params)
        self.model.fit(
            X[:split_idx], y[:split_idx],
            eval_set=[(X[split_idx:], y[split_idx:])],
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(period=-1),
            ],
        )

        joblib.dump({
            "model": self.model,
            "feature_columns": available_features,
            "best_params": self.best_params,
        }, self.model_path)
        logger.info(f"  {self.ticker}: Model saved → {self.model_path.name}")

        result = {
            "ticker":         self.ticker,
            "accuracy":       cv_accuracy,
            "auc":            cv_auc,
            "train_accuracy": train_accuracy,
            "overfit_gap":    overfit_gap,
            "n_samples":      int(len(X)),
            "n_features":     int(len(available_features)),
            "trained_at":     datetime.now().isoformat(),
        }

        logger.info(
            f"  {self.ticker}: CV Accuracy={cv_accuracy:.3f} | AUC={cv_auc:.3f} | Gap={overfit_gap:.3f}"
        )
        return result

    def _run_optuna(self, X: np.ndarray, y: np.ndarray, n_trials: int = 50) -> dict:
        """
        Optuna hyperparameter search over 50 trials.
        Uses 3-fold TimeSeriesSplit (faster than 5-fold for tuning).
        """
        tscv = TimeSeriesSplit(n_splits=3)

        def objective(trial):
            params = {
                "num_leaves":        trial.suggest_int("num_leaves", 20, 300),
                "learning_rate":     trial.suggest_float("learning_rate", 0.001, 0.3, log=True),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "feature_fraction":  trial.suggest_float("feature_fraction", 0.5, 1.0),
                "bagging_fraction":  trial.suggest_float("bagging_fraction", 0.5, 1.0),
                "bagging_freq":      1,
                "max_depth":         trial.suggest_int("max_depth", 3, 12),
                "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 2.0),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.0, 2.0),
                "n_estimators":      500,
                "objective":         "binary",
                "metric":            "binary_logloss",
                "class_weight":      "balanced",
                "random_state":      42,
                "n_jobs":            -1,
                "verbose":           -1,
            }
            fold_scores = []
            for train_idx, val_idx in tscv.split(X):
                model = lgb.LGBMClassifier(**params)
                model.fit(
                    X[train_idx], y[train_idx],
                    eval_set=[(X[val_idx], y[val_idx])],
                    callbacks=[
                        lgb.early_stopping(30, verbose=False),
                        lgb.log_evaluation(period=-1),
                    ],
                )
                proba = model.predict_proba(X[val_idx])[:, 1]
                fold_scores.append(roc_auc_score(y[val_idx], proba))
            return float(np.mean(fold_scores))

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        best = study.best_params.copy()
        best.update({
            "objective":    "binary",
            "metric":       "binary_logloss",
            "class_weight": "balanced",
            "random_state": 42,
            "n_jobs":       -1,
            "verbose":      -1,
        })
        return best

    # ── Predict ───────────────────────────────────────────────────────────────

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Predict direction for the LAST ROW of df (today's data).

        Returns:
            dict: {
                ticker, probability_up, probability_down,
                predicted_direction, confidence, signal_strength
            }
        """
        self._load_if_needed()

        available_features = [c for c in self.feature_columns if c in df.columns]
        last_row = df[available_features].iloc[[-1]].values  # Shape (1, n_features)

        proba_up   = float(self.model.predict_proba(last_row)[0, 1])
        proba_down = 1.0 - proba_up

        direction  = "bullish" if proba_up > 0.5 else "bearish"

        # Confidence: how far from 0.5? Scaled to 0–1
        confidence = abs(proba_up - 0.5) * 2

        if confidence > 0.3:
            strength = "strong"
        elif confidence > 0.15:
            strength = "moderate"
        else:
            strength = "weak"

        return {
            "ticker":               self.ticker,
            "probability_up":       round(proba_up, 4),
            "probability_down":     round(proba_down, 4),
            "predicted_direction":  direction,
            "confidence":           round(confidence, 4),
            "signal_strength":      strength,
        }

    # ── Explain (SHAP) ────────────────────────────────────────────────────────

    def explain_prediction(self, df: pd.DataFrame, top_n: int = 5) -> list:
        """
        Use SHAP TreeExplainer to explain WHY the model made this prediction.

        Returns:
            List of top N feature contributions:
            [{"feature_name": ..., "shap_value": ..., "direction": "positive"/"negative"}]
        """
        self._load_if_needed()

        available_features = [c for c in self.feature_columns if c in df.columns]
        last_row = df[available_features].iloc[[-1]]

        try:
            explainer   = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(last_row)

            # For binary classification, shap_values is a list of 2 arrays
            # shap_values[1] = contributions to class 1 (price goes UP)
            if isinstance(shap_values, list):
                sv = shap_values[1][0]
            else:
                sv = shap_values[0]

            # Pair feature names with their SHAP values
            feature_shap = list(zip(available_features, sv))

            # Sort by absolute SHAP value (biggest impact first)
            feature_shap.sort(key=lambda x: abs(x[1]), reverse=True)

            result = []
            for feat, val in feature_shap[:top_n]:
                result.append({
                    "feature_name": feat,
                    "shap_value":   round(float(val), 5),
                    "direction":    "positive" if val > 0 else "negative",
                })

            return result

        except Exception as e:
            logger.warning(f"  {self.ticker}: SHAP explanation failed — {e}")
            return []

    # ── Load model if not in memory ───────────────────────────────────────────

    def _load_if_needed(self) -> None:
        """Load model from disk if not already in memory."""
        if self.model is not None:
            return

        if not self.model_path.exists():
            # Try loading from ensemble trainer (model_trainer.py)
            lgb_path = MODELS_DIR / f"{self.ticker}_lgb.pkl"
            if lgb_path.exists():
                saved = joblib.load(lgb_path)
                self.model = saved if isinstance(saved, lgb.LGBMClassifier) else saved
                logger.info(f"  {self.ticker}: Loaded LGB model from ensemble trainer")
                return
            raise FileNotFoundError(
                f"No model found for {self.ticker}. "
                f"Run train() or train_all_models() first."
            )

        saved = joblib.load(self.model_path)
        self.model = saved["model"]
        self.feature_columns = saved.get("feature_columns", FEATURE_COLUMNS)
        logger.info(f"  {self.ticker}: Loaded predictor model from {self.model_path.name}")


# ── Standalone: Train All 50 Models ───────────────────────────────────────────

def train_all_models(optimize: bool = False) -> None:
    """
    Train one LightGBM StockPredictor per NIFTY 50 stock.

    Args:
        optimize: If True, run Optuna for each stock (~50x slower but better accuracy)

    Prints a final results table on completion.
    """
    logger.info("=" * 65)
    logger.info("MarketPulse AI -- Training All 50 Stock Predictors")
    logger.info(f"  Optuna tuning: {'YES (50 trials per stock)' if optimize else 'NO (using defaults)'}")
    logger.info("=" * 65)

    results = []
    total   = len(ACTIVE_STOCKS)

    for idx, ticker in enumerate(ACTIVE_STOCKS.keys(), start=1):
        logger.info(f"\n[{idx:02d}/{total}] {ticker}")

        parquet_path = PROCESSED_DIR / f"{ticker}_features.parquet"
        if not parquet_path.exists():
            logger.warning(f"  {ticker}: Features parquet not found — skipping")
            results.append({"ticker": ticker, "status": "SKIPPED — no parquet"})
            continue

        try:
            df = pd.read_parquet(parquet_path)
            if "Date" in df.columns:
                df.set_index("Date", inplace=True)
            predictor = StockPredictor(ticker)
            result = predictor.train(df, optimize_hyperparams=optimize)
            result["status"] = "OK"
            results.append(result)
        except Exception as e:
            logger.error(f"  {ticker}: Training failed — {e}")
            results.append({"ticker": ticker, "status": f"FAILED: {e}"})

    # ── Print Summary Table ───────────────────────────────────────────────────
    logger.info("\n" + "=" * 65)
    logger.info("Training Complete — Results Summary")
    logger.info("=" * 65)
    logger.info(f"  {'Ticker':15s} {'CV Acc':>8s} {'AUC':>8s} {'Overfit':>9s} {'N':>6s} {'Status'}")
    logger.info("  " + "-" * 60)

    for r in results:
        if r.get("status") == "OK":
            logger.info(
                f"  {r['ticker']:15s} {r.get('accuracy',0):8.3f} "
                f"{r.get('auc',0):8.3f} {r.get('overfit_gap',0):9.3f} "
                f"{r.get('n_samples',0):6d}  OK"
            )
        else:
            logger.info(f"  {r['ticker']:15s} {'—':>8s} {'—':>8s} {'—':>9s} {'—':>6s}  {r.get('status','?')}")

    ok_count = sum(1 for r in results if r.get("status") == "OK")
    logger.info(f"\n  Trained: {ok_count}/{total} stocks successfully")
    logger.info("=" * 65)


# ── Standalone: Predict All 50 Stocks (used by EOD pipeline) ─────────────────

def predict_all_stocks(current_regime: str = "unknown") -> list:
    """
    Load each stock's trained predictor and run predict() on latest data.
    Used by the EOD pipeline (pipeline/eod_pipeline.py) every day at 3:45 PM IST.

    Returns:
        List of prediction dicts for all 50 stocks.
        Stocks with missing models or data are skipped (logged as warnings).
    """
    logger.info("Running predictions for all NIFTY 50 stocks...")
    predictions = []

    for ticker in ACTIVE_STOCKS.keys():
        parquet_path = PROCESSED_DIR / f"{ticker}_features.parquet"

        if not parquet_path.exists():
            logger.warning(f"  {ticker}: Features parquet not found — skipping")
            continue

        try:
            df = pd.read_parquet(parquet_path)
            if "Date" in df.columns:
                df.set_index("Date", inplace=True)

            if len(df) < 5:
                logger.warning(f"  {ticker}: Too few rows ({len(df)}) — skipping")
                continue

            predictor = StockPredictor(ticker)
            
            # Inject market regime code if missing
            regime_map = {"bear": 0, "sideways": 1, "bull": 2, "unknown": 1}
            if "market_regime" not in df.columns:
                df["market_regime"] = regime_map.get(str(current_regime).lower(), 1)
                
            pred = predictor.predict(df)

            # Only include signals above confidence threshold
            if pred["confidence"] >= CONFIDENCE_THRESHOLD:
                predictions.append(pred)
                logger.info(
                    f"  {ticker}: {pred['predicted_direction'].upper()} "
                    f"(prob_up={pred['probability_up']:.3f}, "
                    f"confidence={pred['confidence']:.3f}, "
                    f"strength={pred['signal_strength']})"
                )
            else:
                logger.info(
                    f"  {ticker}: WEAK signal (confidence={pred['confidence']:.3f} "
                    f"< threshold {CONFIDENCE_THRESHOLD}) — excluded"
                )

        except FileNotFoundError:
            logger.warning(f"  {ticker}: No trained model found — run train_all_models() first")
        except Exception as e:
            logger.error(f"  {ticker}: Prediction failed — {e}")

    logger.info(f"Predictions complete: {len(predictions)} signals above threshold")
    return predictions


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m ml.predictor
    logger.info("MarketPulse AI -- Predictor Module")

    sample_csv = PROCESSED_DIR / "RELIANCE.NS_features.csv"
    if sample_csv.exists():
        logger.info("Feature CSVs found. Running train_all_models()...")
        train_all_models(optimize=False)
    else:
        logger.warning("No feature CSVs found. Run in order:")
        logger.info("  1. python -m ml.data_collector")
        logger.info("  2. python -m ml.feature_engineering")
        logger.info("  3. python -m ml.regime_detector")
        logger.info("  4. python -m ml.predictor  <-- you are here")
        logger.info("Module imports OK.")
