# MarketPulse AI — Interview Prep

> Everything in this document is grounded in the actual code.  
> File references are exact. If something isn't implemented, it's called out explicitly.

---

## Part 1 — Spoken Script (60–90 seconds)

> Read this at a natural conversational pace. Aim for 75–80 seconds.

---

"So I built an autonomous stock market signal system for the Indian NIFTY 50 market — all fifty stocks that make up India's benchmark index.

The problem I was solving is that retail investors drown in financial news every day, and there's no easy way to separate what actually moves stock prices from all the noise — cricket scores, Bollywood, general tech news.

Architecturally, I built two pipelines that run in parallel and then merge. The first is a news intelligence pipeline — seven LangGraph agents that wake up every day, pull from six RSS feeds like Economic Times and Moneycontrol, run each article through a four-stage filter — keyword blocklist, then spaCy named entity recognition, then FinBERT financial sentiment, and finally a Llama 3 model on Groq as a final gate — so only genuinely market-moving news survives. The articles that pass get mapped to specific NIFTY 50 tickers using a combination of company name lookups and macro trigger patterns I hardcoded — things like 'crude oil surges' mapping to ONGC or BPCL — and then an LLM scores the severity and confidence of each impact.

The second pipeline is machine learning. I trained one LightGBM classifier per stock — fifty models total — on ten years of OHLCV data engineered into about forty technical features. I also layered in a Hidden Markov Model trained on the NIFTY 50 index to detect whether the market is in a bull, bear, or sideways regime, and Amazon's Chronos model for zero-shot time-series forecasting. Those three signals are blended with a 60-30-10 weight scheme.

The final agent combines the ML signal and the news signal — 60% ML, 40% news — and if they strongly conflict, it flags that and reduces confidence. It then asks Llama 3.3 70B to write a plain-English explanation of the reasoning.

For deployment — everything runs serverless on free tier. A GitHub Actions cron job fires at 3:45 PM Indian Standard Time every weekday, runs the whole pipeline, writes predictions to a Supabase PostgreSQL database, and a Streamlit dashboard reads from that and updates live. Zero infrastructure cost."

---

## Part 2 — Follow-Up Q&A Bank

---

### Q1: Why split this into multiple agents instead of one model?

**Answer:**

Each agent has a fundamentally different job and a different cost profile, so combining them would mean running the most expensive operation — the Groq LLM call — on every article, even obvious noise.

The cascade is intentional. Stage 1 of the Relevance Filter is a simple keyword blocklist — it runs in microseconds and kills cricket headlines, Bollywood gossip, travel pieces. The code comment in `agents/relevance_filter.py` line 8 literally says: _"95%+ of cricket/Bollywood noise is discarded in Stage 1."_ Stage 2 is spaCy NER — cheap local model. Stage 3 is FinBERT — CPU-based transformer, no API cost. Only articles that pass all three gates hit the Groq API in Stage 4.

By the time the expensive Llama call runs in the Impact Scorer (Agent 4), you're scoring a small, already-filtered set of genuinely relevant article-ticker pairs. If it were one monolithic model, you'd either pay for every article or lose the nuanced reasoning on the ones that matter.

There's also a conditional edge in the graph: after the relevance filter, `check_has_articles()` in `agents/graph.py` (line 70) routes directly to the Market Monitor if zero articles passed — skipping Agents 3 and 4 entirely. So the ML pipeline still runs even on days with no useful news.

---

### Q2: Walk me through how the Relevance Filter (Agent 2) works.

**Answer:**

It's a four-stage funnel, each stage protecting the next more expensive one.

**Stage 1 — Keyword Blocklist** (`stage1_blocklist` in `agents/relevance_filter.py` line 128): Simple string match against a blocklist defined in `config/sector_knowledge.py`. If an article contains any blocklist keyword — "cricket", "Bollywood", etc. — it's immediately discarded. Runs in microseconds.

**Stage 2 — spaCy NER** (`stage2_entity_check`, line 151): Loads `en_core_web_sm` at module level (once, not per call). Checks title + first 300 chars of body for ORG/GPE entities matching a `MARKET_RELEVANT_ENTITIES` set, and directly checks for macro keywords like "crude", "rupee", "RBI", "SEBI", "NIFTY".

**Stage 3 — FinBERT** (`stage3_finbert`, line 193): Uses `ProsusAI/finbert` via HuggingFace `pipeline`. Runs on CPU (`device=-1`). Articles only pass if the FinBERT confidence score is ≥ 0.5. Even "neutral" financial sentiment passes — the goal here is to reject non-financial text.

**Stage 4 — Groq LLM** (`stage4_llm_check`, line 226): Uses `llama-3.1-8b-instant` (the cheaper 8B model — defined as `MODEL_SECONDARY` in `config/settings.py`). Few-shot prompt with five relevant and five irrelevant examples, returns JSON. Max tokens set to 100 because only a short boolean JSON response is needed.

If Groq is unavailable, it defaults to `relevant=True` — conservative, better to over-include than miss a real signal.

---

### Q3: How do agents pass state and data to each other?

**Answer:**

Through a shared `TypedDict` called `MarketPulseState`, defined in `agents/state.py` (line 162).

LangGraph compiles the graph in `agents/graph.py` (line 95) using `StateGraph(MarketPulseState)`. Each node is a plain Python function that takes the full state dict and returns a new state dict. LangGraph handles the merge — each node does `{**state, "its_output_key": result}`.

The state has clearly typed fields that accumulate through the pipeline. For example:
- Agent 1 writes to `state["raw_articles"]` (List of `NewsArticle` TypedDicts)
- Agent 2 reads `raw_articles`, writes `state["filtered_articles"]`
- Agent 3 reads `filtered_articles`, writes `state["mapped_impacts"]`
- Agent 4 reads `mapped_impacts`, writes `state["impact_scores"]`
- Agent 5 reads nothing from earlier agents (it fetches live prices independently), writes `current_prices`
- Agent 6 reads both `impact_scores` AND `ml_predictions` — the ML pipeline pre-computes those in `pipeline/eod_pipeline.py` before the agent graph even starts, and they're injected into the initial state via `create_initial_state(ml_predictions=ml_signals)`

So ML predictions are not produced by an agent inside the graph — they're computed first in the EOD pipeline (`_step4_lgbm_predictions`, `_step5_chronos_forecasts`, `_step6_combine_signals`) and passed in as the starting state.

---

### Q4: Why LightGBM? What breaks if you used a neural network instead?

**Answer:**

Three practical reasons.

**Speed**: Each EOD run needs to score 50 models in about 55 minutes total (the GitHub Actions timeout is set to `timeout-minutes: 55` in `.github/workflows/agent_pipeline.yml`). LightGBM inference on a CPU runner is milliseconds per stock.

**Interpretability via SHAP**: The dashboard shows *why* the model made a prediction. The `explain_prediction` method in `ml/predictor.py` (line 317) uses `shap.TreeExplainer`, which only works cleanly on tree-based models. For each stock's latest prediction, it returns the top 5 features by SHAP value — things like `rsi_14`, `macd_histogram`, `volume_spike`. Those top features are stored in the `MLPrediction` TypedDict and shown in the Signal Aggregator's Groq prompt.

**Small dataset**: Each stock has roughly 10 years of daily data — around 2,500 rows. The code enforces `MIN_ROWS = 500` and refuses to train on anything less. That's a regime where a deep neural network would likely overfit badly. LightGBM with `TimeSeriesSplit(n_splits=5)` and early stopping at 50 rounds handles this gracefully.

If you swapped in a neural network, you'd lose the SHAP explainability, you'd need GPU infrastructure (the GitHub Actions runner is `ubuntu-latest` with no GPU), and you'd need much more data per stock.

---

### Q5: Why HMM for regime detection? What does it actually do?

**Answer:**

A Hidden Markov Model fits the intuition that markets have *hidden* states — bull, bear, sideways — that aren't directly observable, but can be inferred from observable signals.

The implementation in `ml/regime_detector.py` (line 47) uses `GaussianHMM` from `hmmlearn` with 3 hidden components (`covariance_type="full"`, `n_iter=1000`). The two observable features are daily return and 5-day rolling volatility on the NIFTY 50 index (`^NSEI`). After fitting, the code sorts the three hidden states by their mean return — highest becomes "bull", lowest becomes "bear", middle becomes "sideways".

The output is a numeric feature (`bull=2, sideways=1, bear=0`) injected into each stock's feature matrix. So LightGBM uses regime as one of its ~40 input features. In the signal combiner, regime also gets a direct ±3% probability nudge (`REGIME_BIAS = {"bull": +0.03, "bear": -0.03}` in `ml/signal_combiner.py`), but only with 10% weight in the ensemble.

If you replaced HMM with a simpler moving-average crossover for regime, you'd lose the probabilistic state inference and the ability to learn that volatility patterns distinguish bear from sideways markets.

---

### Q6: Why Chronos? What would break if you removed it?

**Answer:**

Chronos is Amazon's zero-shot time-series forecasting model, installed directly from GitHub in `requirements_pipeline.txt`. The key phrase is "zero-shot" — it runs inference on a stock's historical close price series without any per-stock fine-tuning. That makes it complementary to LightGBM, which was trained on engineered features.

LightGBM is trained on indicators (RSI, MACD, volume ratios, etc.). Chronos looks at the raw price *trajectory* — the shape of recent price movement — which captures different signal than indicator engineering.

In the ensemble (`ml/signal_combiner.py`), Chronos gets 30% weight, LightGBM gets 60%, and regime gets 10%. If you removed Chronos, you'd fall back to 100% LightGBM signal, losing the trajectory context. Signals would likely be less reliable when price momentum contradicts the indicator picture.

The `signals_agree` boolean in `MLPrediction` is `True` only if all three sources — LightGBM, Chronos, and the regime — agree on direction. When all three agree, it's treated as a higher-confidence signal. That flag would be meaningless without Chronos.

---

### Q7: How does the ML + News combination actually work mathematically?

**Answer:**

It's a two-step process in `ml/signal_combiner.py`.

**Step 1 — ML ensemble** (`combine_signals`):
```
combined_prob = (lgbm_prob × 0.60) + (chronos_prob × 0.30) + (regime_prob × 0.10)
```
`chronos_prob` is derived from direction + confidence: bullish at 0.72 confidence → `0.5 + 0.72×0.5 = 0.86`. Regime is `0.5 ± 0.03`.

**Step 2 — Adding news** (`combine_with_news_signal`):
Normal case (non-major news): `final_prob = (ml_prob × 0.60) + (news_prob × 0.40 × severity_adj)` where `severity_adj` is `{"minor": 0.7, "moderate": 0.85, "major": 1.0}`.

Special case: if news severity is "major" AND confidence > 0.80, it overrides the ML entirely — floors probability at 0.80 for bullish or caps it at 0.20 for bearish. This handles things like a surprise earnings shock or an unexpected RBI rate decision.

Conflict detection: if ML and news disagree and news confidence > 0.5, the final confidence is reduced by 30% (`final_confidence × 0.7`).

Confidence everywhere is `abs(prob - 0.5) × 2` — distance from 50/50, scaled to 0–1.

---

### Q8: How is this deployed? What happens if a step fails?

**Answer:**

Deployed on a fully serverless free-tier stack.

**GitHub Actions** (`.github/workflows/agent_pipeline.yml`): Cron runs at `15 10 * * 1-5` UTC (= 3:45 PM IST, Mon-Fri). Separate cron `30 14 1 * *` triggers monthly model retraining on the 1st of each month. The workflow also has `workflow_dispatch` for manual triggers, with `run_type` options: `eod`, `retrain`, or `both`. The runner is `ubuntu-latest` with a `timeout-minutes: 55` guard. API keys are stored as GitHub Secrets.

**Persistence**: Since the GitHub Actions runner's local filesystem is wiped after every run, all data goes to **Supabase** (PostgreSQL). Each final signal is written via `supabase.table("predictions").insert(row)` in `agents/signal_aggregator.py` (line 131). SQLite is also written locally as a fallback for local development, but doesn't survive CI runs.

**Failure modes**:
- Steps 1 and 2 (data collection and feature engineering) are "hard" failures — they raise and abort the pipeline.
- Steps 3, 5 (regime, Chronos) are "soft" failures — they catch exceptions, log a warning, and return a default ("unknown" regime, empty Chronos dict). The pipeline continues.
- Individual agent failures are caught per-ticker, logged to `state["errors"]`, and the pipeline keeps running for other tickers.
- If Supabase credentials are missing, the code logs an explicit `CRITICAL WARNING` at the top of `run_eod_pipeline()` and continues (data just won't persist to cloud).

**Streamlit dashboard**: Deployed on Streamlit Community Cloud. It's stateless — reads Supabase on every page load. No server to maintain.

---

### Q9: What's the weakest part of this system? What would you improve first?

**Answer (honest and grounded in the code):**

**Biggest weakness — no closed-loop accuracy tracking in production.** The `predictions` table in SQLite has `actual_direction` and `was_correct` columns, and `validate_previous_predictions()` in `agents/market_monitor.py` does try to back-fill these daily. But whether this actually runs reliably on the GitHub Actions runner depends on the runner having consistent timing, and the SQLite file doesn't survive runs — so actual accuracy numbers visible on the Supabase-connected dashboard may be missing or incomplete.

**Second — backtesting is disconnected from live predictions.** `ml/backtesting.py` exists and has a proper backtesting framework using `vectorbt`, with Sharpe, drawdown, CAGR vs. five baselines. But it runs on *simulated* historical predictions from stored features — it does not automatically load and replay the actual signals the system generated in production. So I can't honestly quote you a verified live accuracy number. If you ask me "what's the accuracy?", the honest answer is: the code tracks it, but I haven't verified the end-to-end number from production runs.

**Third — confidence calibration.** The `CONFIDENCE_THRESHOLD = 0.55` in `config/settings.py` is a hardcoded value — not derived from calibration against historical outcomes. It's a reasonable default, but it's not empirically tuned.

**What I'd improve first:** Connect the backtesting module to replay actual Supabase-stored predictions against next-day prices, run it nightly, and display a rolling 30-day accuracy on the dashboard. That closes the feedback loop properly.

---

### Q10: Are there any hardcoded values or known TODOs I should be ready to explain?

**Answer — yes, here are the real ones from the code:**

| Location | What's hardcoded |
|---|---|
| `config/settings.py` line 99 | `CONFIDENCE_THRESHOLD = 0.55` — not calibrated, just a reasonable default |
| `config/settings.py` line 95 | `TRANSACTION_COST = 0.001` (0.1% per side) — fixed estimate, real NSE costs vary by broker |
| `config/settings.py` line 84–86 | `MARKET_OPEN = "09:15"`, `MARKET_CLOSE = "15:30"`, `EOD_PIPELINE_TIME = "15:45"` — NSE hours hardcoded |
| `ml/signal_combiner.py` line 32–36 | `REGIME_BIAS = {"bull": +0.03, "bear": -0.03}` — the 3% adjustment is hand-tuned |
| `ml/signal_combiner.py` line 71–87 | Ensemble weights (60/30/10) — chosen by intuition, not by cross-validated optimization |
| `ml/backtesting.py` line 81 | Risk-free rate hardcoded at 6% per annum for Sharpe calculation (India's approximate rate) |
| `agents/impact_scorer.py` line 92 | `SIMILARITY_THRESHOLD = 0.80` for ChromaDB RAG similarity — hand-tuned |
| `ml/predictor.py` line 68 | `MIN_ROWS = 500` minimum training data — if a stock has fewer rows, it's silently skipped |
| `ml/predictor.py` lines 71–82 | `DEFAULT_LGB_PARAMS` — used when Optuna is not run; the monthly retrain uses `optimize=False` for speed |
| Scheduler | There is a `keep_alive.yml` workflow, which suggests the system has needed "keep-alive" pings to prevent Streamlit from sleeping |

**What's NOT implemented that you might be asked about:**

- **No real-time live price data**: The pipeline runs once at 3:45 PM IST. All "current prices" are yesterday's close fetched via `yfinance`. There is no intraday tick data.
- **No verified backtested accuracy number from live signals**: The backtesting module works with historical feature data, not the actual predictions the system produced daily in the cloud.
- **No portfolio optimizer**: Signals are generated per-stock independently. There is no mean-variance or risk-parity optimizer combining them into a portfolio.
- **No sentiment time series / NLP embedding storage**: Articles are classified and scored, but the underlying text embeddings are not persisted for longitudinal sentiment analysis.
- **No automated model retraining trigger based on accuracy degradation**: Monthly retrain runs on a fixed calendar schedule (`1st of month`), not triggered by detected performance drop.

---

### Q11: Walk me through what actually happens from 3:45 PM IST to the dashboard updating.

**Answer:**

The GitHub Actions cron (`15 10 * * 1-5`) fires. The runner checks out the repo, sets up Python 3.12, installs from `requirements_pipeline.txt`, and downloads the spaCy model.

Then `python -m pipeline.eod_pipeline` runs `run_eod_pipeline()`:

1. **Step 1** — `update_all_stocks_daily()` from `ml/data_collector.py` fetches latest OHLCV for all 50 stocks via `yfinance` and writes to SQLite.
2. **Step 2** — `engineer_all_stocks()` from `ml/feature_engineering.py` computes ~40 technical indicators (RSI, MACD, Bollinger Bands, ATR, OBV, etc.) and writes `{ticker}_features.parquet` files.
3. **Step 3** — `MarketRegimeDetector` loads the saved HMM `.pkl` from `data/models/regime_model.pkl` and returns today's regime ("bull"/"bear"/"sideways") from the NIFTY 50 index close series.
4. **Step 4** — `predict_all_stocks()` loads each stock's LightGBM `.pkl`, runs inference on the last row of its feature file, and returns predictions for stocks above the 0.55 confidence threshold.
5. **Step 5** — `ChronosForecaster` runs zero-shot forecasts on each stock's close series.
6. **Step 6** — `combine_signals()` blends LightGBM + Chronos + regime with 60/30/10 weights into `MLPrediction` TypedDicts.
7. **Step 7** — `run_pipeline(run_type="eod_full", ml_predictions=ml_signals)` invokes the LangGraph graph. The seven agents run in sequence: news harvester → relevance filter → entity mapper → impact scorer → market monitor → signal aggregator → alert generator.
8. Signal Aggregator writes each `FinalSignal` to Supabase (`predictions` table) and local SQLite.
9. **Step 8** — Email alert sent via `send_email_alert()` in `pipeline/send_alerts.py`.

The Streamlit dashboard reads from Supabase on every page load — no WebSocket push, just a plain query. As soon as Supabase has the new rows, the next dashboard refresh shows the updated predictions.

Total wall-clock time is typically under 55 minutes (the Actions timeout).

---

*Document generated from codebase read on 2026-07-16. All file references point to actual functions in the repo.*
