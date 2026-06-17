# MarketPulse AI — Complete Blueprint & Development Prompts

---

## HOW TO USE THIS DOCUMENT

- Open this file alongside your VS Code
- Copy **one Part at a time** and paste it to your VS Code LLM (GitHub Copilot Chat / Cursor / Continue)
- **Run the code after each Part. Fix errors before moving to the next Part.**
- Never skip a Part — each one builds on the previous
- If the LLM gives incomplete code, paste the same prompt again and say "complete the implementation"

---

---

# SECTION 1: COMPLETE PROJECT BLUEPRINT

---

## What We Are Building

**MarketPulse AI** — An intelligent stock signal system for NIFTY 50 that combines:
- **7 LangGraph agents** that monitor news 24/7, filter relevant events, map them to stocks, and generate calibrated probability signals
- **3-layer ML pipeline** (HMM + LightGBM + Chronos) that predicts stock direction from technical data
- **Streamlit dashboard** showing predictions, news signals, backtesting results, and model performance
- **Fully free stack** — no paid APIs, no paid cloud, no paid databases

---

## Full Tech Stack — What Uses What

| Purpose | Tool/Library | Why |
|---|---|---|
| Agent orchestration | LangGraph + LangChain | Controls exact flow between 7 agents |
| Primary LLM | Groq API (Llama 3.3 70B + Llama 3.1 8B) | Free, fast, reliable |
| Fallback LLM | Gemini Flash 2.0 | When Groq hits rate limits |
| News relevance filter | FinBERT (ProsusAI/finbert) | Local, free, financial sentiment |
| NER (name extraction) | spaCy (en_core_web_sm) | Extract company names from news |
| Market data | yfinance + nsepy | Free NSE/BSE historical + live data |
| Technical indicators | pandas-ta | 200+ indicators (RSI, MACD, BB etc) |
| Market regime detection | hmmlearn (GaussianHMM) | Classify bull/bear/sideways |
| Core ML prediction | LightGBM | Binary classifier, fast, accurate |
| Time series forecast | Amazon Chronos (HuggingFace) | Pre-trained, zero-shot, differentiator |
| ML explainability | SHAP | Why did the model predict this? |
| Hyperparameter tuning | Optuna | Free, automatic tuning |
| Backtesting | vectorbt | Professional metrics (Sharpe, drawdown) |
| Vector DB (RAG memory) | ChromaDB | Store historical news-impact pairs |
| Embeddings | sentence-transformers | Local embeddings, no API |
| Dashboard | Streamlit | Free deploy, Python-native |
| Scheduling (dev) | APScheduler | Run agents every 30 min locally |
| Scheduling (prod) | GitHub Actions | Free cloud scheduler |
| Data storage (dev) | SQLite | Zero setup, built into Python |
| Data storage (prod) | Supabase free tier | PostgreSQL, always on |
| Monitoring | LangSmith | Debug agent traces, free tier |

---

## Complete Folder Structure

```
marketpulse-ai/
├── README.md
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   ├── settings.py              # All API keys, model names, constants
│   ├── nifty50_tickers.py       # All 50 tickers with .NS suffix
│   └── sector_knowledge.py      # Full dependency graph + trade maps
│
├── data/
│   ├── raw/                     # Raw news articles (JSON)
│   ├── processed/               # Feature-engineered stock data (CSV)
│   ├── predictions/             # Daily predictions log (SQLite)
│   ├── outcomes/                # Actual outcomes for accuracy tracking
│   ├── models/                  # Saved LightGBM models per stock
│   └── chroma_db/               # ChromaDB vector store
│
├── agents/
│   ├── __init__.py
│   ├── state.py                 # LangGraph shared state definition
│   ├── news_harvester.py        # Agent 1: RSS + NewsAPI polling
│   ├── relevance_filter.py      # Agent 2: 4-stage relevance pipeline
│   ├── entity_mapper.py         # Agent 3: Company + macro trigger mapping
│   ├── impact_scorer.py         # Agent 4: LLM impact assessment
│   ├── market_monitor.py        # Agent 5: Live price + prediction tracking
│   ├── signal_aggregator.py     # Agent 6: Combine news + ML signals
│   ├── alert_generator.py       # Agent 7: Generate SEBI-compliant alerts
│   └── graph.py                 # LangGraph full orchestration
│
├── ml/
│   ├── __init__.py
│   ├── data_collector.py        # Fetch + store historical price data
│   ├── feature_engineering.py   # All pandas-ta indicators + NSE features
│   ├── regime_detector.py       # HMM market regime (bull/bear/sideways)
│   ├── predictor.py             # LightGBM train + predict + SHAP
│   ├── chronos_forecaster.py    # Chronos zero-shot time series
│   ├── signal_combiner.py       # Weighted ensemble of all ML signals
│   └── backtesting.py           # vectorbt backtesting + 5 baselines
│
├── pipeline/
│   ├── __init__.py
│   ├── scheduler.py             # APScheduler (development)
│   ├── eod_pipeline.py          # End-of-day full run (agents + ML)
│   └── retrain_pipeline.py      # Monthly ML retraining trigger
│
├── dashboard/
│   ├── app.py                   # Main Streamlit entry point
│   └── pages/
│       ├── 1_predictions.py     # Main predictions page
│       ├── 2_news_signals.py    # News signals and reasoning
│       ├── 3_backtesting.py     # Backtest results + baselines
│       └── 4_model_performance.py # Accuracy tracking over time
│
└── .github/
    └── workflows/
        └── agent_pipeline.yml   # GitHub Actions scheduler
```

---

## Data Flow — How Everything Connects

```
EVERY 30 MINUTES (News Pipeline):
RSS Feeds + NewsAPI
        ↓
Agent 1: News Harvester → Deduplicated raw articles → ChromaDB
        ↓
Agent 2: Relevance Filter
    Stage 1: Regex blocklist (cricket, Bollywood → discard)
    Stage 2: spaCy NER (no NIFTY entity? → discard)
    Stage 3: FinBERT (not financial? → discard)
    Stage 4: Groq LLM (final confirmation + initial sentiment)
        ↓
Agent 3: Entity & Sector Mapper
    → Extract company names + macro triggers
    → Lookup sector dependency graph
    → Output: {stock: HPCL, direction: bearish, trigger: crude_oil}
        ↓
Agent 4: Impact Scorer
    → LLM + knowledge graph context
    → Historical RAG (did similar news move this stock before?)
    → Output: severity + confidence + reasoning
        ↓
Stored in SQLite (news signals table)

EVERY DAY AT 3:45 PM IST (EOD Pipeline):
Agent 5: Market Monitor
    → Fetch all 50 stocks closing prices
    → Compare yesterday's predictions vs today's outcomes
    → Log accuracy

ML Pipeline runs in parallel:
    → feature_engineering.py (calculate today's indicators)
    → regime_detector.py (current market regime)
    → predictor.py (LightGBM predict_proba for all 50)
    → chronos_forecaster.py (directional signal)
    → signal_combiner.py (weighted ensemble)
        ↓
Agent 6: Signal Aggregator
    → Combine news signals + ML signals for each stock
    → Final probability with reasoning chain
        ↓
Agent 7: Alert Generator
    → SEBI-compliant formatted alerts
    → Stored in predictions table
        ↓
Streamlit Dashboard reads from SQLite and displays everything
```

---

---

# SECTION 2: DEVELOPMENT PROMPTS

---

## PART 1 — Project Setup

```
You are helping me build MarketPulse AI — a NIFTY 50 stock signal intelligence 
system using LangGraph agents and a LightGBM + Chronos ML pipeline.

Task: Set up the complete project structure.

Create the following folder structure exactly:
marketpulse-ai/
├── config/ (with __init__.py)
├── data/raw/, data/processed/, data/predictions/, data/outcomes/, 
    data/models/, data/chroma_db/
├── agents/ (with __init__.py)
├── ml/ (with __init__.py)
├── pipeline/ (with __init__.py)
├── dashboard/pages/
└── .github/workflows/

Create requirements.txt with these exact libraries:
langgraph
langchain
langchain-groq
langchain-google-genai
langchain-community
langsmith
groq
google-generativeai
feedparser
newsapi-python
spacy
transformers
torch
sentence-transformers
chromadb
yfinance
nsepy
pandas-ta
lightgbm
hmmlearn
shap
optuna
vectorbt
streamlit
plotly
apscheduler
python-dotenv
sqlalchemy
supabase
requests
beautifulsoup4
scipy
scikit-learn
numpy
pandas
chronos-forecasting

Create .env.example with these placeholders:
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
NEWSAPI_KEY=your_newsapi_key_here
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=marketpulse-ai

Create .gitignore that ignores: .env, __pycache__, *.pyc, data/raw/*, 
data/processed/*, data/models/*, data/chroma_db/*, *.sqlite, .DS_Store

Create a README.md skeleton with project name, description, and 
"Setup Instructions" and "Architecture" sections as placeholders.

Do not write any logic yet. Only create the structure and files listed above.
```

---

## PART 2 — Configuration Layer (Settings + NIFTY 50 Tickers)

```
You are building MarketPulse AI. 

Task: Create config/settings.py and config/nifty50_tickers.py

In config/settings.py:
- Load all environment variables using python-dotenv
- Define MODEL_PRIMARY = "llama-3.3-70b-versatile" (for complex agents)
- Define MODEL_SECONDARY = "llama-3.1-8b-instant" (for simple agents)
- Define GROQ_API_KEY, GEMINI_API_KEY, NEWSAPI_KEY loaded from .env
- Define LANGSMITH_API_KEY loaded from .env
- Define DATA_DIR, MODELS_DIR, CHROMA_DIR as Path objects pointing to 
  the data/ subdirectories
- Define POLL_INTERVAL_MINUTES = 30
- Define MARKET_OPEN = "09:15" and MARKET_CLOSE = "15:30" (IST)
- Define NIFTY50_COUNT = 50
- Define TRANSACTION_COST = 0.001 (0.1% per side for backtesting)
- Define TRAINING_START_DATE = "2015-01-01"
- Define CONFIDENCE_THRESHOLD = 0.55 (minimum confidence to show signal)

In config/nifty50_tickers.py:
Create a complete dictionary called NIFTY50_STOCKS where:
- Key is the yfinance ticker symbol (with .NS suffix)
- Value is a dict with "name" (full company name), "sector" (sector name), 
  "industry" (specific industry)

Include all current NIFTY 50 stocks as of 2024:
RELIANCE.NS, TCS.NS, HDFCBANK.NS, BHARTIARTL.NS, ICICIBANK.NS, INFOSYS.NS,
SBIN.NS, HINDUNILVR.NS, ITC.NS, LT.NS, BAJFINANCE.NS, HCLTECH.NS,
MARUTI.NS, SUNPHARMA.NS, ADANIENT.NS, KOTAKBANK.NS, TITAN.NS, ONGC.NS,
NTPC.NS, ULTRACEMCO.NS, AXISBANK.NS, ASIANPAINT.NS, WIPRO.NS, NESTLEIND.NS,
BAJAJFINSV.NS, POWERGRID.NS, M&M.NS, TATAMOTORS.NS, HDFCLIFE.NS, TECHM.NS,
INDUSINDBK.NS, TATASTEEL.NS, SBILIFE.NS, GRASIM.NS, JSWSTEEL.NS, 
ADANIPORTS.NS, BPCL.NS, HINDALCO.NS, DIVISLAB.NS, DRREDDY.NS, 
CIPLA.NS, EICHERMOT.NS, COALINDIA.NS, HEROMOTOCO.NS, BRITANNIA.NS,
TATACONSUM.NS, APOLLOHOSP.NS, SHRIRAMFIN.NS, BEL.NS, HAL.NS

Also create a reverse mapping called COMPANY_TO_TICKER — a dict where common 
company name variations map to their ticker. Include at least 3 name variants 
per major company (e.g. "Reliance", "RIL", "Reliance Industries" → "RELIANCE.NS").

Also create a list called SECTOR_GROUPS that groups tickers by sector:
IT_STOCKS, BANKING_STOCKS, OIL_GAS_STOCKS, AUTO_STOCKS, PHARMA_STOCKS, 
FMCG_STOCKS, METAL_STOCKS, INFRA_STOCKS, DEFENSE_STOCKS
```

---

## PART 3 — Sector Knowledge Base (The Intelligence Layer)

```
You are building MarketPulse AI.

Task: Create config/sector_knowledge.py — this is the most critical file 
in the entire project. It contains ALL the structured financial knowledge 
the agents use. The LLM agents consult this file instead of reasoning from 
scratch, making predictions reliable and consistent.

Create the following data structures:

1. MACRO_TRIGGERS dict — maps economic event names to their sector impacts:
Include these triggers with bullish and bearish stock lists:
- "crude_oil_price_increase": bearish for OMCs (BPCL), airlines (INDIGO if listed), 
  tyres (not in NIFTY50 directly), paints (ASIANPAINT). Bullish for ONGC, RELIANCE 
  upstream.
- "crude_oil_price_decrease": opposite of above
- "rupee_depreciation": bullish for IT (TCS, INFOSYS, WIPRO, HCLTECH, TECHM), 
  pharma exporters (SUNPHARMA, DRREDDY, CIPLA, DIVISLAB). Bearish for aviation, 
  importers.
- "rupee_appreciation": opposite
- "rbi_rate_hike": bearish for all banking stocks (HDFCBANK, ICICIBANK, SBIN, 
  AXISBANK, KOTAKBANK, INDUSINDBK), NBFC (BAJFINANCE, BAJAJFINSV). 
  Bearish for real estate adjacent.
- "rbi_rate_cut": bullish for banking, NBFC, rate-sensitive sectors
- "us_fed_rate_hike": bearish for IT stocks (dollar earnings attractive but 
  US companies cut budgets). Mixed for banking.
- "india_china_tension": bullish for defense (HAL, BEL), bearish for 
  ADANIPORTS (trade flows)
- "global_recession_fear": bearish for IT (client budget cuts), metals 
  (TATASTEEL, JSWSTEEL, HINDALCO), bearish broadly
- "india_gdp_strong": bullish for banks, auto (MARUTI, TATAMOTORS, M&M, 
  EICHERMOT, HEROMOTOCO), FMCG (HINDUNILVR, ITC, BRITANNIA, NESTLEIND, TATACONSUM)
- "fii_selloff": broadly bearish, especially large caps
- "fii_buying": broadly bullish
- "gold_price_rise": slightly bullish for TITAN (jewellery margins affected, 
  but brand value holds)
- "coal_price_rise": bearish for NTPC, POWERGRID (input costs). 
  Bullish for COALINDIA
- "us_sanctions_on_country": depends on country — add Russia (affects oil), 
  China (affects imports), Middle East (affects oil)
- "budget_announcement_capex": bullish for LT, NTPC, POWERGRID, BHEL, 
  infra and defense
- "semiconductor_shortage": bearish for auto (MARUTI, TATAMOTORS, M&M) 
  that use chips in vehicles
- "ev_adoption_acceleration": bullish for TATAMOTORS (Tata EV), bearish 
  for traditional auto fuel dependent

2. TRADE_DEPENDENCY_MAP dict — for each stock that has significant 
trade exposure:
- "export_revenue_usd": stocks earning significantly in USD — 
  IT stocks, pharma exporters
- "import_dependent_crude": stocks where crude oil is a major input cost — 
  BPCL, ASIANPAINT (crude derivatives), tyre sector
- "china_import_dependent": stocks importing significantly from China — 
  solar, electronics adjacent
- "middle_east_exposure": ADANIPORTS (port traffic), oil companies

3. NSE_CALENDAR_EVENTS dict — important dates/patterns:
- "fo_expiry": "Last Thursday of every month — causes intraday volatility 
  and short covering. Affects all NIFTY 50 stocks. Typically reversal 
  patterns intraday."
- "rbi_mpc": "6-8 times per year. Scheduled dates published by RBI. 
  Strongly affects banking stocks 2-3 days before and on announcement day."
- "union_budget": "First Tuesday of February. Biggest single market 
  event annually. Affects all sectors. Heightened uncertainty 1 week before."
- "q_results_season": "Quarterly — April, July, October, January. 
  Individual stock volatility spikes around result dates."
- "nifty_rebalancing": "Semi-annual. NSE announces 4-6 weeks in advance. 
  Stocks being added see buying pressure, stocks being removed see selling."

4. KEYWORD_BLOCKLIST list — news headlines containing ANY of these words 
should be immediately discarded as market-irrelevant:
Include: cricket, IPL, bollywood, film, actor, actress, celebrity, 
wedding, divorce, weather (unless followed by flood/cyclone/drought), 
sports score, match result, entertainment, music, fashion, recipe, 
travel blog, astrology, horoscope, religion (unless involves listed company)

5. MARKET_RELEVANT_ENTITIES list — spaCy NER check: an article must 
mention at least one of these to pass stage 2 of the relevance filter:
Include: all NIFTY 50 company names and common variants, plus:
RBI, SEBI, Finance Ministry, NSE, BSE, Federal Reserve, Fed, 
crude oil, Brent, WTI, rupee, dollar, USDINR, FII, DII, 
foreign institutional, domestic institutional, Sensex, NIFTY, 
repo rate, inflation, CPI, GDP, exports, imports, trade deficit

Make all these structures importable and well-commented.
```

---

## PART 4 — ML Data Collection

```
You are building MarketPulse AI.

Task: Create ml/data_collector.py

This file fetches and stores historical price data for all NIFTY 50 stocks.

Requirements:
- Import NIFTY50_STOCKS from config/nifty50_tickers.py
- Import TRAINING_START_DATE, DATA_DIR from config/settings.py

Create these functions:

1. fetch_historical_data(ticker: str, start_date: str, end_date: str = None) -> pd.DataFrame
   - Use yfinance to download data
   - Always use auto_adjust=True and actions=True
   - If end_date is None, use today's date
   - Add a column "ticker" with the ticker symbol
   - Handle exceptions: if download fails, log warning and return empty DataFrame
   - Return OHLCV dataframe with Date as index

2. fetch_all_nifty50(start_date: str = TRAINING_START_DATE) -> dict
   - Loop through all tickers in NIFTY50_STOCKS
   - Call fetch_historical_data for each
   - Save each stock's data as CSV to DATA_DIR/processed/{ticker}.csv
   - Print progress (e.g. "Fetching RELIANCE.NS... done (2341 rows)")
   - Return dict of {ticker: dataframe}
   - Add 2 second sleep between fetches to avoid rate limiting

3. fetch_single_stock_today(ticker: str) -> pd.Series
   - Fetch last 5 days of data for one stock (needed for feature calculation)
   - Return last row as Series (today's OHLCV)

4. update_all_stocks_daily() -> None
   - For each stock, read existing CSV
   - Find last date in CSV
   - Fetch data from that date onwards
   - Append new rows to existing CSV (avoid duplicates)
   - Used by the daily EOD pipeline

5. get_nifty50_index_data(start_date: str = TRAINING_START_DATE) -> pd.DataFrame
   - Fetch "^NSEI" (NIFTY 50 index) data
   - Used as benchmark in backtesting
   - Save to DATA_DIR/processed/NIFTY50_INDEX.csv

Add a main block at the bottom that runs fetch_all_nifty50() when 
the script is run directly — this is the one-time initial data download.

Use proper logging (Python logging module, not print) for all messages.
Handle the case where NSE data might have gaps for Indian holidays.
```

---

## PART 5 — Feature Engineering

```
You are building MarketPulse AI.

Task: Create ml/feature_engineering.py

This file takes raw OHLCV data and creates all ML features.

Import: pandas, numpy, pandas_ta, and NSE_CALENDAR_EVENTS from config/sector_knowledge.py

Create this main function:
engineer_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame

The function should add these feature columns to the dataframe:

PRICE FEATURES:
- daily_return: percentage return for the day
- weekly_return: 5-day return
- monthly_return: 21-day return
- log_return: log of (close/previous_close)

TECHNICAL INDICATORS (using pandas_ta):
- rsi_14: RSI with 14 period
- rsi_7: RSI with 7 period (short-term momentum)
- macd: MACD line
- macd_signal: MACD signal line  
- macd_histogram: MACD histogram
- bb_upper, bb_middle, bb_lower: Bollinger Bands (20 period)
- bb_width: (bb_upper - bb_lower) / bb_middle (squeeze indicator)
- bb_position: where close sits within the band (0 to 1)
- ema_9, ema_21, ema_50, ema_200: Exponential moving averages
- ema_cross_9_21: 1 if ema_9 > ema_21, else 0
- ema_cross_21_50: 1 if ema_21 > ema_50, else 0
- atr_14: Average True Range (volatility)
- obv: On Balance Volume
- obv_ema: 20-period EMA of OBV
- adx_14: Average Directional Index (trend strength)
- cci_20: Commodity Channel Index
- stoch_k, stoch_d: Stochastic oscillator
- williams_r: Williams %R
- mfi_14: Money Flow Index
- vwap: Volume Weighted Average Price (approximate daily)

VOLUME FEATURES:
- volume_sma_20: 20-day average volume
- volume_ratio: today's volume / volume_sma_20 (relative volume)
- volume_spike: 1 if volume_ratio > 2.0, else 0

PRICE PATTERN FEATURES:
- price_vs_52w_high: close / 52-week high
- price_vs_52w_low: close / 52-week low
- distance_from_ema200: (close - ema_200) / ema_200

NSE CALENDAR FEATURES:
- days_to_fo_expiry: days until next F&O expiry (last Thursday of month)
  Calculate this correctly using pandas date logic
- is_fo_expiry_week: 1 if within 5 days of F&O expiry
- is_rbi_week: 1 if within 3 days of a known RBI MPC date
  Hardcode 2024-2025 RBI MPC dates: 
  2024-02-08, 2024-04-05, 2024-06-07, 2024-08-08, 2024-10-09, 2024-12-06,
  2025-02-07, 2025-04-09, 2025-06-06
- is_budget_month: 1 if month is February (Union Budget month)
- is_result_season: 1 if month is April, July, October, or January

TARGET VARIABLE:
- target: 1 if next day's close > today's close, else 0
  (This is what LightGBM predicts — shift by -1)

After creating all features:
- Drop rows with NaN (first 200 rows will have NaN due to EMA-200)
- Return cleaned dataframe

Also create:
engineer_all_stocks() -> None
- Reads each stock's CSV from DATA_DIR/processed/
- Calls engineer_features()
- Saves output to DATA_DIR/processed/{ticker}_features.csv
```

---

## PART 6 — Market Regime Detector (HMM)

```
You are building MarketPulse AI.

Task: Create ml/regime_detector.py

This file uses a Hidden Markov Model to classify the current market as 
Bull, Bear, or Sideways. This regime label is used as a feature in LightGBM.

Import: hmmlearn.hmm.GaussianHMM, numpy, pandas, joblib

Create class MarketRegimeDetector:

__init__(self, n_states=3):
    - self.model = GaussianHMM(n_components=3, covariance_type="full", n_iter=1000)
    - self.state_labels = {}  # maps state number to "bull"/"bear"/"sideways"
    - self.is_fitted = False

fit(self, price_series: pd.Series) -> None:
    - Calculate daily returns from price series
    - Calculate 5-day rolling volatility
    - Stack returns and volatility as features: shape (n, 2)
    - Fit the GaussianHMM model on these features
    - After fitting, identify which state is bull/bear/sideways:
      * Calculate mean return for each state
      * Highest mean return state → "bull"
      * Lowest mean return state → "bear"  
      * Middle state → "sideways"
    - Set self.is_fitted = True

predict_regime(self, price_series: pd.Series) -> pd.Series:
    - Calculate same features as fit()
    - Predict hidden states using model.predict()
    - Map state numbers to labels using self.state_labels
    - Return Series of regime labels aligned with input index

get_current_regime(self, price_series: pd.Series) -> str:
    - Return the regime label for the most recent date
    - Returns one of: "bull", "bear", "sideways"

save(self, filepath: str) -> None:
    - Save model using joblib.dump()

load(self, filepath: str) -> None:
    - Load model using joblib.load()

Also create standalone function:
fit_and_save_all_regime_models() -> None:
- Load NIFTY 50 index data (^NSEI)
- Fit one regime model on the index (market-wide regime)
- Save to data/models/regime_model.pkl
- Also add regime as a feature column to each stock's feature CSV
  by loading each {ticker}_features.csv and adding "market_regime" column
  (encoded as: bull=2, sideways=1, bear=0)
```

---

## PART 7 — LightGBM Predictor

```
You are building MarketPulse AI.

Task: Create ml/predictor.py

This is the core ML prediction engine. It trains one LightGBM model per stock 
and makes directional predictions with confidence scores.

Import: lightgbm, sklearn, shap, optuna, pandas, numpy, joblib

Define FEATURE_COLUMNS list — include all feature column names created in 
feature_engineering.py EXCEPT: Date, Open, High, Low, Close, Volume, ticker, 
target, Dividends, Stock Splits (only use engineered features as inputs)

Create class StockPredictor:

__init__(self, ticker: str):
    - self.ticker = ticker
    - self.model = None
    - self.feature_columns = FEATURE_COLUMNS
    - self.model_path = DATA_DIR/models/{ticker}_model.pkl

train(self, df: pd.DataFrame, optimize_hyperparams: bool = False) -> dict:
    - Use TimeSeriesSplit(n_splits=5) for validation — NEVER random split
    - Features X = df[self.feature_columns]
    - Target y = df["target"]
    - If optimize_hyperparams is True:
        Run Optuna study with 50 trials to find best:
        num_leaves (20-300), learning_rate (0.001-0.3), 
        min_child_samples (5-100), feature_fraction (0.5-1.0),
        bagging_fraction (0.5-1.0), max_depth (3-12)
    - Train final LightGBM model with best params (or defaults if not optimizing):
        Default params: num_leaves=63, learning_rate=0.05, n_estimators=500,
        min_child_samples=20, objective="binary", metric="binary_logloss",
        class_weight="balanced"
    - Calculate out-of-fold accuracy and AUC across all splits
    - Save trained model with joblib
    - Return dict: {accuracy, auc, n_samples, ticker}

predict(self, df: pd.DataFrame) -> dict:
    - Load model if not in memory
    - Get features from last row of df
    - Call model.predict_proba() to get probability scores
    - Return dict: {
        ticker: self.ticker,
        probability_up: float (probability of going up),
        probability_down: float,
        predicted_direction: "bullish" if prob_up > 0.5 else "bearish",
        confidence: abs(prob_up - 0.5) * 2  (0 to 1 scale),
        signal_strength: "strong" if confidence > 0.3 else "moderate" if > 0.15 else "weak"
      }

explain_prediction(self, df: pd.DataFrame, top_n: int = 5) -> list:
    - Use SHAP TreeExplainer on the last row
    - Return top N features driving the prediction as list of dicts:
      [{feature_name, shap_value, direction: "positive"/"negative"}]

Also create standalone functions:
train_all_models(optimize: bool = False) -> None
- Load each {ticker}_features.csv
- Create StockPredictor and call train()
- Print results table at the end

predict_all_stocks() -> list
- For each ticker, load its feature CSV and call predict()
- Return list of all prediction dicts
- Used by the daily EOD pipeline
```

---

## PART 8 — Chronos Forecaster

```
You are building MarketPulse AI.

Task: Create ml/chronos_forecaster.py

This uses Amazon's pre-trained Chronos time series model for zero-shot 
price trajectory forecasting. No training required — Chronos is pre-trained.

Import: torch, numpy, pandas
The chronos package is installed as: from chronos import ChronosPipeline

Create class ChronosForecaster:

__init__(self):
    - Load the small Chronos model to save memory:
      self.pipeline = ChronosPipeline.from_pretrained(
          "amazon/chronos-t5-small",
          device_map="cpu",
          torch_dtype=torch.bfloat16
      )
    - self.prediction_horizon = 5  (predict next 5 days)
    - self.context_length = 60     (use last 60 days as context)

forecast_direction(self, price_series: pd.Series, ticker: str) -> dict:
    - Take last self.context_length closing prices
    - Convert to torch tensor
    - Call self.pipeline.predict() with num_samples=20 for uncertainty
    - Get the median forecast trajectory (next 5 days)
    - Calculate direction: 
      * If day-5 predicted price > current price → "bullish"
      * If day-5 predicted price < current price → "bearish"
      * Within 0.5% → "neutral"
    - Calculate confidence based on spread of the 20 samples
      (low spread = high confidence, high spread = low confidence)
    - Return dict: {
        ticker: ticker,
        chronos_direction: "bullish"/"bearish"/"neutral",
        chronos_confidence: float (0 to 1),
        forecast_horizon_days: 5,
        predicted_change_pct: percentage change from current to day-5 median
      }

forecast_all_stocks(price_data: dict) -> dict:
    - Takes dict of {ticker: price_series}
    - Calls forecast_direction for each
    - Returns dict of {ticker: forecast_result}
    - Handle exceptions per stock — if Chronos fails for one stock, 
      log and continue (don't crash the pipeline)

Note: Chronos may take 30-60 seconds total for all 50 stocks on CPU. 
This is acceptable since it runs once per day at EOD.
```

---

## PART 9 — Signal Combiner + Backtesting

```
You are building MarketPulse AI.

Task: Create ml/signal_combiner.py and ml/backtesting.py

FILE 1: ml/signal_combiner.py

This combines LightGBM, Chronos, and HMM regime signals into one final score.

Create function:
combine_signals(lgbm_pred: dict, chronos_pred: dict, regime: str) -> dict:

Logic:
- Start with LightGBM probability as base (weight: 0.6)
- Chronos directional signal adjusts it (weight: 0.3):
  * If chronos direction matches LightGBM direction: boost confidence
  * If contradicts: reduce confidence
- Market regime adjusts final score (weight: 0.1):
  * Bull regime: slight upward bias to all predictions
  * Bear regime: slight downward bias
  * Sideways: no adjustment
- Return dict: {
    ticker,
    final_probability_up: float,
    final_direction: "bullish"/"bearish",
    final_confidence: float,
    signal_sources: ["lgbm", "chronos", "regime"],
    signals_agree: bool (True if all three point same direction),
    ml_only_signal: True  (flag that this is pure ML, no news)
  }

Also create:
combine_with_news_signal(ml_signal: dict, news_signal: dict) -> dict:
- Takes the ML combined signal and adds news agent signal
- News signals from agents have: direction, severity, confidence
- If news and ML agree: increase final confidence
- If news and ML disagree: reduce confidence, flag as "conflicting signals"
- Severity modifier: major news overrides ML signal if confidence > 0.8
- Return final merged signal with full reasoning


FILE 2: ml/backtesting.py

Import: vectorbt as vbt, pandas, numpy

Create function:
run_backtest(predictions_df: pd.DataFrame, price_df: pd.DataFrame) -> dict:

Parameters:
- predictions_df: historical predictions with columns [date, ticker, predicted_direction, confidence]
- price_df: historical closing prices for all stocks

Logic:
1. Convert predictions to entry/exit signals
   - Only trade signals where confidence > CONFIDENCE_THRESHOLD (0.55)
   - Long when predicted_direction == "bullish"
   - Flat (no position) when bearish or low confidence

2. Apply transaction costs: 0.1% per side (TRANSACTION_COST from settings)

3. Simulate portfolio with vectorbt:
   - Equal weight across all active positions
   - Rebalance daily at close price

4. Calculate strategy metrics:
   - Sharpe ratio (annualized)
   - Maximum drawdown
   - CAGR
   - Win rate
   - Total return

5. Calculate 5 baseline metrics over same period:
   Baseline 1 - Always predict Up (long all stocks always)
   Baseline 2 - Momentum (if stock rose yesterday, predict up today)
   Baseline 3 - Mean reversion (if rose yesterday, predict down)
   Baseline 4 - Buy and hold NIFTY 50 index
   Baseline 5 - Random signals (use numpy random seed for reproducibility)

6. Return dict: {
    strategy_metrics: {sharpe, max_drawdown, cagr, win_rate, total_return},
    baselines: {
        always_up: {...same metrics},
        momentum: {...},
        mean_reversion: {...},
        buy_and_hold: {...},
        random: {...}
    },
    beats_all_baselines: bool,
    best_performing_stocks: list of top 5 tickers by accuracy,
    worst_performing_stocks: list of bottom 5
  }
```

---

## PART 10 — LangGraph State Definition

```
You are building MarketPulse AI.

Task: Create agents/state.py

This defines the shared state that flows through all 7 LangGraph agent nodes.
Every agent reads from and writes to this state.

Import: TypedDict, List, Dict, Optional, Any from typing
Import: Annotated from typing
Import: add from langgraph's operator utilities

Create the following TypedDict classes:

class NewsArticle(TypedDict):
    id: str                    # MD5 hash of URL for deduplication
    url: str
    title: str
    body: str
    source: str                # "economic_times", "moneycontrol", "reddit", etc
    published_at: str          # ISO format datetime
    fetched_at: str            # when our system got it

class FilteredArticle(TypedDict):
    article: NewsArticle
    passed_blocklist: bool
    passed_ner: bool
    finbert_sentiment: str     # "positive", "negative", "neutral"
    finbert_score: float
    llm_is_relevant: bool
    llm_relevance_reason: str
    relevance_score: float     # 0.0 to 1.0

class MappedImpact(TypedDict):
    article_id: str
    headline: str
    mentioned_companies: List[str]    # direct company mentions
    macro_triggers: List[str]         # crude_oil_spike, rbi_rate_hike etc
    affected_tickers: List[str]       # final list of NIFTY 50 tickers affected
    impact_direction: Dict[str, str]  # {ticker: "bullish"/"bearish"/"neutral"}
    knowledge_source: str             # "direct_mention"/"macro_trigger"/"llm_reasoning"

class ImpactScore(TypedDict):
    ticker: str
    article_id: str
    severity: str              # "minor"/"moderate"/"major"
    direction: str             # "bullish"/"bearish"/"neutral"
    confidence: float          # 0.0 to 1.0
    reasoning: str             # LLM reasoning chain
    historical_precedent: str  # from RAG memory, if found
    timestamp: str

class MLPrediction(TypedDict):
    ticker: str
    lgbm_probability_up: float
    lgbm_direction: str
    chronos_direction: str
    chronos_confidence: float
    market_regime: str
    final_probability_up: float
    final_direction: str
    final_confidence: float
    signals_agree: bool
    top_shap_features: List[Dict]

class FinalSignal(TypedDict):
    ticker: str
    company_name: str
    final_probability_up: float
    final_direction: str
    final_confidence: float
    signal_strength: str       # "strong"/"moderate"/"weak"
    news_signals: List[ImpactScore]
    ml_signal: MLPrediction
    signals_agree: bool        # news and ML agree?
    alert_text: str            # SEBI-compliant alert
    generated_at: str
    valid_for_sessions: int    # how many trading sessions signal is valid

class MarketPulseState(TypedDict):
    # Input
    run_timestamp: str
    run_type: str              # "news_cycle"/"eod_full"/"manual"
    
    # Agent 1 output
    raw_articles: List[NewsArticle]
    articles_fetched_count: int
    
    # Agent 2 output
    filtered_articles: List[FilteredArticle]
    articles_filtered_count: int
    
    # Agent 3 output
    mapped_impacts: List[MappedImpact]
    
    # Agent 4 output
    impact_scores: List[ImpactScore]
    
    # Agent 5 output (Market Monitor)
    current_prices: Dict[str, float]
    price_changes_today: Dict[str, float]
    
    # ML Pipeline output (parallel to agents)
    ml_predictions: List[MLPrediction]
    
    # Agent 6 output
    final_signals: List[FinalSignal]
    
    # Agent 7 output
    alerts: List[str]
    
    # Metadata
    errors: List[str]
    warnings: List[str]
```

---

## PART 11 — Agent 1: News Harvester

```
You are building MarketPulse AI.

Task: Create agents/news_harvester.py

This is the first LangGraph agent node. It collects news from multiple free sources,
deduplicates by URL hash, and stores raw articles.

Import: feedparser, NewsApiClient from newsapi, hashlib, sqlite3, json, datetime
Import: NewsArticle from agents/state.py
Import: MarketPulseState from agents/state.py
Import: settings

Define RSS_FEEDS list with these free Indian financial news feeds:
- "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
- "https://www.moneycontrol.com/rss/MCtopnews.xml"
- "https://www.livemint.com/rss/markets"
- "https://www.business-standard.com/rss/markets-106.rss"
- "https://feeds.feedburner.com/ndtvprofit-latest" 
- "https://economictimes.indiatimes.com/rssfeedsdefault.cms"

Create SQLite deduplication database functions:
init_db() -> None: Create articles table if not exists with columns: 
  id (TEXT PRIMARY KEY), url, title, source, fetched_at

is_duplicate(article_id: str) -> bool: Check if id exists in DB

mark_fetched(article_id: str, url: str, title: str, source: str) -> None: Insert record

Create news fetching functions:
fetch_rss_articles() -> List[NewsArticle]:
    - Loop through RSS_FEEDS
    - Parse with feedparser.parse()
    - For each entry: create MD5 hash of URL as article ID
    - Skip if is_duplicate()
    - Extract: title, link (url), summary (body), published, source from feed URL domain
    - Truncate body to 500 chars (we only need the headline + first paragraph)
    - Call mark_fetched()
    - Return list of NewsArticle dicts

fetch_newsapi_articles() -> List[NewsArticle]:
    - If NEWSAPI_KEY is set:
    - Use NewsApiClient to fetch top-headlines for India, category=business
    - Also search for: "NSE", "NIFTY", "Sensex", "RBI", "SEBI"
    - Same deduplication logic
    - Return List[NewsArticle]
    - If NEWSAPI_KEY not set, return empty list (make this optional)

Main LangGraph node function:
def news_harvester_node(state: MarketPulseState) -> MarketPulseState:
    - Call fetch_rss_articles()
    - Call fetch_newsapi_articles()
    - Combine, deduplicate again (in case of overlap between sources)
    - Update state: state["raw_articles"] = all_articles
    - Update state: state["articles_fetched_count"] = len(all_articles)
    - Log: "Harvested {count} new articles from {n_sources} sources"
    - Return updated state

The node should not crash if one feed fails — wrap each feed fetch in try/except
and add to state["warnings"] if a feed fails.
```

---

## PART 12 — Agent 2: Relevance Filter

```
You are building MarketPulse AI.

Task: Create agents/relevance_filter.py

This is the 4-stage relevance pipeline. Only articles passing ALL stages 
reach the LLM, saving API quota.

Import: re, spacy, transformers pipeline, langchain_groq
Import: KEYWORD_BLOCKLIST, MARKET_RELEVANT_ENTITIES from config/sector_knowledge.py
Import: MarketPulseState, FilteredArticle from agents/state.py
Import: MODEL_SECONDARY (Llama 3.1 8B), GROQ_API_KEY from settings

Initialize at module level (not inside functions — load once):
- nlp = spacy.load("en_core_web_sm")
- finbert = pipeline("text-classification", model="ProsusAI/finbert", 
  device=-1)  # device=-1 means CPU
- groq_llm = ChatGroq(model=MODEL_SECONDARY, api_key=GROQ_API_KEY)

STAGE 1 — Blocklist Filter:
def stage1_blocklist(article: NewsArticle) -> bool:
    - Combine title + body, lowercase
    - Check if ANY word in KEYWORD_BLOCKLIST appears
    - Return False (reject) if match found, True (pass) if clean

STAGE 2 — NER Entity Check:
def stage2_entity_check(article: NewsArticle) -> bool:
    - Run spaCy NER on title + first 300 chars of body
    - Extract all ORG and GPE entities
    - Convert MARKET_RELEVANT_ENTITIES to lowercase set
    - Check if any extracted entity matches market-relevant entities
    - Also check for macro keywords directly: "crude", "rupee", "dollar", 
      "repo rate", "inflation", "GDP", "FII", "DII", "federal reserve"
    - Return True if at least one relevant entity/keyword found

STAGE 3 — FinBERT Sentiment:
def stage3_finbert(article: NewsArticle) -> tuple[str, float]:
    - Run FinBERT on article title (FinBERT works best on short text)
    - Return (label, score): label is "positive"/"negative"/"neutral"
    - If score < 0.6 (low confidence), still pass — neutral news can be relevant

STAGE 4 — LLM Final Check:
def stage4_llm_check(article: NewsArticle) -> tuple[bool, str]:
    - Only called for articles passing stages 1-3
    - Use few-shot prompt with 5 examples of relevant/irrelevant news
    - Ask LLM: "Does this news article have the potential to move Indian stock 
      prices in the next 1-3 trading sessions? Answer with JSON: 
      {is_relevant: true/false, reason: 'brief reason'}"
    - Parse JSON response
    - Return (is_relevant, reason)

Main LangGraph node:
def relevance_filter_node(state: MarketPulseState) -> MarketPulseState:
    - Process each article in state["raw_articles"]
    - Run through all 4 stages in order
    - Stop at first failing stage (don't run expensive stages unnecessarily)
    - Build FilteredArticle for each with all stage results
    - Only articles where llm_is_relevant=True go into filtered_articles
    - Update state["filtered_articles"]
    - Update state["articles_filtered_count"]
    - Log: "Filtered {input} → {output} relevant articles 
      (Stage1: {n1} removed, Stage2: {n2}, Stage3: {n3}, Stage4: {n4})"
    - Return state
```

---

## PART 13 — Agent 3: Entity & Sector Mapper

```
You are building MarketPulse AI.

Task: Create agents/entity_mapper.py

This agent maps filtered news to specific NIFTY 50 stocks using both direct 
company mentions AND macro trigger detection via the knowledge graph.

Import: spacy, langchain_groq, json
Import: MACRO_TRIGGERS, TRADE_DEPENDENCY_MAP from config/sector_knowledge.py
Import: COMPANY_TO_TICKER, NIFTY50_STOCKS from config/nifty50_tickers.py
Import: MarketPulseState, MappedImpact, FilteredArticle from agents/state.py
Import: MODEL_SECONDARY, GROQ_API_KEY from settings

Initialize: nlp = spacy.load("en_core_web_sm")

Create these functions:

extract_direct_mentions(text: str) -> List[str]:
    - Run spaCy NER to find ORG entities
    - For each ORG entity, check if it matches any key in COMPANY_TO_TICKER
    - Also do simple string matching against company names in NIFTY50_STOCKS
    - Return list of matched tickers (deduplicated)

detect_macro_triggers(text: str) -> List[str]:
    - text = title + body lowercased
    - Check for each macro trigger pattern:
      * "crude oil" + ("rise"/"up"/"spike"/"high"/"surge") → "crude_oil_price_increase"
      * "crude oil" + ("fall"/"down"/"drop"/"low"/"decline") → "crude_oil_price_decrease"
      * "rupee" + ("weaken"/"depreciat"/"fall"/"low") → "rupee_depreciation"
      * "rupee" + ("strengthen"/"appreciat"/"rise"/"high") → "rupee_appreciation"
      * "repo rate" or "rbi rate" + ("hike"/"increase"/"raise") → "rbi_rate_hike"
      * "repo rate" + ("cut"/"decrease"/"lower"/"reduce") → "rbi_rate_cut"
      * "federal reserve" or "fed rate" + ("hike"/"increase"/"raise") → "us_fed_rate_hike"
      * "fii" + ("sell"/"outflow"/"exit") → "fii_selloff"
      * "fii" + ("buy"/"inflow"/"invest") → "fii_buying"
      * "india" + "china" + ("tension"/"border"/"conflict"/"dispute") → "india_china_tension"
      * "gdp" + ("growth"/"strong"/"beat"/"exceed") → "india_gdp_strong"
      * "sanction" + any country name → "us_sanctions_on_country"
      * "budget" + ("capex"/"infrastructure"/"spending") → "budget_announcement_capex"
      * "coal" + ("price"/"rise"/"spike") → "coal_price_rise"
    - Return list of detected trigger names

lookup_affected_stocks(triggers: List[str], direct_mentions: List[str]) -> Dict[str, str]:
    - For each trigger, look up MACRO_TRIGGERS[trigger]
    - Get bullish and bearish stock lists
    - Merge with direct_mentions (direct mentions take priority)
    - Return dict: {ticker: "bullish"/"bearish"/"unknown"}

Main LangGraph node:
def entity_mapper_node(state: MarketPulseState) -> MarketPulseState:
    - For each article in state["filtered_articles"]:
      * Extract direct company mentions
      * Detect macro triggers  
      * Lookup affected stocks from knowledge graph
      * If no stocks found from above, use LLM as last resort:
        Ask: "Which NIFTY 50 companies are affected by: {headline}? 
        Return JSON: {ticker: direction}"
        Pass the NIFTY50_STOCKS list as context
      * Create MappedImpact object
    - Update state["mapped_impacts"]
    - Log summary of how many stocks affected per article
    - Return state
```

---

## PART 14 — Agent 4: Impact Scorer + Agent 5: Market Monitor

```
You are building MarketPulse AI.

Task: Create agents/impact_scorer.py and agents/market_monitor.py

FILE 1: agents/impact_scorer.py

This agent assesses severity and confidence of each stock-news pair.
It also queries ChromaDB for historical precedents.

Import: langchain_groq, chromadb, sentence_transformers
Import: MODEL_PRIMARY (Llama 3.3 70B — complex reasoning)
Import: MarketPulseState, MappedImpact, ImpactScore from agents/state.py

Initialize:
- groq_llm = ChatGroq(model=MODEL_PRIMARY, api_key=GROQ_API_KEY)
- chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
- embedder = SentenceTransformer("all-MiniLM-L6-v2")
- collection = chroma_client.get_or_create_collection("news_impact_history")

Create:
query_historical_precedent(headline: str, ticker: str) -> str:
    - Embed the headline
    - Query ChromaDB for similar past headlines affecting same ticker
    - If found (similarity > 0.8): return "Historical precedent: [past headline] 
      resulted in [actual_outcome] for {ticker}"
    - If not found: return "No close historical precedent found"

store_outcome(headline: str, ticker: str, predicted_direction: str, 
              actual_outcome: str, confidence: float) -> None:
    - Store in ChromaDB with metadata for future RAG queries
    - Called by Market Monitor after outcomes are known

score_impact(mapped_impact: MappedImpact) -> List[ImpactScore]:
    - For each (ticker, direction) in mapped_impact:
      * Query historical precedent
      * Build prompt with: headline, ticker, sector info, historical precedent,
        MACRO_TRIGGERS context if applicable
      * Ask LLM: "Rate the severity (minor/moderate/major) and confidence (0-1) 
        of this news impact on {ticker}. Output JSON: 
        {severity, confidence, reasoning}"
      * Create ImpactScore object
    - Return list of ImpactScore objects

Main LangGraph node:
def impact_scorer_node(state: MarketPulseState) -> MarketPulseState:
    - Batch process: group mapped_impacts by ticker 
      (one stock may have multiple news items)
    - Score each impact
    - Update state["impact_scores"]
    - Return state


FILE 2: agents/market_monitor.py

This tracks live prices and validates previous predictions.

Import: yfinance, datetime, sqlite3
Import: MarketPulseState from agents/state.py
Import: NIFTY50_STOCKS from config/nifty50_tickers.py

Create:
fetch_current_prices() -> Dict[str, float]:
    - Use yfinance to fetch latest closing price for all 50 tickers
    - yf.download(tickers_list, period="2d", auto_adjust=True)["Close"]
    - Return dict: {ticker: current_close_price}

calculate_daily_changes(prices: Dict[str, float]) -> Dict[str, float]:
    - Fetch 2 days of data
    - Calculate percentage change: (today - yesterday) / yesterday * 100
    - Return dict: {ticker: pct_change}

validate_previous_predictions(current_prices: Dict[str, float]) -> None:
    - Load yesterday's predictions from SQLite
    - Compare predicted_direction vs actual price change
    - Update outcome in DB
    - Call store_outcome() in impact_scorer to update ChromaDB RAG memory
    - Log accuracy metrics

detect_fo_expiry_today() -> bool:
    - Check if today is last Thursday of the month
    - Return True if F&O expiry day (affects signal reliability)

Main LangGraph node:
def market_monitor_node(state: MarketPulseState) -> MarketPulseState:
    - Call validate_previous_predictions() (learns from past)
    - Call fetch_current_prices()
    - Call calculate_daily_changes()
    - Check for F&O expiry — if True, add warning to state
    - Update state["current_prices"] and state["price_changes_today"]
    - Return state
```

---

## PART 15 — Agent 6: Signal Aggregator + Agent 7: Alert Generator

```
You are building MarketPulse AI.

Task: Create agents/signal_aggregator.py and agents/alert_generator.py

FILE 1: agents/signal_aggregator.py

This is the most important agent — combines all signals into final predictions.
Uses Llama 3.3 70B (most capable model) for the final reasoning step.

Import: langchain_groq, json, datetime
Import: MODEL_PRIMARY from settings
Import: MarketPulseState, FinalSignal from agents/state.py
Import: combine_signals, combine_with_news_signal from ml/signal_combiner.py

Create:
aggregate_stock_signals(
    ticker: str,
    news_impact_scores: List[ImpactScore],
    ml_prediction: MLPrediction,
    current_price: float
) -> FinalSignal:

Logic:
1. From news side: if multiple news items affect same stock:
   - Weight by recency (newer news = higher weight)
   - Weight by severity (major > moderate > minor)
   - Weight by confidence
   - Aggregate to single news direction + confidence

2. Combine with ML signal using combine_with_news_signal()

3. Only if combined confidence > CONFIDENCE_THRESHOLD (0.55):
   Use Groq 70B for final reasoning step:
   Prompt: "Given these signals for {ticker} ({company_name}):
   - News signals: {news_summary}
   - ML prediction: {ml_direction} with {ml_confidence} confidence  
   - Market regime: {regime}
   - Top ML features: {shap_features}
   Provide a final assessment: JSON {
     final_direction, final_confidence, reasoning_chain, 
     key_risk_factors, valid_for_sessions
   }"

4. Create FinalSignal object with all data

5. If confidence below threshold: create FinalSignal with 
   signal_strength="insufficient_data"

Main LangGraph node:
def signal_aggregator_node(state: MarketPulseState) -> MarketPulseState:
    - Collect all tickers that have either news signals or ML predictions
    - For each ticker, call aggregate_stock_signals()
    - Sort by confidence (highest first)
    - Update state["final_signals"]
    - Return state


FILE 2: agents/alert_generator.py

Generates SEBI-compliant, human-readable alert text for the dashboard.

CRITICAL RULE: Never use words "buy", "sell", "invest", "recommend", 
"purchase", "acquire" anywhere in alert text. Use signal intelligence language.

Create:
format_signal_text(signal: FinalSignal) -> str:
    - Template based on direction and confidence:
    
    For bullish strong signal:
    "⬆ BULLISH SIGNAL — {ticker} ({company_name})
    Probability of upward movement: {prob_up:.0%}
    Signal strength: Strong | Corroborating signals: {n_signals}
    Key drivers: {top_2_shap_features}
    News catalyst: {news_headline if present}
    Valid for: Next {valid_sessions} trading session(s)
    Confidence: {confidence_bar}"  ← use ████░░ style bar
    
    For bearish: similar but "⬇ BEARISH SIGNAL"
    For weak: "⟷ WEAK SIGNAL — Insufficient conviction"
    For conflicting: "⚡ CONFLICTING SIGNALS — News and technical indicators diverge"
    
    Confidence bar: 
    0.55-0.65 → "██░░░░ Moderate"
    0.65-0.75 → "████░░ High"  
    0.75+ → "██████ Very High"

format_disclaimer() -> str:
    - Return fixed disclaimer text:
    "⚠ RESEARCH DISCLAIMER: MarketPulse AI is a student research project for 
    educational and informational purposes only. Signals are statistical 
    indicators, not investment advice. We are not SEBI-registered investment 
    advisors. Do not use these signals for actual trading decisions. 
    Past signal accuracy does not guarantee future results."

Main LangGraph node:
def alert_generator_node(state: MarketPulseState) -> MarketPulseState:
    - For each signal in state["final_signals"]:
      * Call format_signal_text()
      * Add to signal object as alert_text field
    - Store all signals to SQLite predictions table with timestamp
    - Update state["alerts"] with list of formatted alert texts
    - Log: "Generated {n} signals: {n_bullish} bullish, {n_bearish} bearish"
    - Return state
```

---

## PART 16 — LangGraph Full Graph Orchestration

```
You are building MarketPulse AI.

Task: Create agents/graph.py — this wires all 7 agents into the LangGraph graph.

Import: StateGraph, END from langgraph.graph
Import all 7 node functions from their respective files
Import: MarketPulseState from agents/state.py

Create the graph:

def create_marketpulse_graph():
    
    # Initialize graph with our state
    graph = StateGraph(MarketPulseState)
    
    # Add all 7 nodes
    graph.add_node("news_harvester", news_harvester_node)
    graph.add_node("relevance_filter", relevance_filter_node)
    graph.add_node("entity_mapper", entity_mapper_node)
    graph.add_node("impact_scorer", impact_scorer_node)
    graph.add_node("market_monitor", market_monitor_node)
    graph.add_node("signal_aggregator", signal_aggregator_node)
    graph.add_node("alert_generator", alert_generator_node)
    
    # Define the flow
    graph.set_entry_point("news_harvester")
    
    # News pipeline chain
    graph.add_edge("news_harvester", "relevance_filter")
    
    # Conditional edge after relevance filter:
    # If no relevant articles found, skip to market_monitor (still need ML signals)
    def check_has_articles(state: MarketPulseState) -> str:
        if len(state.get("filtered_articles", [])) == 0:
            return "skip_to_monitor"
        return "continue_to_mapper"
    
    graph.add_conditional_edges(
        "relevance_filter",
        check_has_articles,
        {
            "continue_to_mapper": "entity_mapper",
            "skip_to_monitor": "market_monitor"
        }
    )
    
    graph.add_edge("entity_mapper", "impact_scorer")
    graph.add_edge("impact_scorer", "market_monitor")
    graph.add_edge("market_monitor", "signal_aggregator")
    graph.add_edge("signal_aggregator", "alert_generator")
    graph.add_edge("alert_generator", END)
    
    return graph.compile()

# Create the compiled graph (singleton)
marketpulse_graph = create_marketpulse_graph()

Create runner function:
def run_pipeline(run_type: str = "news_cycle", ml_predictions: list = None) -> dict:
    """
    run_type: "news_cycle" (every 30 min), "eod_full" (daily at 3:45 PM)
    ml_predictions: pass pre-computed ML predictions for eod_full runs
    """
    import datetime
    
    initial_state = MarketPulseState(
        run_timestamp=datetime.datetime.now().isoformat(),
        run_type=run_type,
        raw_articles=[],
        articles_fetched_count=0,
        filtered_articles=[],
        articles_filtered_count=0,
        mapped_impacts=[],
        impact_scores=[],
        current_prices={},
        price_changes_today={},
        ml_predictions=ml_predictions or [],
        final_signals=[],
        alerts=[],
        errors=[],
        warnings=[]
    )
    
    result = marketpulse_graph.invoke(initial_state)
    return result

Also add LangSmith tracing setup at the top of this file:
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "marketpulse-ai"
(These will activate automatically if LANGCHAIN_API_KEY is in .env)
```

---

## PART 17 — EOD Pipeline + Scheduler

```
You are building MarketPulse AI.

Task: Create pipeline/eod_pipeline.py and pipeline/scheduler.py

FILE 1: pipeline/eod_pipeline.py

This runs every day at 3:45 PM IST — after market close.
It runs the full ML pipeline first, then passes results to agents.

Import: predict_all_stocks from ml/predictor.py
Import: ChronosForecaster from ml/chronos_forecaster.py
Import: MarketRegimeDetector from ml/regime_detector.py
Import: combine_signals from ml/signal_combiner.py
Import: update_all_stocks_daily from ml/data_collector.py
Import: engineer_all_stocks from ml/feature_engineering.py
Import: run_pipeline from agents/graph.py
Import: joblib, datetime, logging

def run_eod_pipeline():
    logger.info("=== EOD Pipeline Started ===")
    
    Step 1: Update price data
    logger.info("Step 1: Updating price data...")
    update_all_stocks_daily()
    
    Step 2: Re-engineer features
    logger.info("Step 2: Engineering features...")
    engineer_all_stocks()  
    
    Step 3: Load regime model and get current regime
    logger.info("Step 3: Detecting market regime...")
    regime_model = MarketRegimeDetector()
    regime_model.load(DATA_DIR/models/regime_model.pkl)
    # Load NIFTY50 index data and get current regime
    current_regime = regime_model.get_current_regime(nifty_close_series)
    
    Step 4: LightGBM predictions for all stocks
    logger.info("Step 4: Running LightGBM predictions...")
    lgbm_predictions = predict_all_stocks()
    
    Step 5: Chronos predictions for all stocks
    logger.info("Step 5: Running Chronos forecasts...")
    chronos = ChronosForecaster()
    chronos_preds = chronos.forecast_all_stocks(price_data_dict)
    
    Step 6: Combine ML signals
    logger.info("Step 6: Combining ML signals...")
    ml_signals = []
    for pred in lgbm_predictions:
        ticker = pred["ticker"]
        chronos_pred = chronos_preds.get(ticker, {})
        combined = combine_signals(pred, chronos_pred, current_regime)
        ml_signals.append(combined)
    
    Step 7: Run agent pipeline with ML signals
    logger.info("Step 7: Running agent pipeline...")
    result = run_pipeline(run_type="eod_full", ml_predictions=ml_signals)
    
    logger.info(f"=== EOD Pipeline Complete: {len(result['final_signals'])} signals generated ===")
    return result

def run_monthly_retrain():
    from ml.predictor import train_all_models
    from ml.regime_detector import fit_and_save_all_regime_models
    logger.info("=== Monthly Retraining Started ===")
    fit_and_save_all_regime_models()
    train_all_models(optimize=False)  # optimize=True takes too long monthly
    logger.info("=== Monthly Retraining Complete ===")


FILE 2: pipeline/scheduler.py

This runs everything on a schedule during development (on your laptop).
For production, GitHub Actions replaces this.

Import: APScheduler (BackgroundScheduler), pytz
Import: run_pipeline from agents/graph.py
Import: run_eod_pipeline, run_monthly_retrain from pipeline/eod_pipeline.py
Import: datetime

def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    
    # News pipeline: every 30 minutes during market hours (9 AM to 6 PM IST)
    scheduler.add_job(
        func=lambda: run_pipeline("news_cycle"),
        trigger="cron",
        hour="9-18",
        minute="*/30",
        id="news_pipeline"
    )
    
    # EOD pipeline: daily at 3:45 PM IST (15 min after market close)
    scheduler.add_job(
        func=run_eod_pipeline,
        trigger="cron",
        hour=15,
        minute=45,
        id="eod_pipeline"
    )
    
    # Monthly retraining: 1st of every month at 8 PM IST
    scheduler.add_job(
        func=run_monthly_retrain,
        trigger="cron",
        day=1,
        hour=20,
        minute=0,
        id="monthly_retrain"
    )
    
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to stop.")
    return scheduler

if __name__ == "__main__":
    scheduler = start_scheduler()
    try:
        while True:
            import time
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
```

---

## PART 18 — Streamlit Dashboard

```
You are building MarketPulse AI.

Task: Create dashboard/app.py and all pages in dashboard/pages/

The dashboard reads from SQLite (predictions, signals, outcomes) and 
displays everything in a clean, professional interface.

FILE 1: dashboard/app.py (Main entry point)

Import: streamlit, sqlite3, pandas, plotly.express, datetime

Page config:
st.set_page_config(
    page_title="MarketPulse AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

Main page shows:
1. Header: "MarketPulse AI — NIFTY 50 Signal Intelligence"
   Subtitle: "Research prototype · Educational purposes only"

2. SEBI Disclaimer banner at the top (red/orange background):
   Show the full disclaimer from alert_generator.format_disclaimer()
   Make this dismissible but always visible on first load

3. Market Status indicator: 
   - Green "Market Open" between 9:15 AM and 3:30 PM IST weekdays
   - Grey "Market Closed" otherwise
   - Show current IST time

4. Summary stats row (4 columns):
   - Total signals today
   - Bullish signals count
   - Bearish signals count  
   - Last pipeline run time

5. Quick view: Top 5 highest confidence signals as cards

6. Navigation sidebar pointing to 4 pages

FILE 2: dashboard/pages/1_predictions.py

Full predictions page:
- Filter bar: All / Bullish / Bearish / Strong only / By sector
- Signal cards in a grid (2 columns):
  Each card shows: ticker, company name, direction arrow, probability bar, 
  confidence, signal strength badge, top news catalyst (if any), 
  top 2 SHAP features, timestamp
- Color coding: green border = bullish, red border = bearish, 
  grey = weak/insufficient

FILE 3: dashboard/pages/2_news_signals.py

News intelligence page:
- Timeline of all relevant articles processed today
- For each article: headline, source, timestamp, 
  which stocks affected, relevance score
- Expandable: full relevance filter pipeline results 
  (passed stage 1? stage 2? etc — show the filter journey)
- Macro triggers detected today (e.g. "Crude oil trigger detected — 
  affected 4 stocks")

FILE 4: dashboard/pages/3_backtesting.py

Backtesting results page:
- Date range selector
- Main strategy metrics table vs 5 baselines:
  Columns: Strategy Name | Accuracy | Sharpe Ratio | Max Drawdown | CAGR | Win Rate
  Highlight your strategy row
- Equity curve chart (plotly line chart) showing portfolio value over time
  vs NIFTY 50 buy and hold benchmark
- Per-stock accuracy heatmap (which stocks model handles best)
- Walk-forward validation results chart

FILE 5: dashboard/pages/4_model_performance.py

Live accuracy tracking:
- Rolling 30-day directional accuracy chart per model (LightGBM, Chronos, Combined)
- Calibration plot: predicted probability vs actual hit rate
  (well-calibrated model should have 65% prediction → 65% accuracy)
- Confusion matrix
- Recent predictions vs outcomes table (last 20 predictions)
- System health: last run time, API status, model last retrained date

Style notes:
- Dark theme preferred (use st.set_page_config with "dark" theme in config)  
- Use plotly charts (not matplotlib) — they're interactive
- Show loading spinners when fetching data
- Cache database queries with @st.cache_data(ttl=300) — refresh every 5 min
- Mobile responsive layout
```

---

## PART 19 — GitHub Actions (Production Scheduler)

```
You are building MarketPulse AI.

Task: Create .github/workflows/agent_pipeline.yml

This GitHub Actions workflow replaces APScheduler for production.
It runs the agent pipeline on schedule using GitHub's free cloud servers.

Create the YAML workflow file with:

name: MarketPulse AI Pipeline

Triggers:
- Schedule: cron for 30-minute intervals during India market hours
  India market hours in UTC: 3:45 AM to 10:30 AM UTC (= 9:15 AM to 4 PM IST)
  Run at minutes 0 and 30 of each hour, hours 3-10 UTC, Monday to Friday
  Also add a schedule for EOD pipeline at 10:15 AM UTC (= 3:45 PM IST)
- workflow_dispatch: (allow manual trigger from GitHub UI)

Jobs:

Job 1: news_pipeline
  runs-on: ubuntu-latest
  if: condition to check current time is between 3:45 AM UTC and 10:30 AM UTC
  
  Steps:
  - Checkout repository
  - Set up Python 3.11
  - Cache pip dependencies (cache key based on requirements.txt hash)
  - Install dependencies: pip install -r requirements.txt
  - Download spacy model: python -m spacy download en_core_web_sm
  - Run pipeline: python -c "from agents.graph import run_pipeline; run_pipeline('news_cycle')"
  
  Environment variables (from GitHub Secrets):
  GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  NEWSAPI_KEY: ${{ secrets.NEWSAPI_KEY }}
  LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
  LANGCHAIN_TRACING_V2: "true"
  LANGCHAIN_PROJECT: "marketpulse-ai-prod"
  
  Note: SQLite won't persist between GitHub Actions runs. 
  For production, switch to Supabase — add SUPABASE_URL and SUPABASE_KEY 
  to secrets and modify data access layer to use Supabase instead of SQLite.
  
Job 2: eod_pipeline  
  runs-on: ubuntu-latest
  Schedule: only at 10:15 AM UTC (3:45 PM IST), Monday to Friday
  Steps: same as above but run eod_pipeline:
  python -c "from pipeline.eod_pipeline import run_eod_pipeline; run_eod_pipeline()"

Add a README section explaining:
"Add these secrets in GitHub repo Settings → Secrets and variables → Actions:
GROQ_API_KEY, GEMINI_API_KEY, NEWSAPI_KEY, LANGSMITH_API_KEY"
```

---

## PART 20 — Initial Data Setup + Integration Test

```
You are building MarketPulse AI.

Task: Create a setup script and integration test.

FILE 1: setup.py (one-time setup script, run before anything else)

Create a script that:
1. Checks all API keys are set in .env (warn but don't fail for optional ones)
2. Creates all data directories if they don't exist
3. Downloads spaCy model: os.system("python -m spacy download en_core_web_sm")
4. Downloads FinBERT model (trigger the HuggingFace download):
   from transformers import pipeline
   pipeline("text-classification", model="ProsusAI/finbert")
5. Fetches all NIFTY 50 historical data: 
   from ml.data_collector import fetch_all_nifty50
   fetch_all_nifty50()  ← This takes 5-10 minutes, that's fine
6. Runs feature engineering:
   from ml.feature_engineering import engineer_all_stocks
   engineer_all_stocks()
7. Fits and saves regime model:
   from ml.regime_detector import fit_and_save_all_regime_models
   fit_and_save_all_regime_models()
8. Trains all LightGBM models (this takes 10-15 minutes):
   from ml.predictor import train_all_models
   train_all_models(optimize=False)
9. Runs backtesting and saves results:
   from ml.backtesting import run_backtest
   (load historical predictions or use walk-forward results)
10. Prints setup complete summary with all model accuracy scores

FILE 2: test_pipeline.py (quick integration test)

Create a test that verifies the full pipeline works end-to-end with mock data:

def test_news_harvester():
    from agents.graph import run_pipeline
    result = run_pipeline("news_cycle")
    assert "final_signals" in result
    assert "errors" in result
    print(f"✅ Pipeline ran. Signals: {len(result['final_signals'])}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
    return result

def test_ml_pipeline():
    from ml.predictor import predict_all_stocks
    predictions = predict_all_stocks()
    assert len(predictions) > 0
    print(f"✅ ML Pipeline ran. Predictions for {len(predictions)} stocks")
    sample = predictions[0]
    print(f"Sample: {sample['ticker']} → {sample['predicted_direction']} "
          f"({sample['probability_up']:.2%} confidence)")
    return predictions

def test_single_agent():
    # Test just Agent 1 in isolation
    from agents.news_harvester import news_harvester_node
    from agents.state import MarketPulseState
    state = {key: [] for key in MarketPulseState.__annotations__}
    state["run_timestamp"] = "test"
    state["run_type"] = "test"
    result = news_harvester_node(state)
    print(f"✅ Harvester: fetched {result['articles_fetched_count']} articles")

if __name__ == "__main__":
    print("Running MarketPulse AI integration tests...")
    test_single_agent()
    test_ml_pipeline()
    test_news_harvester()
    print("\n✅ All tests passed. System ready.")
```

---

## PART 21 — Deployment to Streamlit Community Cloud

```
You are building MarketPulse AI.

Task: Prepare the project for deployment on Streamlit Community Cloud (free).

The Streamlit app (dashboard/) is what gets deployed.
The agent pipeline runs on GitHub Actions separately.
They share data through Supabase (free PostgreSQL).

Step 1: Create streamlit_app.py in project root
This is the entry point Streamlit Community Cloud looks for:
Just import and run the dashboard:
  import subprocess
  import sys
  sys.path.insert(0, ".")
  from dashboard.app import *

Step 2: Create .streamlit/config.toml
Content:
[theme]
base = "dark"
primaryColor = "#00D4AA"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1C2333"
textColor = "#FAFAFA"

[server]
maxUploadSize = 50

Step 3: Update dashboard to use Supabase instead of SQLite
In all dashboard pages, replace SQLite queries with Supabase client:
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Instead of: conn.execute("SELECT * FROM predictions")
# Use: supabase.table("predictions").select("*").execute()

Create the Supabase tables (provide SQL to run in Supabase dashboard):
CREATE TABLE predictions (
    id TEXT PRIMARY KEY,
    ticker TEXT,
    company_name TEXT,
    final_direction TEXT,
    probability_up REAL,
    confidence REAL,
    signal_strength TEXT,
    alert_text TEXT,
    reasoning TEXT,
    generated_at TIMESTAMP,
    run_type TEXT
);

CREATE TABLE news_signals (
    id TEXT PRIMARY KEY,
    headline TEXT,
    source TEXT,
    ticker TEXT,
    direction TEXT,
    severity TEXT,
    confidence REAL,
    processed_at TIMESTAMP
);

CREATE TABLE prediction_outcomes (
    prediction_id TEXT,
    ticker TEXT,
    predicted_direction TEXT,
    actual_direction TEXT,
    was_correct BOOLEAN,
    outcome_date DATE
);

Step 4: Deployment instructions (add to README):
"Deploy to Streamlit Community Cloud:
1. Push all code to GitHub (public repo)
2. Go to share.streamlit.io
3. Connect your GitHub repo
4. Set Main file path: streamlit_app.py
5. Add secrets in Streamlit dashboard:
   GROQ_API_KEY, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY, LANGSMITH_API_KEY
6. Deploy"

Step 5: Verify requirements.txt has all dependencies
Streamlit Community Cloud reads requirements.txt for pip installs.
Make sure versions are pinned for the most critical libraries:
langchain==0.3.x, langgraph==0.2.x, lightgbm==4.x, streamlit==1.x
```

---

---

# FINAL CHECKLIST — Before Showing to Recruiters

- [ ] All 7 agents run without errors end-to-end
- [ ] ML models trained on all 50 stocks (check data/models/ has 50 .pkl files)
- [ ] Backtesting results show comparison vs all 5 baselines
- [ ] Dashboard deployed on Streamlit Community Cloud with public URL
- [ ] SEBI disclaimer visible on every page
- [ ] LangSmith showing agent traces (proof the agents are running)
- [ ] README has: architecture diagram, tech stack, live demo link, 
      accuracy numbers, and explanation of each agent
- [ ] GitHub repo is public with clean commit history
- [ ] GitHub Actions workflow is enabled and showing successful runs

---

# IMPORTANT: ORDER TO RUN THESE PARTS

1. PART 1 → Create project structure
2. PART 2 → Config: settings + tickers
3. PART 3 → Config: knowledge base (spend time here — most important)
4. PART 4 → ML data collection
5. PART 5 → Feature engineering
6. PART 6 → HMM regime detector
7. PART 7 → LightGBM predictor
8. PART 8 → Chronos + Signal combiner + Backtesting
9. **Run setup.py here → downloads data and trains all models**
10. PART 10 → LangGraph state
11. PART 11 → Agent 1 (Harvester)
12. PART 12 → Agent 2 (Filter)
13. PART 13 → Agent 3 (Mapper)
14. PART 14 → Agents 4 + 5
15. PART 15 → Agents 6 + 7
16. PART 16 → LangGraph graph
17. **Run test_pipeline.py here → verify everything connects**
18. PART 17 → Streamlit dashboard
19. PART 18 → EOD pipeline + Scheduler
20. PART 19 → GitHub Actions
21. PART 20 → Setup script + Integration tests
22. PART 21 → Deployment

---

*MarketPulse AI Development Blueprint — Generated for Gagan Diwakar*
*Project: NIFTY 50 Multi-Agent Signal Intelligence System*
