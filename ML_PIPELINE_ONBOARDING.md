# MarketPulse AI: Machine Learning Pipeline Onboarding

Welcome to the ML team! This document walks through our Machine Learning pipeline exactly as implemented in the codebase. I will define every concept assuming no prior ML background, cite exact file paths, and explicitly flag any risks or missing components in our current architecture.

---

## 1. Model Inventory

We use four distinct statistical and machine learning models in our ML pipeline (Engine 1):

| Model | Category | Job |
|-------|----------|-----|
| **LightGBM** (`lgb.LGBMClassifier`) | Classical ML (Gradient Boosted Decision Trees) | Core directional predictor — looks at 40+ tabular features and predicts whether the stock price will go **up or down** tomorrow. |
| **CatBoost** (`CatBoostClassifier`) | Classical ML (Ordered Gradient Boosted Decision Trees) | Ensemble partner to LightGBM — handles categorical data (like "Regime" or "Expiry Week") natively. |
| **GaussianHMM** (`GaussianHMM`) | Probabilistic / State-Space Model | Detects the **market regime** (Bull, Bear, or Sideways) using the NIFTY 50 index — output feeds into LightGBM/CatBoost as a feature. |
| **Amazon Chronos-T5-Small** (`ChronosPipeline`) | Time-Series Foundation Model (Zero-shot probabilistic forecaster) | Looks at the last 60 days of raw prices and predicts the actual price **trajectory** for the next 5 days. Requires **zero training** on our end. |

---

## 2. Foundational Explanation of Each Model

### LightGBM (Gradient Boosted Decision Trees)

- **The Problem:** We have rows of data (days) and columns of features (like RSI, Volume, Moving Averages), and we want to predict a binary outcome (Up/Down).
- **The Mechanism:** A "decision tree" is like a flowchart (e.g., Is RSI > 70? If yes, go left. Is Volume > average? If yes, predict UP). "Gradient Boosting" means it builds hundreds of these trees **sequentially**. Tree #2 specifically looks at the mistakes made by Tree #1 and tries to fix them. Tree #3 fixes the mistakes of Tree #2.
- **Why Chosen:** Tree-based models utterly dominate tabular (spreadsheet) data. LightGBM is chosen over standard Logistic Regression because it can learn complex, **non-linear relationships** (e.g., RSI is only important *if* Volume is also high).

### CatBoost (Ordered Gradient Boosting)

- **The Problem:** Machine learning models only understand numbers. If you have a category like "Month = February", standard models require you to create complex dummy columns ("one-hot encoding").
- **The Mechanism:** Similar to LightGBM (it builds trees that fix previous trees' errors), but uses a special "ordered" mathematical trick to prevent overfitting and naturally understands integer categories.
- **Why Chosen:** Combining CatBoost and LightGBM in a **50/50 ensemble** (averaging their predictions) cancels out the individual biases of each model, resulting in higher overall accuracy.

### Hidden Markov Model (HMM)

- **The Problem:** The stock market has hidden "moods" (Regimes) that we cannot observe directly, but we *can* observe the symptoms of that mood (price returns and volatility).
- **The Mechanism:** An HMM assumes the system is in one of a few "hidden states" (we set it to 3: Bull, Bear, Sideways) and that the system randomly transitions between them. It uses math (Expectation-Maximization) to figure out what those states look like based on the symptoms.
- **Why Chosen:** Instead of rigidly saying "if price drops 20%, it's a bear market", the HMM **probabilistically clusters** the days into regimes based on volatility and momentum.

### Amazon Chronos

- **The Problem:** Standard ML models (like LightGBM) look at single rows of tabular features. They don't have a good "memory" of the visual shape of a price chart over time.
- **The Mechanism:** Chronos is built on the same architecture as ChatGPT (a Transformer), but instead of being trained on text, Amazon trained it on **millions of real-world time-series datasets**. It literally translates the stock chart into a "language" of tokens and predicts the next tokens (prices).
- **Why Chosen:** Standard time-series models (ARIMA) are too rigid and require constant tuning. LSTMs take massive amounts of data and time to train. Chronos is **"zero-shot"** — we don't train it at all, we just download it and use it out-of-the-box.

---

## 3. Data and Target Variable

- **Data Source & Granularity:** Daily OHLCV (Open, High, Low, Close, Volume) data. (Sourced via Yahoo Finance).
- **The Target Variable (What we predict):** We predict a **binary classification**: `1` if the price goes **UP** tomorrow, `0` if it stays the same or goes down.

**Exact Logic:** Found in `ml/feature_engineering.py` (Line 299):
```python
df["target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
```

- **Train/Validation/Test Split:** We use **Time-based splitting**, not random splitting.

**Exact Logic:** Found in `ml/model_trainer.py` (Line 222):
```python
tscv = TimeSeriesSplit(n_splits=5)
```

> **Why it matters:** If we randomly shuffled dates, the model would train on data from Friday to predict data from Wednesday. This is **"future data leakage"** and ruins financial ML models. `TimeSeriesSplit` strictly walks forward chronologically (Train on Jan–Jun, validate on Jul. Then train on Jan–Jul, validate on Aug).

---

## 4. Feature Engineering

We generate **40+ features** in `ml/feature_engineering.py`. They are grouped logically:

| Feature Group | Examples | Purpose |
|---------------|----------|---------|
| **Price/Momentum** | `daily_return`, `weekly_return`, `monthly_return`, `log_return` | Understand if the stock is trending |
| **Technical Indicators** | RSI, MACD, Bollinger Bands, Stochastics, VWAP, EMAs (via `ta` library) | Quantify "overbought" or "oversold" conditions |
| **Volume Features** | `volume_sma_20`, `volume_ratio`, `volume_spike` | A price move on 2× average volume is far more significant than a move on low volume |
| **Price Patterns** | `price_vs_52w_high`, `distance_from_ema200` | Where we are in the grand historical scheme |
| **NSE Calendar Features** | `is_fo_expiry_week`, `is_rbi_week`, `is_result_season` | Captures structural Indian market volatility that pure math would miss |
| **Macro Regime** | `market_regime` | Generated by `regime_detector.py` |

**Dependency Trace:** `model_trainer.py` requires `regime_detector.py` to run first, because the HMM output is a direct input feature (`market_regime`) into the LightGBM/CatBoost models.

---

## 5. Feature Importance and Contribution

We calculate feature importance in two ways:

1. **LightGBM Built-in (Global):** In `ml/model_trainer.py` (Line 373), the code extracts `self.lgb_model.feature_importances_` and saves the top 10 most globally important features to the model's metadata JSON.

2. **SHAP (Local):** In `ml/predictor.py` (Line 317), we use `shap.TreeExplainer`. SHAP uses game theory to explain exactly *why* the model made a specific prediction on a specific day (e.g., "I predicted UP today largely because `distance_from_ema200` was highly negative").

> [!WARNING]
> **Missing Component:** The codebase does not actively prune "dead" or low-importance features automatically. All 40+ features remain in the pipeline forever unless manually removed.

---

## 6. Overfitting and Underfitting Handling

Overfitting is when a model memorizes the past perfectly but fails to predict the future. We use specific regularizations in `ml/model_trainer.py` (Line 98) to stop this:

| Parameter | Value | Effect |
|-----------|-------|--------|
| `max_depth` | `6` | Stops trees from growing too deep and memorizing noise |
| `min_child_samples` | `50` | Forces every leaf to be based on at least 50 historical days |
| `subsample` | `0.8` | Forces each tree to randomly ignore 20% of rows |
| `colsample_bytree` | `0.8` | Forces each tree to randomly ignore 20% of features |
| **Early Stopping** | `od_wait: 50` | Stops training if validation score hasn't improved for 50 rounds |

**Monitoring:** The system calculates the gap between Training Accuracy and Cross-Validation (CV) Accuracy. If the gap is > 10% (e.g., Train is 85%, CV is 60%), it logs a major `WARNING` that the model is overfitting (Line 284).

---

## 7. Data Imbalance

Stock markets generally go up more often than they go down.

- **The Numbers:** The code dynamically prints this during training: `target balance: {self.y.mean():.2%} up days`.
- **The Treatment:** We natively handle this using `class_weight="balanced"` in LightGBM (Line 112) and `auto_class_weights="Balanced"` in CatBoost (Line 130). This mathematically penalizes the model heavier if it gets the minority class (e.g., Bearish days) wrong.

---

## 8. Evaluation Metrics

We use two different sets of metrics:

### Pure Machine Learning Metrics
`accuracy_score` and `roc_auc_score` are computed during cross-validation in `model_trainer.py`.

### Financial Backtesting Metrics
In `ml/backtesting.py`, we use the **vectorbt** library to simulate actually trading the model's historical predictions. It calculates:
- **Sharpe Ratio** (risk-adjusted return)
- **Max Drawdown**
- **CAGR**
- **Win Rate**

**Baselines:** It honestly compares the model against 5 baselines: *Always Up*, *Momentum*, *Mean Reversion*, *Random*, and *Buy-and-Hold NIFTY 50* (Line 187).

---

## 9. Error Analysis

> [!WARNING]
> **Missing Component:** There is currently **NO** systematic error analysis in the pipeline. We do not have logic that groups failures by regime, tracks if we consistently over-predict bullishness, or analyzes failures during high volatility. We only track global accuracy and backtested returns.

---

## 10. Model and Pipeline Outputs

### Individual Outputs

| Model | Output |
|-------|--------|
| LightGBM / CatBoost | Float probability (e.g., `0.65` → 65% chance of UP) |
| Chronos | Matrix of 20 simulated 5-day price trajectories — we take the **median** of those 20 paths |

### Combination Logic (`ml/signal_combiner.py` Line 41)

- ML models are weighted: **60% LightGBM/CatBoost Ensemble + 30% Chronos + 10% HMM Regime Bias**
- If Chronos says "Bullish" with high confidence, its 30% weight is added to LightGBM.
- If the Regime is "Bull", a bias adjustment of `+0.03` is added.
- If the final ML probability > `0.5`, the signal is **BULLISH**.

### Bayesian News Signal Fusion (`ml/signal_combiner.py` Line 130)
- Uses **Bayesian Dynamic Updating** (Prior vs. Likelihood Ratio) to combine ML prior probability with News Agent impact scores.
- When ML and News conflict, Bayes' Theorem mathematically pulls the posterior probability towards $0.50$ (neutrality) and dynamically shrinks confidence without static hardcoded hacks.
- If high-confidence major news occurs, the Likelihood Ratio naturally shifts the ML prior.

---

## 11. Things You Haven't Thought to Ask (But Should)

| Topic | Status | Detail |
|-------|--------|--------|
| **Data Leakage** | ✅ Safe | `.shift(-1)` for target + `TimeSeriesSplit` ensures the model strictly cannot see the future. |
| **Look-Ahead Bias in Backtesting** | ✅ Safe | `vectorbt` simulates step-by-step trading. Signal shifted by 1 day (`signal_matrix.shift(1)`) ensures we only buy *after* the signal is generated (Line 181). |
| **Stationarity** | ⚠️ Risk | Financial data drifts constantly. RSI meant something different in 1999 than in 2024. We do **not** currently apply fractional differencing to force stationarity on features. |
| **Model Retraining & Execution Cadence** | ✅ Automated | ML pipeline runs daily at **8:15 AM IST** (1hr pre-market) via `.github/workflows/agent_pipeline.yml`. Monthly retraining runs on 1st of every month at 8 PM IST. |
| **Drift Detection** | ✅ Resolved | `ml/drift_monitor.py` uses Evidently AI & PSI to compare 30-day live feature distributions vs historical baseline. |
| **Model Versioning** | ✅ Resolved | `ml/model_registry.py` uses MLflow tracking to version runs and support automated rollback (`rollback_to_best`). |
| **Confidence Calibration** | ✅ Resolved | `ml/model_trainer.py` uses `CalibratedClassifierCV` (Platt Scaling) so raw model probability outputs match real-world probabilities. |
