"""
config/settings.py — MarketPulse AI
====================================
Central configuration file. Loads all environment variables and defines
all constants used throughout the project.

All other files should import from here — never hardcode API keys or paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env file ─────────────────────────────────────────────────────────────
# Resolve the project root (two levels up from this file: config/ → root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── LLM Model Names ────────────────────────────────────────────────────────────
# Rule 7 (LLM_INSTRUCTIONS): Use 70B for complex reasoning, 8B for simple tasks

# For complex agent tasks: impact scoring, signal aggregation, final reasoning
MODEL_PRIMARY = "llama-3.3-70b-versatile"

# For simple agent tasks: entity extraction, relevance check, alert formatting
MODEL_SECONDARY = "llama-3.1-8b-instant"

# Fallback model (used when Groq hits rate limits)
MODEL_FALLBACK = "gemini-2.0-flash-exp"

# ── API Keys ───────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")        # Optional — RSS feeds used if not set
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")  # Optional — for agent tracing

# ── Supabase (Cloud Database) ──────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ── LangSmith Tracing (activates automatically if key is set) ──────────────────
if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "marketpulse-ai")

# ── Directory Paths ────────────────────────────────────────────────────────────
# All data lives under data/ at the project root
DATA_DIR = PROJECT_ROOT / "data"

# Subdirectories — created automatically if they don't exist
RAW_DIR = DATA_DIR / "raw"            # Raw news articles (JSON)
PROCESSED_DIR = DATA_DIR / "processed"  # Feature-engineered stock data (CSV)
PREDICTIONS_DIR = DATA_DIR / "predictions"  # Daily predictions log (SQLite)
OUTCOMES_DIR = DATA_DIR / "outcomes"   # Actual outcomes for accuracy tracking
MODELS_DIR = DATA_DIR / "models"       # Saved LightGBM models per stock (.pkl)
CHROMA_DIR = DATA_DIR / "chroma_db"   # ChromaDB vector store for RAG memory

# Ensure all data directories exist at import time
for _dir in [RAW_DIR, PROCESSED_DIR, PREDICTIONS_DIR, OUTCOMES_DIR, MODELS_DIR, CHROMA_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ── SQLite Database Path ────────────────────────────────────────────────────────
SQLITE_DB_PATH = PREDICTIONS_DIR / "marketpulse.sqlite"

# ── Scheduling Constants ───────────────────────────────────────────────────────
POLL_INTERVAL_MINUTES = 30   # News pipeline runs every 30 minutes

# ── NSE Market Hours (IST) ─────────────────────────────────────────────────────
MARKET_OPEN = "09:15"    # NSE market opens at 9:15 AM IST
MARKET_CLOSE = "15:30"   # NSE market closes at 3:30 PM IST
EOD_PIPELINE_TIME = "15:45"  # EOD pipeline runs 15 min after close

# ── NIFTY 50 ────────────────────────────────────────────────────────────────────
NIFTY50_COUNT = 50          # Total number of stocks tracked

# ── ML / Backtesting Constants ─────────────────────────────────────────────────
# Historical data start date for training (10+ years for robust ML)
TRAINING_START_DATE = "2015-01-01"

# 0.1% per side (buy + sell = 0.2% round trip) — realistic NSE brokerage estimate
TRANSACTION_COST = 0.001

# Minimum ML/news confidence to show a signal on dashboard or generate alert
# Below this threshold, signal is marked "insufficient data"
CONFIDENCE_THRESHOLD = 0.55

# ── Validation ─────────────────────────────────────────────────────────────────
def validate_config() -> dict:
    """
    Check that all required settings are properly loaded.
    Call this at startup to catch missing keys early.
    Returns dict of {key: status} for display.
    """
    checks = {
        "GROQ_API_KEY": bool(GROQ_API_KEY and GROQ_API_KEY.startswith("gsk_")),
        "GEMINI_API_KEY": bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here"),
        "NEWSAPI_KEY (optional)": bool(NEWSAPI_KEY and NEWSAPI_KEY != "your_newsapi_key_here"),
        "LANGSMITH_API_KEY (optional)": bool(LANGSMITH_API_KEY and LANGSMITH_API_KEY != "your_langsmith_api_key_here"),
        "SUPABASE_URL": bool(SUPABASE_URL and "supabase.co" in SUPABASE_URL),
        "SUPABASE_KEY": bool(SUPABASE_KEY and SUPABASE_KEY.startswith("sb_")),
        "DATA_DIR exists": DATA_DIR.exists(),
        "MODELS_DIR exists": MODELS_DIR.exists(),
        "CHROMA_DIR exists": CHROMA_DIR.exists(),
    }
    return checks


if __name__ == "__main__":
    # Quick config validation -- run: python config/settings.py
    print("-" * 50)
    print("MarketPulse AI -- Configuration Check")
    print("-" * 50)
    results = validate_config()
    for key, status in results.items():
        icon = "[OK]" if status else "[MISSING]"
        print(f"  {icon}  {key}")
    print()
    print(f"  PROJECT_ROOT : {PROJECT_ROOT}")
    print(f"  DATA_DIR     : {DATA_DIR}")
    print(f"  MODELS_DIR   : {MODELS_DIR}")
    print(f"  MODEL_PRIMARY: {MODEL_PRIMARY}")
    print(f"  MODEL_SEC    : {MODEL_SECONDARY}")
    print("-" * 50)
