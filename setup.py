"""
setup.py — MarketPulse AI
===========================
Blueprint Part 20 File 1: One-time setup script.

Run ONCE before anything else. Downloads models, fetches historical
data, trains all ML models. Takes ~20-25 minutes on first run.

Usage:
    python setup.py
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Force UTF-8 output (fixes Windows cp1252 encoding errors)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("MarketPulse AI -- One-Time Setup")
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)


# ── Step 0: Ensure pipeline package has __init__.py ──────────────────────────
for pkg_dir in ["pipeline", "dashboard", "dashboard/pages", "agents", "ml", "config"]:
    init_file = Path(pkg_dir) / "__init__.py"
    if not init_file.exists():
        init_file.touch()


# ── Step 1: Check API keys ─────────────────────────────────────────────────────
print("\n[Step 1] Checking API keys in .env...")
required_keys = {
    "GROQ_API_KEY":  "Required -- Groq LLM (Llama models)",
    "NEWSAPI_KEY":   "Required -- NewsAPI.org news fetch",
}
optional_keys = {
    "GEMINI_API_KEY":     "Optional -- Gemini LLM fallback",
    "LANGCHAIN_API_KEY":  "Optional -- LangSmith tracing",
}

all_required_ok = True
for key, desc in required_keys.items():
    val = os.environ.get(key, "")
    status = "[OK]" if val else "[MISSING]"
    if not val:
        all_required_ok = False
    print(f"  {status}  {key}: {desc}")

for key, desc in optional_keys.items():
    val = os.environ.get(key, "")
    print(f"  {'[OK]' if val else '[OPT]'}  {key}: {desc}")

if not all_required_ok:
    print("\n[WARN] Some required keys are missing. Add them to .env before continuing.")
    print("  Continue anyway? (y/N): ", end="", flush=True)
    response = input()
    if response.lower() != "y":
        print("Setup aborted. Add API keys to .env and retry.")
        sys.exit(1)


# ── Step 2: Create data directories ──────────────────────────────────────────
print("\n[Step 2] Creating data directories...")
from config.settings import DATA_DIR, MODELS_DIR, PROCESSED_DIR, RAW_DIR, CHROMA_DIR

dirs_to_create = [
    DATA_DIR,
    MODELS_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    CHROMA_DIR,
    DATA_DIR / "predictions",
]

for d in dirs_to_create:
    d.mkdir(parents=True, exist_ok=True)
    print(f"  [OK]  {d}")


# ── Step 3: Download spaCy model ──────────────────────────────────────────────
print("\n[Step 3] Downloading spaCy en_core_web_sm...")
try:
    import spacy
    spacy.load("en_core_web_sm")
    print("  [OK]  en_core_web_sm already downloaded")
except OSError:
    ret = os.system(f"{sys.executable} -m spacy download en_core_web_sm")
    if ret == 0:
        print("  [OK]  en_core_web_sm downloaded")
    else:
        print("  [FAIL]  Run manually: python -m spacy download en_core_web_sm")


# ── Step 4: Download FinBERT model ────────────────────────────────────────────
print("\n[Step 4] Downloading FinBERT (ProsusAI/finbert) ~450MB...")
try:
    from transformers import pipeline as hf_pipeline
    finbert = hf_pipeline("text-classification", model="ProsusAI/finbert", device=-1)
    test_result = finbert("RBI cuts interest rate")
    print(f"  [OK]  FinBERT ready -- test result: {test_result[0]['label']}")
    del finbert
except Exception as e:
    print(f"  [FAIL]  FinBERT: {e}")


# ── Step 5: Fetch all NIFTY 50 historical data ────────────────────────────────
print("\n[Step 5] Fetching NIFTY 50 historical data (2015 to today)...")
print("  This fetches 50 stocks x 10 years of daily OHLCV. ~10 minutes.")
try:
    from ml.data_collector import fetch_all_nifty50, get_nifty50_index_data
    t0 = time.time()
    data = fetch_all_nifty50()
    get_nifty50_index_data()
    elapsed = time.time() - t0
    print(f"  [OK]  {len(data)} stocks downloaded in {elapsed:.0f}s")
except Exception as e:
    print(f"  [FAIL]  Data fetch: {e}")
    print("  Try manually: python -m ml.data_collector")


# ── Step 6: Feature engineering ───────────────────────────────────────────────
print("\n[Step 6] Engineering features (50+ technical indicators)...")
try:
    from ml.feature_engineering import engineer_all_stocks
    t0 = time.time()
    engineer_all_stocks()
    elapsed = time.time() - t0
    n_files = len(list(PROCESSED_DIR.glob("*_features.csv")))
    print(f"  [OK]  Feature engineering done in {elapsed:.0f}s ({n_files} feature files)")
except Exception as e:
    print(f"  [FAIL]  Feature engineering: {e}")


# ── Step 7: Fit regime detector ───────────────────────────────────────────────
print("\n[Step 7] Fitting HMM regime detector...")
try:
    from ml.regime_detector import fit_and_save_all_regime_models
    t0 = time.time()
    fit_and_save_all_regime_models()
    elapsed = time.time() - t0
    print(f"  [OK]  Regime model fitted in {elapsed:.0f}s")
except Exception as e:
    print(f"  [FAIL]  Regime detector: {e}")


# ── Step 8: Train all ML models ───────────────────────────────────────────────
print("\n[Step 8] Training LightGBM + CatBoost ensemble models...")
print("  50 stocks x ensemble training. ~15 minutes. Watch data/models/ fill up.")
try:
    from ml.predictor import train_all_models
    t0 = time.time()
    train_all_models(optimize=False)
    elapsed = time.time() - t0
    n_models = len(list(MODELS_DIR.glob("*.pkl")))
    print(f"  [OK]  {n_models} models trained in {elapsed:.0f}s")
except Exception as e:
    print(f"  [FAIL]  Model training: {e}")
    print("  Try manually: python -m ml.predictor")


# ── Step 9: Run backtesting ───────────────────────────────────────────────────
print("\n[Step 9] Running backtesting...")
try:
    from ml.backtesting import run_backtest
    import inspect
    sig = inspect.signature(run_backtest)
    n_params = len([p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty])
    if n_params == 0:
        result = run_backtest()
        print(f"  [OK]  Backtesting complete")
        if result:
            sharpe = result.get("sharpe_ratio", "N/A")
            acc    = result.get("directional_accuracy", 0)
            print(f"        Sharpe Ratio        : {sharpe}")
            if isinstance(acc, float):
                print(f"        Directional Accuracy: {acc:.1%}")
    else:
        print(f"  [SKIP]  run_backtest() needs {n_params} args -- run separately after training")
except Exception as e:
    print(f"  [SKIP]  Backtesting: {e}")


# ── Step 10: Summary ──────────────────────────────────────────────────────────
print()
print("=" * 60)
print("MarketPulse AI Setup Complete!")
print("=" * 60)
n_csv      = len(list(PROCESSED_DIR.glob("*.csv")))
n_parquet  = len(list(PROCESSED_DIR.glob("*.parquet")))
n_models   = len(list(MODELS_DIR.glob("*.pkl")))
print(f"  CSV files (raw OHLCV)      : {n_csv}")
print(f"  Parquet files (features)   : {n_parquet}")
from config.tickers import ACTIVE_STOCKS
print(f"  Trained models (.pkl)      : {n_models} / {len(ACTIVE_STOCKS)}")
print()
print("Next steps:")
print("  1. Run integration tests : python test_pipeline.py")
print("  2. Launch dashboard      : streamlit run dashboard/app.py")
print("  3. Start scheduler       : python -m pipeline.scheduler")
print()
print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
