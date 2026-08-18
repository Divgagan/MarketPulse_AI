"""
ml/model_registry.py — MarketPulse AI
========================================
Improvement #1: MLflow Model Versioning

Every training run is now tracked. Each stock gets:
  - A versioned MLflow run with params, CV metrics, holdout metrics
  - Model artifacts saved under a unique run ID
  - The ability to roll back to any previous version

Usage:
    registry = MLflowRegistry()
    with registry.start_run("RELIANCE.NS") as run_id:
        registry.log_params(lgb_params)
        registry.log_metrics({"cv_accuracy": 0.57, "holdout_auc": 0.61})
        registry.log_model(lgb_model, "lgb")

    # Roll back to best model
    registry.rollback_to_best("RELIANCE.NS", metric="holdout_auc")
"""

import logging
import json
import shutil
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("model_registry")

try:
    import mlflow
    import mlflow.sklearn
    import mlflow.lightgbm
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("mlflow not installed — model versioning disabled. Run: pip install mlflow")

import joblib
from config.settings import MODELS_DIR, DATA_DIR

# ── MLflow tracking URI — local filesystem (no server needed) ─────────────────
MLFLOW_DIR = DATA_DIR / "mlflow_runs"
MLFLOW_DIR.mkdir(parents=True, exist_ok=True)
MLFLOW_TRACKING_URI = f"file:///{MLFLOW_DIR.as_posix()}"
MLFLOW_EXPERIMENT_NAME = "MarketPulse-AI-Stock-Models"


class MLflowRegistry:
    """
    Wraps MLflow for per-stock model versioning and tracking.

    Each call to train_all_stocks() creates one MLflow run per stock.
    Every run stores:
      - Parameters (LGB params, CAT params)
      - Metrics (CV accuracy, hold-out AUC, overfit gap)
      - Artifacts (model .pkl files, meta.json)
      - Tags (ticker, trained_at timestamp)
    """

    def __init__(self):
        if MLFLOW_AVAILABLE:
            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            logger.info(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")
        self._active_run_id = None

    @contextmanager
    def start_run(self, ticker: str):
        """
        Context manager — wraps a full training session for one stock.

        Usage:
            with registry.start_run("RELIANCE.NS") as run_id:
                registry.log_params(...)
                registry.log_metrics(...)
        """
        if not MLFLOW_AVAILABLE:
            yield None
            return

        run_name = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.set_tag("ticker", ticker)
            mlflow.set_tag("trained_at", datetime.now().isoformat())
            self._active_run_id = run.info.run_id
            logger.info(f"  {ticker}: MLflow run started → {run.info.run_id[:8]}")
            try:
                yield run.info.run_id
            finally:
                self._active_run_id = None
                logger.info(f"  {ticker}: MLflow run complete → {run.info.run_id[:8]}")

    def log_params(self, params: dict) -> None:
        """Log hyperparameters for this run."""
        if not MLFLOW_AVAILABLE or not mlflow.active_run():
            return
        # MLflow has a param limit — log the most important ones
        safe_params = {
            k: str(v)[:250]
            for k, v in params.items()
            if k in ["max_depth", "learning_rate", "n_estimators",
                     "min_child_samples", "subsample", "reg_alpha", "reg_lambda",
                     "num_leaves", "colsample_bytree"]
        }
        mlflow.log_params(safe_params)

    def log_metrics(self, metrics: dict) -> None:
        """Log performance metrics for this run."""
        if not MLFLOW_AVAILABLE or not mlflow.active_run():
            return
        numeric_metrics = {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
        mlflow.log_metrics(numeric_metrics)

    def log_model_artifact(self, model_path: Path, artifact_name: str) -> None:
        """Log a saved model file as an MLflow artifact."""
        if not MLFLOW_AVAILABLE or not mlflow.active_run():
            return
        if model_path.exists():
            mlflow.log_artifact(str(model_path), artifact_path=artifact_name)

    def log_meta_json(self, meta: dict, ticker: str) -> None:
        """Log the full performance meta dict as a JSON artifact."""
        if not MLFLOW_AVAILABLE or not mlflow.active_run():
            return
        import tempfile, os
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"{ticker}_meta_"
        ) as f:
            json.dump(meta, f, indent=2)
            tmp_path = f.name
        mlflow.log_artifact(tmp_path, artifact_path="meta")
        os.unlink(tmp_path)

    def get_all_runs(self, ticker: str) -> list:
        """
        Return all historical MLflow runs for a given ticker, sorted by date.
        Each run is a dict with: run_id, metrics, params, trained_at
        """
        if not MLFLOW_AVAILABLE:
            return []
        try:
            client = mlflow.tracking.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
            experiment = client.get_experiment_by_name(MLFLOW_EXPERIMENT_NAME)
            if experiment is None:
                return []
            runs = client.search_runs(
                experiment_ids=[experiment.experiment_id],
                filter_string=f"tags.ticker = '{ticker}'",
                order_by=["start_time DESC"],
            )
            return [
                {
                    "run_id":     r.info.run_id,
                    "trained_at": r.data.tags.get("trained_at", ""),
                    "metrics":    r.data.metrics,
                    "params":     r.data.params,
                }
                for r in runs
            ]
        except Exception as e:
            logger.warning(f"Could not fetch runs for {ticker}: {e}")
            return []

    def get_best_run(self, ticker: str, metric: str = "holdout_auc") -> Optional[dict]:
        """
        Return the single best historical run for a ticker by a given metric.

        Args:
            ticker: Stock ticker (e.g. "RELIANCE.NS")
            metric: Metric name to rank by (default: "holdout_auc")

        Returns:
            dict with run info, or None if no runs exist
        """
        runs = self.get_all_runs(ticker)
        if not runs:
            return None
        valid = [r for r in runs if metric in r["metrics"]]
        if not valid:
            return None
        return max(valid, key=lambda r: r["metrics"][metric])

    def rollback_to_best(self, ticker: str, metric: str = "holdout_auc") -> bool:
        """
        Restore the best historical model version for a ticker.

        This downloads the model artifacts from MLflow and overwrites the
        current model files in MODELS_DIR, effectively rolling back.

        Returns:
            True if rollback succeeded, False if no historical runs found.
        """
        if not MLFLOW_AVAILABLE:
            logger.warning("MLflow not available — cannot rollback")
            return False

        best = self.get_best_run(ticker, metric)
        if not best:
            logger.warning(f"  {ticker}: No historical runs found — rollback impossible")
            return False

        logger.info(
            f"  {ticker}: Rolling back to run {best['run_id'][:8]} "
            f"({metric}={best['metrics'].get(metric, '?'):.4f})"
        )

        # Download artifacts from MLflow to MODELS_DIR
        client = mlflow.tracking.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        local_dir = client.download_artifacts(best["run_id"], "", dst_path=str(MODELS_DIR / "_rollback_tmp"))

        # Copy model files back to MODELS_DIR
        rollback_dir = Path(local_dir)
        for suffix in ["lgb.pkl", "cat.pkl", "meta.json", "calibrator.pkl", "meta_learner.pkl"]:
            src = rollback_dir / suffix
            dst = MODELS_DIR / f"{ticker}_{suffix}"
            if src.exists():
                shutil.copy2(src, dst)
                logger.info(f"  {ticker}: Restored {suffix}")

        # Clean up temp dir
        shutil.rmtree(rollback_dir, ignore_errors=True)
        logger.info(f"  {ticker}: Rollback complete ✓")
        return True


# ── Singleton registry instance ───────────────────────────────────────────────
registry = MLflowRegistry()


# ── Main Block ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("MarketPulse AI — MLflow Model Registry")
    logger.info(f"MLflow available: {MLFLOW_AVAILABLE}")
    logger.info(f"Tracking URI: {MLFLOW_TRACKING_URI}")

    if MLFLOW_AVAILABLE:
        reg = MLflowRegistry()
        # Smoke test: create a fake run
        with reg.start_run("SMOKE_TEST") as run_id:
            reg.log_params({"max_depth": 6, "learning_rate": 0.05, "n_estimators": 1000})
            reg.log_metrics({"cv_accuracy": 0.57, "holdout_auc": 0.61, "overfit_gap": 0.04})
        logger.info(f"Smoke test run created: {run_id[:8]}")
        logger.info(f"View runs at: {MLFLOW_TRACKING_URI}")
        logger.info("Run `mlflow ui --backend-store-uri <MLFLOW_TRACKING_URI>` to open the UI")
    else:
        logger.warning("Install mlflow first: pip install mlflow")
