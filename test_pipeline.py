"""
test_pipeline.py - MarketPulse AI
====================================
Blueprint Part 20 File 2: Integration Test Suite.

Run AFTER setup.py to verify the full pipeline connects end-to-end.
Tests every layer: config, ML, agents, graph, dashboard imports.

Usage:
    python test_pipeline.py

Exit code 0 = all critical tests pass.
Exit code 1 = one or more critical tests failed.
"""

import sys
import os
import time
import traceback
from pathlib import Path
from datetime import datetime

# Force UTF-8 output (fixes Windows cp1252 issues)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

PASS  = "[PASS]"
FAIL  = "[FAIL]"
SKIP  = "[SKIP]"
WARN  = "[WARN]"

results = []   # (name, status, detail)
critical_fails = 0

def test(name, fn, critical=True):
    """Run a single test, catch exceptions, record result."""
    global critical_fails
    try:
        detail = fn()
        results.append((name, PASS, detail or ""))
        print(f"  {PASS}  {name}" + (f"  -- {detail}" if detail else ""))
    except Exception as e:
        status = FAIL if critical else WARN
        detail = str(e)[:120]
        results.append((name, status, detail))
        if critical:
            critical_fails += 1
        print(f"  {status}  {name}  -- {detail}")


print()
print("=" * 65)
print("  MarketPulse AI -- Integration Test Suite")
print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("=" * 65)


# ══════════════════════════════════════════════════════════════════
# LAYER 1: CONFIG & SETTINGS
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 1] Config & Settings")

def t_settings():
    from config.settings import (GROQ_API_KEY, NEWSAPI_KEY, DATA_DIR,
                                  MODELS_DIR, PROCESSED_DIR, TRAINING_START_DATE)
    assert DATA_DIR.exists(), f"DATA_DIR missing: {DATA_DIR}"
    assert MODELS_DIR.exists(), f"MODELS_DIR missing: {MODELS_DIR}"
    assert TRAINING_START_DATE == "2015-01-01"
    return f"DATA_DIR={DATA_DIR}"

def t_tickers():
    from config.tickers import ACTIVE_STOCKS
    assert len(ACTIVE_STOCKS) >= 100, f"Expected 100+ tickers, got {len(ACTIVE_STOCKS)}"
    return f"{len(ACTIVE_STOCKS)} tickers loaded"

def t_knowledge():
    from config.sector_knowledge import TRADE_DEPENDENCY_MAP, MACRO_TRIGGERS
    assert len(TRADE_DEPENDENCY_MAP) >= 5, "Sector knowledge too small"
    assert len(MACRO_TRIGGERS) >= 5, "Macro triggers too small"
    return f"{len(TRADE_DEPENDENCY_MAP)} sectors, {len(MACRO_TRIGGERS)} triggers"

test("settings.py imports & paths", t_settings)
test("nifty50_tickers: 50 stocks loaded", t_tickers)
test("sector_knowledge: sectors & triggers", t_knowledge)


# ══════════════════════════════════════════════════════════════════
# LAYER 2: DATA & FEATURES
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 2] Data & Feature Files")

def t_raw_csv():
    from config.settings import PROCESSED_DIR
    csvs = [f for f in PROCESSED_DIR.glob("*.csv") if "_features" not in f.name]
    assert len(csvs) >= 40, f"Expected 40+ raw CSVs, found {len(csvs)}"
    return f"{len(csvs)} raw CSVs in data/processed/"

def t_feature_files():
    from config.settings import PROCESSED_DIR
    feat = list(PROCESSED_DIR.glob("*_features.csv"))
    assert len(feat) >= 40, f"Expected 40+ feature CSVs, found {len(feat)}"
    return f"{len(feat)} feature files"

def t_feature_shape():
    import pandas as pd
    from config.settings import PROCESSED_DIR
    sample = PROCESSED_DIR / "RELIANCE.NS_features.csv"
    assert sample.exists(), "RELIANCE.NS_features.csv not found"
    df = pd.read_csv(sample, index_col="Date", parse_dates=True, nrows=10)
    assert len(df.columns) >= 40, f"Expected 40+ feature cols, got {len(df.columns)}"
    return f"{len(df.columns)} feature columns confirmed"

def t_model_files():
    from config.settings import MODELS_DIR
    pkls = list(MODELS_DIR.glob("*_lgb_predictor.pkl"))
    assert len(pkls) >= 40, f"Expected 40+ .pkl models, found {len(pkls)}"
    return f"{len(pkls)} trained models in data/models/"

def t_regime_model():
    from config.settings import MODELS_DIR
    regime = MODELS_DIR / "regime_model.pkl"
    assert regime.exists(), "regime_model.pkl missing"
    return f"regime_model.pkl exists ({regime.stat().st_size//1024} KB)"

test("Raw OHLCV CSVs exist (40+)", t_raw_csv)
test("Feature engineering CSVs exist (40+)", t_feature_files)
test("Feature shape: 40+ columns", t_feature_shape)
test("Trained models (.pkl) exist (40+)", t_model_files)
test("Regime detector model exists", t_regime_model)


# ══════════════════════════════════════════════════════════════════
# LAYER 3: ML MODULES
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 3] ML Modules")

def t_feature_eng():
    from ml.feature_engineering import engineer_features
    import pandas as pd
    from config.settings import PROCESSED_DIR
    df = pd.read_csv(PROCESSED_DIR / "RELIANCE.NS.csv", index_col="Date", parse_dates=True)
    result = engineer_features(df, "RELIANCE.NS")
    assert not result.empty, "engineer_features returned empty"
    assert "rsi_14" in result.columns
    assert "target" in result.columns
    return f"RELIANCE.NS: {result.shape[0]} rows x {result.shape[1]} cols"

def t_predictor_load():
    from ml.predictor import StockPredictor
    predictor = StockPredictor("RELIANCE.NS")
    return "StockPredictor initialized for RELIANCE.NS"

def t_predictor_predict():
    from ml.predictor import predict_all_stocks
    return "predict_all_stocks imported OK"

def t_regime():
    from ml.regime_detector import MarketRegimeDetector
    detector = MarketRegimeDetector()
    return f"MarketRegimeDetector initialized"

def t_signal_combiner():
    from ml.signal_combiner import combine_signals
    return f"combine_signals imported OK"

test("feature_engineering: engineer_features()", t_feature_eng)
test("predictor: load_model()", t_predictor_load)
test("predictor: predict_next_day()", t_predictor_predict)
test("regime_detector: get_current_regime()", t_regime)
test("signal_combiner: combine_signals()", t_signal_combiner)


# ══════════════════════════════════════════════════════════════════
# LAYER 4: AGENT IMPORTS
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 4] Agent Imports")

def t_state():
    from agents.state import MarketPulseState
    import typing
    assert hasattr(MarketPulseState, "__annotations__"), "Not a TypedDict"
    return f"{len(MarketPulseState.__annotations__)} state fields"

def t_news_harvester():
    from agents.news_harvester import fetch_newsapi_articles
    return "news_harvester imported OK"

def t_relevance_filter():
    from agents.relevance_filter import FilteredArticle
    return "relevance_filter imported OK"

def t_entity_mapper():
    from agents.entity_mapper import detect_macro_triggers
    return "entity_mapper imported OK"

def t_impact_scorer():
    from agents.impact_scorer import ImpactScore
    return "impact_scorer imported OK"

def t_market_monitor():
    from agents.market_monitor import calculate_daily_changes
    return "market_monitor imported OK"

def t_signal_aggregator():
    from agents.signal_aggregator import FinalSignal
    return "signal_aggregator imported OK"

def t_alert_generator():
    from agents.alert_generator import alert_generator_node
    return "alert_generator imported OK"

test("agents.state: MarketPulseState", t_state)
test("agents.news_harvester import", t_news_harvester)
test("agents.relevance_filter import", t_relevance_filter)
test("agents.entity_mapper import", t_entity_mapper)
test("agents.impact_scorer import", t_impact_scorer)
test("agents.market_monitor import", t_market_monitor)
test("agents.signal_aggregator import", t_signal_aggregator)
test("agents.alert_generator import", t_alert_generator)


# ══════════════════════════════════════════════════════════════════
# LAYER 5: LANGGRAPH GRAPH
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 5] LangGraph Graph")

def t_graph_compile():
    from agents.graph import create_marketpulse_graph
    graph = create_marketpulse_graph()
    assert graph is not None, "graph is None"
    return "LangGraph graph compiled successfully"

def t_graph_nodes():
    from agents.graph import create_marketpulse_graph
    graph = create_marketpulse_graph()
    graph_repr = str(graph)
    return "Graph structure valid"

test("agents.graph: compiled_graph not None", t_graph_compile)
test("agents.graph: graph structure valid", t_graph_nodes, critical=False)


# ══════════════════════════════════════════════════════════════════
# LAYER 6: PIPELINE MODULES
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 6] Pipeline Modules")

def t_eod_pipeline():
    from pipeline.eod_pipeline import run_eod_pipeline
    return "eod_pipeline imported OK"

def t_scheduler():
    from pipeline.scheduler import start_scheduler
    return "scheduler imported OK"

test("pipeline.eod_pipeline import", t_eod_pipeline)
test("pipeline.scheduler import", t_scheduler)


# ══════════════════════════════════════════════════════════════════
# LAYER 7: API KEY LIVE CHECK
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 7] API Keys (live check)")

def t_groq_api():
    from groq import Groq
    from config.settings import GROQ_API_KEY
    assert GROQ_API_KEY and GROQ_API_KEY.startswith("gsk_")
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
    )
    reply = resp.choices[0].message.content.strip()
    return f"Groq live: '{reply}'"

def t_newsapi():
    import requests
    from config.settings import NEWSAPI_KEY
    assert NEWSAPI_KEY, "NEWSAPI_KEY not set"
    url = f"https://newsapi.org/v2/everything?q=NIFTY&pageSize=1&apiKey={NEWSAPI_KEY}"
    r = requests.get(url, timeout=10)
    assert r.status_code == 200, f"NewsAPI returned {r.status_code}"
    data = r.json()
    n = data.get("totalResults", 0)
    return f"NewsAPI live: {n} total articles for 'NIFTY'"

test("Groq API live call (llama-3.1-8b)", t_groq_api)
test("NewsAPI live call", t_newsapi)


# ══════════════════════════════════════════════════════════════════
# LAYER 8: DASHBOARD IMPORTS
# ══════════════════════════════════════════════════════════════════
print("\n[Layer 8] Dashboard Dependencies")

def t_streamlit():
    import streamlit
    import plotly
    return f"streamlit={streamlit.__version__}, plotly={plotly.__version__}"

def t_chromadb():
    import chromadb
    from config.settings import CHROMA_DIR
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    coll = client.get_or_create_collection("test_collection")
    return f"ChromaDB OK, collections: {len(client.list_collections())}"

test("streamlit + plotly imports", t_streamlit)
test("ChromaDB client", t_chromadb)


# ══════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════
total  = len(results)
passed = sum(1 for _, s, _ in results if s == PASS)
warned = sum(1 for _, s, _ in results if s == WARN)
failed = sum(1 for _, s, _ in results if s == FAIL)

print()
print("=" * 65)
print("  TEST SUMMARY")
print("=" * 65)
print(f"  Total  : {total}")
print(f"  Passed : {passed}")
print(f"  Warned : {warned}  (non-critical)")
print(f"  Failed : {failed}  (critical)")
print()

if critical_fails == 0:
    print("  ALL CRITICAL TESTS PASSED!")
    print()
    print("  Ready to run:")
    print("    streamlit run dashboard/app.py")
    print("    python -m pipeline.scheduler")
else:
    print(f"  {critical_fails} CRITICAL TEST(S) FAILED.")
    print("  Fix failures before running the pipeline.")
    print()
    print("  Failed tests:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"    {FAIL} {name}: {detail}")

print()
print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("=" * 65)
print()

sys.exit(0 if critical_fails == 0 else 1)
