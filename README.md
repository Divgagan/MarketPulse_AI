# MarketPulse AI 🚀

> **An intelligent NIFTY 50 stock signal intelligence system** built with LangGraph agents, LightGBM, Amazon Chronos, and a Streamlit dashboard.

---

## What It Does

MarketPulse AI combines two pipelines:

1. **7 LangGraph Agents** — Monitor financial news 24/7, filter relevant events, map them to NIFTY 50 stocks, and generate calibrated probability signals
2. **3-Layer ML Pipeline** — Uses HMM (market regime) + LightGBM (directional prediction) + Amazon Chronos (time series forecast) for daily stock direction signals

All signals are displayed on a Streamlit dashboard with full SEBI-compliant disclaimers.

> ⚠️ **Disclaimer:** MarketPulse AI is a student research and educational project. It is NOT investment advice. Do not use signals for actual trading decisions.

---

## Architecture

```
News Sources (RSS + NewsAPI)
        ↓
Agent 1: News Harvester
        ↓
Agent 2: Relevance Filter (Blocklist → NER → FinBERT → LLM)
        ↓
Agent 3: Entity & Sector Mapper (knowledge graph)
        ↓
Agent 4: Impact Scorer (LLM + ChromaDB RAG)
        ↓
Agent 5: Market Monitor (live prices + prediction validation)
        ↑
ML Pipeline: LightGBM + Chronos + HMM
        ↓
Agent 6: Signal Aggregator
        ↓
Agent 7: Alert Generator (SEBI-compliant)
        ↓
Streamlit Dashboard
```

---

## Tech Stack

| Purpose | Tool |
|---|---|
| Agent orchestration | LangGraph + LangChain |
| Primary LLM | Groq (Llama 3.3 70B + Llama 3.1 8B) |
| Fallback LLM | Google Gemini Flash 2.0 |
| News relevance | FinBERT (ProsusAI/finbert) |
| NER | spaCy (en_core_web_sm) |
| Market data | yfinance + nsepy |
| Technical indicators | pandas-ta |
| Market regime | hmmlearn (GaussianHMM) |
| Core ML | LightGBM |
| Time series forecast | Amazon Chronos |
| ML explainability | SHAP |
| Backtesting | vectorbt |
| Vector DB | ChromaDB |
| Dashboard | Streamlit |

---

## Setup Instructions

### Prerequisites
- Python 3.10+ (via conda `agentic_env`)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/marketpulse-ai.git
cd marketpulse-ai
```

### 2. Activate Your Conda Environment
```bash
conda activate agentic_env
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Set Up API Keys
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 5. Download Historical Data & Train Models
```bash
python setup.py
```

### 6. Run the Dashboard
```bash
streamlit run dashboard/app.py
```

### 7. (Optional) Run the Scheduler Locally
```bash
python pipeline/scheduler.py
```

---

## Project Structure

```
marketpulse-ai/
├── config/          # API keys, NIFTY 50 tickers, sector knowledge graph
├── agents/          # 7 LangGraph agent nodes + graph orchestration
├── ml/              # ML pipeline: data, features, HMM, LightGBM, Chronos
├── pipeline/        # EOD pipeline + APScheduler
├── dashboard/       # Streamlit app + pages
├── data/            # Raw news, processed features, models, ChromaDB
└── .github/         # GitHub Actions workflow for production scheduling
```

---

## Development Status

| Part | Description | Status |
|---|---|---|
| Part 1 | Project structure + requirements | ✅ Done |
| Part 2 | config/settings.py + nifty50_tickers.py | ⏳ Pending |
| Part 3 | config/sector_knowledge.py | ⏳ Pending |
| Part 4 | ml/data_collector.py | ⏳ Pending |
| Part 5 | ml/feature_engineering.py | ⏳ Pending |
| Part 6 | ml/regime_detector.py | ⏳ Pending |
| Part 7 | ml/predictor.py | ⏳ Pending |
| Part 8 | ml/chronos_forecaster.py + signal_combiner + backtesting | ⏳ Pending |
| Part 9 | setup.py + test_pipeline.py | ⏳ Pending |
| Parts 10–16 | LangGraph agents | ⏳ Pending |
| Parts 17–21 | Dashboard + pipeline + deployment | ⏳ Pending |

---

*Built by a student developer as a learning project in AI-assisted financial signal intelligence.*
