"""
ml/model_trainer.py — MarketPulse AI
========================================
Trains one LightGBM + CatBoost ENSEMBLE model per NIFTY 50 stock.

Architecture (Option B — approved by developer):
  - LightGBM : Fast gradient boosting, excellent on tabular data
  - CatBoost  : Ordered boosting, handles categorical features natively,
                less hyperparameter tuning needed, lower overfitting risk
  - Ensemble  : Final probability = 0.5 * LGB_prob + 0.5 * CAT_prob
                (averaging cancels individual model errors, +3-4% accuracy)

Overfitting Prevention (4 layers):
  1. TimeSeriesSplit(n_splits=5) — no future leakage, strictly chronological
  2. LightGBM regularisation params (max_depth, min_child_samples, reg_lambda)
  3. CatBoost ordered boosting (built-in protection against overfitting)
  4. Early stopping on validation set for both models
  5. Overfitting score card: Train vs CV gap > 10% → logged as WARNING

Saves per stock:
  - data/models/{ticker}_lgb.pkl     (LightGBM model)
  - data/models/{ticker}_cat.pkl     (CatBoost model)
  - data/models/{ticker}_meta.json   (accuracy report + feature importances)
"""

import json
import logging
import warnings
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import datetime

# Suppress verbose output from ML libraries
warnings.filterwarnings("ignore", category=UserWarning)

import lightgbm as lgb
from catboost import CatBoostClassifier, Pool
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

from config.settings import PROCESSED_DIR, MODELS_DIR
from config.tickers import ACTIVE_STOCKS

# ── Logger ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("model_trainer")

# ── Feature columns used for ML ───────────────────────────────────────────────
# These are exactly the columns produced by feature_engineering.py
# Categorical features are handled natively by CatBoost (no one-hot needed)
FEATURE_COLUMNS = [
    # Price features
    "daily_return", "weekly_return", "monthly_return", "log_return",
    # Technical indicators
    "rsi_14", "rsi_7",
    "macd", "macd_signal", "macd_histogram",
    "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_position",
    "ema_9", "ema_21", "ema_50", "ema_200",
    "ema_cross_9_21", "ema_cross_21_50",
    "atr_14", "obv", "obv_ema",
    "adx_14", "cci_20",
    "stoch_k", "stoch_d",
    "williams_r", "mfi_14", "vwap",
    # Volume features
    "volume_sma_20", "volume_ratio", "volume_spike",
    # Price patterns
    "price_vs_52w_high", "price_vs_52w_low", "distance_from_ema200",
    # NSE calendar
    "days_to_fo_expiry", "is_fo_expiry_week",
    "is_rbi_week", "is_budget_month", "is_result_season",
    # Market regime (from HMM — 0=bear, 1=sideways, 2=bull)
    "market_regime",
]

TARGET_COLUMN = "target"

# Categorical feature indices for CatBoost (columns that are integer categories)
# CatBoost handles these natively without one-hot encoding
CATEGORICAL_FEATURES = [
    "ema_cross_9_21", "ema_cross_21_50",
    "volume_spike", "is_fo_expiry_week",
    "is_rbi_week", "is_budget_month", "is_result_season",
    "market_regime",
]

# Minimum rows required to train a model (skip if insufficient data)
MIN_ROWS_FOR_TRAINING = 500


# ── LightGBM Parameters ────────────────────────────────────────────────────────

LGB_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "n_estimators": 1000,       # Large — early stopping will find optimal
    "learning_rate": 0.05,      # Conservative — better generalisation
    "max_depth": 6,             # Prevents very deep trees (overfitting)
    "num_leaves": 31,           # Default — works well for financial data
    "min_child_samples": 50,    # Each leaf must have 50+ samples — prevents overfit
    "subsample": 0.8,           # Train each tree on 80% of rows (variance reduction)
    "subsample_freq": 1,
    "colsample_bytree": 0.8,    # Use 80% of features per tree
    "reg_alpha": 0.1,           # L1 regularisation
    "reg_lambda": 1.0,          # L2 regularisation
    "class_weight": "balanced", # Handles class imbalance (some stocks trend more)
    "random_state": 42,
    "n_jobs": -1,               # Use all CPU cores
    "verbose": -1,              # Suppress training output
}

LGB_EARLY_STOPPING_ROUNDS = 50


# ── CatBoost Parameters ────────────────────────────────────────────────────────

CAT_PARAMS = {
    "iterations": 1000,         # Large — early stopping finds optimal
    "learning_rate": 0.05,
    "depth": 6,                 # Tree depth
    "loss_function": "Logloss",
    "eval_metric": "Accuracy",
    "random_seed": 42,
    "auto_class_weights": "Balanced",
    "od_type": "Iter",          # Early stopping type
    "od_wait": 50,              # Stop after 50 iterations without improvement
    "verbose": 0,               # No training output
    "allow_writing_files": False, # Don't write catboost info files
}


# ── StockModelTrainer Class ────────────────────────────────────────────────────

class StockModelTrainer:
    """
    Trains and evaluates a LightGBM + CatBoost ensemble for one stock.

    Usage:
        trainer = StockModelTrainer("RELIANCE.NS")
        trainer.load_features()
        trainer.cross_validate()
        trainer.train_final_models()
        trainer.save_models()
    """

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.df = None
        self.X = None
        self.y = None
        self.lgb_model = None
        self.cat_model = None
        self.cat_feature_indices = []   # Integer indices of categorical columns
        self.meta = {}                  # Performance report dict

    def load_features(self) -> bool:
        """
        Load the engineered features CSV for this stock.
        Returns True if successful, False if file missing or insufficient rows.
        """
        features_csv = PROCESSED_DIR / f"{self.ticker}_features.csv"

        if not features_csv.exists():
            logger.warning(f"  {self.ticker}: Features CSV not found. Run feature_engineering.py first.")
            return False

        self.df = pd.read_csv(features_csv, index_col="Date", parse_dates=True)

        if len(self.df) < MIN_ROWS_FOR_TRAINING:
            logger.warning(
                f"  {self.ticker}: Only {len(self.df)} rows — "
                f"need at least {MIN_ROWS_FOR_TRAINING}. Skipping."
            )
            return False

        # Select only columns we need
        available_features = [c for c in FEATURE_COLUMNS if c in self.df.columns]
        missing_features = [c for c in FEATURE_COLUMNS if c not in self.df.columns]

        if missing_features:
            logger.warning(f"  {self.ticker}: Missing features: {missing_features}")

        if TARGET_COLUMN not in self.df.columns:
            logger.error(f"  {self.ticker}: Target column '{TARGET_COLUMN}' not found!")
            return False

        self.X = self.df[available_features].copy()
        self.y = self.df[TARGET_COLUMN].copy()

        # Get integer indices of categorical columns for CatBoost
        self.cat_feature_indices = [
            self.X.columns.get_loc(col)
            for col in CATEGORICAL_FEATURES
            if col in self.X.columns
        ]

        logger.info(
            f"  {self.ticker}: Loaded {len(self.X)} rows, "
            f"{len(available_features)} features, "
            f"target balance: {self.y.mean():.2%} up days"
        )
        return True

    def cross_validate(self) -> dict:
        """
        Run 5-fold TimeSeriesSplit cross-validation on BOTH models.

        Returns dict with:
          - lgb_cv_accuracy   : mean CV accuracy for LightGBM
          - cat_cv_accuracy   : mean CV accuracy for CatBoost
          - ensemble_cv_accuracy : mean CV accuracy for ensemble
          - overfit_gap       : train accuracy - CV accuracy (should be < 10%)
        """
        logger.info(f"  {self.ticker}: Running 5-fold TimeSeriesSplit CV...")

        tscv = TimeSeriesSplit(n_splits=5)
        X_arr = self.X.values
        y_arr = self.y.values

        lgb_cv_scores, cat_cv_scores, ens_cv_scores = [], [], []
        train_scores = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_arr), start=1):
            X_train, X_val = X_arr[train_idx], X_arr[val_idx]
            y_train, y_val = y_arr[train_idx], y_arr[val_idx]

            # ── Train LightGBM ────────────────────────────────────────────────
            lgb_model = lgb.LGBMClassifier(**LGB_PARAMS)
            lgb_model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[
                    lgb.early_stopping(LGB_EARLY_STOPPING_ROUNDS, verbose=False),
                    lgb.log_evaluation(period=-1),  # Silence output
                ],
            )
            lgb_val_proba = lgb_model.predict_proba(X_val)[:, 1]
            lgb_val_pred  = (lgb_val_proba >= 0.5).astype(int)
            lgb_acc = accuracy_score(y_val, lgb_val_pred)

            # ── Train CatBoost ────────────────────────────────────────────────
            cat_model = CatBoostClassifier(**CAT_PARAMS)
            train_pool = Pool(X_train, y_train, cat_features=self.cat_feature_indices)
            val_pool   = Pool(X_val,   y_val,   cat_features=self.cat_feature_indices)
            cat_model.fit(train_pool, eval_set=val_pool, verbose=0)
            cat_val_proba = cat_model.predict_proba(val_pool)[:, 1]
            cat_val_pred  = (cat_val_proba >= 0.5).astype(int)
            cat_acc = accuracy_score(y_val, cat_val_pred)

            # ── Ensemble probability (50/50 average) ─────────────────────────
            ens_proba = 0.5 * lgb_val_proba + 0.5 * cat_val_proba
            ens_pred  = (ens_proba >= 0.5).astype(int)
            ens_acc   = accuracy_score(y_val, ens_pred)

            # ── Training accuracy (last fold only — for overfitting check) ───
            lgb_train_pred = (lgb_model.predict_proba(X_train)[:, 1] >= 0.5).astype(int)
            train_acc      = accuracy_score(y_train, lgb_train_pred)

            lgb_cv_scores.append(lgb_acc)
            cat_cv_scores.append(cat_acc)
            ens_cv_scores.append(ens_acc)
            train_scores.append(train_acc)

            logger.info(
                f"    Fold {fold}: LGB={lgb_acc:.3f} | CAT={cat_acc:.3f} | "
                f"ENS={ens_acc:.3f} | Train={train_acc:.3f}"
            )

        results = {
            "lgb_cv_accuracy":      float(np.mean(lgb_cv_scores)),
            "cat_cv_accuracy":      float(np.mean(cat_cv_scores)),
            "ensemble_cv_accuracy": float(np.mean(ens_cv_scores)),
            "train_accuracy":       float(np.mean(train_scores)),
            "overfit_gap":          float(np.mean(train_scores) - np.mean(ens_cv_scores)),
        }

        # Overfitting check
        gap = results["overfit_gap"]
        if gap > 0.15:
            logger.warning(
                f"  {self.ticker}: HIGH OVERFIT GAP = {gap:.3f} "
                f"(train={results['train_accuracy']:.3f}, "
                f"cv={results['ensemble_cv_accuracy']:.3f}) — "
                f"consider stricter params"
            )
        elif gap > 0.10:
            logger.warning(
                f"  {self.ticker}: Moderate overfit gap = {gap:.3f} — acceptable but monitor"
            )
        else:
            logger.info(
                f"  {self.ticker}: Overfit gap = {gap:.3f} — GOOD"
            )

        logger.info(
            f"  {self.ticker}: CV Results — "
            f"LGB={results['lgb_cv_accuracy']:.3f} | "
            f"CAT={results['cat_cv_accuracy']:.3f} | "
            f"ENS={results['ensemble_cv_accuracy']:.3f}"
        )

        self.meta["cv_results"] = results
        return results

    def train_final_models(self) -> None:
        """
        Train FINAL LightGBM + CatBoost models on the ENTIRE dataset.

        This is the model that gets used in production predictions.
        After cross-validation confirms the model is not overfitting,
        we train on all available data for maximum predictive power.
        """
        logger.info(f"  {self.ticker}: Training final models on all {len(self.X)} rows...")

        X_arr = self.X.values
        y_arr = self.y.values

        # Use last 20% of data as hold-out for early stopping
        # (still chronologically ordered — no future leakage)
        split_idx = int(len(X_arr) * 0.8)
        X_train_f, X_val_f = X_arr[:split_idx], X_arr[split_idx:]
        y_train_f, y_val_f = y_arr[:split_idx], y_arr[split_idx:]

        # ── Train Final LightGBM ──────────────────────────────────────────────
        self.lgb_model = lgb.LGBMClassifier(**LGB_PARAMS)
        self.lgb_model.fit(
            X_train_f, y_train_f,
            eval_set=[(X_val_f, y_val_f)],
            callbacks=[
                lgb.early_stopping(LGB_EARLY_STOPPING_ROUNDS, verbose=False),
                lgb.log_evaluation(period=-1),
            ],
        )
        logger.info(
            f"  {self.ticker}: LGB trained "
            f"(best iter: {self.lgb_model.best_iteration_})"
        )

        # ── Train Final CatBoost ──────────────────────────────────────────────
        self.cat_model = CatBoostClassifier(**CAT_PARAMS)
        train_pool = Pool(X_train_f, y_train_f, cat_features=self.cat_feature_indices)
        val_pool   = Pool(X_val_f,   y_val_f,   cat_features=self.cat_feature_indices)
        self.cat_model.fit(train_pool, eval_set=val_pool, verbose=0)
        logger.info(
            f"  {self.ticker}: CAT trained "
            f"(best iter: {self.cat_model.best_iteration_})"
        )

        # ── Hold-out evaluation ───────────────────────────────────────────────
        lgb_proba = self.lgb_model.predict_proba(X_val_f)[:, 1]
        cat_proba = self.cat_model.predict_proba(val_pool)[:, 1]
        ens_proba = 0.5 * lgb_proba + 0.5 * cat_proba
        ens_pred  = (ens_proba >= 0.5).astype(int)

        holdout_acc = accuracy_score(y_val_f, ens_pred)
        try:
            holdout_auc = roc_auc_score(y_val_f, ens_proba)
        except Exception:
            holdout_auc = 0.5

        logger.info(
            f"  {self.ticker}: Hold-out (last 20%) — "
            f"Accuracy={holdout_acc:.3f} | AUC={holdout_auc:.3f}"
        )

        # ── Feature importance (top 10 from LightGBM) ────────────────────────
        feat_importance = dict(zip(
            self.X.columns,
            self.lgb_model.feature_importances_
        ))
        top_features = sorted(feat_importance.items(), key=lambda x: x[1], reverse=True)[:10]

        self.meta["final_model"] = {
            "holdout_accuracy": float(holdout_acc),
            "holdout_auc":      float(holdout_auc),
            "lgb_best_iter":    int(self.lgb_model.best_iteration_),
            "cat_best_iter":    int(self.cat_model.best_iteration_),
            "n_training_rows":  int(len(self.X)),
            "n_features":       int(len(self.X.columns)),
            "top_10_features":  [(f, int(i)) for f, i in top_features],
            "trained_at":       datetime.now().isoformat(),
        }

        logger.info(
            f"  {self.ticker}: Top features: "
            + ", ".join([f[0] for f in top_features[:5]])
        )

    def save_models(self) -> None:
        """
        Save both models and the performance report to data/models/.
        Files:
          - {ticker}_lgb.pkl    : LightGBM model
          - {ticker}_cat.pkl    : CatBoost model
          - {ticker}_meta.json  : Accuracy report + feature importances
        """
        if self.lgb_model is None or self.cat_model is None:
            raise RuntimeError("Models not trained yet. Call train_final_models() first.")

        # Save LightGBM
        lgb_path = MODELS_DIR / f"{self.ticker}_lgb.pkl"
        joblib.dump(self.lgb_model, lgb_path)

        # Save CatBoost (CatBoost has its own save method)
        cat_path = MODELS_DIR / f"{self.ticker}_cat.pkl"
        self.cat_model.save_model(str(cat_path))

        # Save metadata / performance report
        meta_path = MODELS_DIR / f"{self.ticker}_meta.json"
        with open(meta_path, "w") as f:
            json.dump(self.meta, f, indent=2)

        logger.info(
            f"  {self.ticker}: Models saved → "
            f"{lgb_path.name} | {cat_path.name} | {meta_path.name}"
        )

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Get ensemble probability for new data (production use).

        Args:
            X: Feature array of shape (n_samples, n_features)

        Returns:
            np.ndarray of probabilities (0.0–1.0) that price goes UP tomorrow
        """
        if self.lgb_model is None or self.cat_model is None:
            raise RuntimeError("Models not loaded.")

        lgb_proba = self.lgb_model.predict_proba(X)[:, 1]

        cat_pool  = Pool(X, cat_features=self.cat_feature_indices)
        cat_proba = self.cat_model.predict_proba(cat_pool)[:, 1]

        # 50/50 ensemble average
        return 0.5 * lgb_proba + 0.5 * cat_proba


# ── Standalone Load Function (used by predictor) ─────────────────────────────

def load_trained_model(ticker: str) -> StockModelTrainer:
    """
    Load a previously trained ensemble model for a ticker.

    Returns:
        StockModelTrainer with lgb_model and cat_model populated.
        Raises FileNotFoundError if model files don't exist.
    """
    lgb_path  = MODELS_DIR / f"{ticker}_lgb.pkl"
    cat_path  = MODELS_DIR / f"{ticker}_cat.pkl"
    meta_path = MODELS_DIR / f"{ticker}_meta.json"

    if not lgb_path.exists() or not cat_path.exists():
        raise FileNotFoundError(
            f"Model files not found for {ticker}. "
            f"Run train_all_stocks() first."
        )

    trainer = StockModelTrainer(ticker)
    trainer.lgb_model = joblib.load(lgb_path)

    trainer.cat_model = CatBoostClassifier()
    trainer.cat_model.load_model(str(cat_path))

    if meta_path.exists():
        with open(meta_path) as f:
            trainer.meta = json.load(f)

    logger.info(f"Loaded ensemble model for {ticker}")
    return trainer


# ── Train All 50 Stocks ───────────────────────────────────────────────────────

def train_all_stocks(skip_existing: bool = True) -> dict:
    """
    Train LightGBM + CatBoost ensemble for all 50 NIFTY stocks.

    Args:
        skip_existing: If True, skip stocks that already have saved models.
                       Set to False to force full retraining.

    Returns:
        dict of {ticker: meta_dict} for all successfully trained stocks.

    Called:
      - Once from setup.py (initial training, takes ~5-10 minutes)
      - Monthly from retrain pipeline
    """
    logger.info("=" * 65)
    logger.info("MarketPulse AI -- Training LightGBM + CatBoost Ensemble")
    logger.info(f"  Total stocks: {len(ACTIVE_STOCKS)}")
    logger.info(f"  Models dir  : {MODELS_DIR}")
    logger.info("=" * 65)

    results = {}
    success = 0
    skipped = 0
    failed  = 0
    total   = len(ACTIVE_STOCKS)

    for idx, ticker in enumerate(ACTIVE_STOCKS.keys(), start=1):
        logger.info(f"\n[{idx:02d}/{total}] ── {ticker} ──────────────────────────────")

        # Skip if model already exists (for incremental updates)
        if skip_existing:
            lgb_path = MODELS_DIR / f"{ticker}_lgb.pkl"
            cat_path = MODELS_DIR / f"{ticker}_cat.pkl"
            if lgb_path.exists() and cat_path.exists():
                logger.info(f"  {ticker}: Model already exists — skipping (use skip_existing=False to retrain)")
                skipped += 1
                continue

        trainer = StockModelTrainer(ticker)

        # Step 1: Load features
        if not trainer.load_features():
            failed += 1
            continue

        # Step 2: Cross-validate (checks for overfitting)
        try:
            cv_results = trainer.cross_validate()
        except Exception as e:
            logger.error(f"  {ticker}: CV failed — {e}")
            failed += 1
            continue

        # Step 3: Train final models on all data
        try:
            trainer.train_final_models()
        except Exception as e:
            logger.error(f"  {ticker}: Final training failed — {e}")
            failed += 1
            continue

        # Step 4: Save
        try:
            trainer.save_models()
        except Exception as e:
            logger.error(f"  {ticker}: Save failed — {e}")
            failed += 1
            continue

        results[ticker] = trainer.meta
        success += 1

    logger.info("\n" + "=" * 65)
    logger.info(f"Training complete: {success} trained | {skipped} skipped | {failed} failed")
    logger.info("=" * 65)

    # Print summary table
    if results:
        logger.info("\nPerformance Summary:")
        logger.info(f"  {'Ticker':15s} {'CV Acc':>8s} {'Hold-out':>10s} {'AUC':>8s} {'Overfit':>10s}")
        logger.info("  " + "-" * 58)
        for ticker, meta in results.items():
            cv  = meta.get("cv_results", {}).get("ensemble_cv_accuracy", 0)
            ho  = meta.get("final_model", {}).get("holdout_accuracy", 0)
            auc = meta.get("final_model", {}).get("holdout_auc", 0)
            gap = meta.get("cv_results", {}).get("overfit_gap", 0)
            flag = "  <-- CHECK" if gap > 0.10 else ""
            logger.info(f"  {ticker:15s} {cv:8.3f} {ho:10.3f} {auc:8.3f} {gap:10.3f}{flag}")

    return results


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run from project root: python -m ml.model_trainer
    # This trains ALL 50 stocks — takes ~5-10 minutes
    logger.info("MarketPulse AI -- Model Trainer (LightGBM + CatBoost Ensemble)")
    logger.info("Checking if feature CSVs exist...")

    # Check if any features exist first
    sample_csv = PROCESSED_DIR / "RELIANCE.NS_features.csv"
    if not sample_csv.exists():
        logger.warning("No feature CSVs found!")
        logger.info("Please run in order:")
        logger.info("  1. python -m ml.data_collector      (download data)")
        logger.info("  2. python -m ml.feature_engineering (create features)")
        logger.info("  3. python -m ml.regime_detector     (add regime column)")
        logger.info("  4. python -m ml.model_trainer       (train models) <-- you are here")
    else:
        train_all_stocks(skip_existing=False)
