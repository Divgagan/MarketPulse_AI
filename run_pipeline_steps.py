"""
run_pipeline_steps.py - MarketPulse AI
Runs Steps 2, 3, and predictions in sequence.
Step 1 (data download) is already done.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("runner")

print()
print("=" * 65)
print("  MarketPulse AI — Pipeline Runner (Steps 2, 3, Predict)")
print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("=" * 65)

# ── STEP 2: Feature Engineering ───────────────────────────────────────────────
print("\n[STEP 2] Feature Engineering (50+ indicators for all stocks)...")
print("         This takes ~3-5 minutes...")
try:
    from ml.feature_engineering import engineer_all_stocks
    engineer_all_stocks()
    print("[STEP 2] ✅ DONE")
except Exception as e:
    print(f"[STEP 2] ❌ FAILED: {e}")
    sys.exit(1)

# ── STEP 3: Regime Detection ──────────────────────────────────────────────────
print("\n[STEP 3] Detecting current market regime (HMM)...")
current_regime_label = "sideways"
current_regime_code  = 1
try:
    import yfinance as yf
    from ml.regime_detector import MarketRegimeDetector
    from config.settings import MODELS_DIR

    detector    = MarketRegimeDetector()
    regime_path = MODELS_DIR / "regime_model.pkl"

    if regime_path.exists():
        detector.load(str(regime_path))
        nifty = yf.download("^NSEI", period="6mo", progress=False, auto_adjust=True)
        if not nifty.empty:
            current_regime_label = detector.get_current_regime(nifty["Close"])
            regime_map = {"bear": 0, "sideways": 1, "bull": 2, "unknown": 1}
            current_regime_code = regime_map.get(str(current_regime_label).lower(), 1)
            print(f"         Regime: {current_regime_label.upper()} (code={current_regime_code})")
        else:
            print("         Could not fetch NIFTY — defaulting to sideways")
    else:
        print("         regime_model.pkl not found — defaulting to sideways")
    print("[STEP 3] ✅ DONE")
except Exception as e:
    print(f"[STEP 3] ⚠️  Regime detection failed ({e}) — using default sideways")

# ── STEP 4: Run Predictions for All Stocks ───────────────────────────────────
print("\n[STEP 4] Running predictions for all stocks...")
print("         (Using fresh data + real market regime)")
import joblib
import numpy as np
import pandas as pd
from config.tickers import ACTIVE_STOCKS
from config.settings import PROCESSED_DIR, MODELS_DIR

results = []
errors  = []

for ticker in list(ACTIVE_STOCKS.keys()):
    csv_path = PROCESSED_DIR / f"{ticker}_features.csv"
    pkl_path = MODELS_DIR / f"{ticker}_lgb_predictor.pkl"

    if not csv_path.exists() or not pkl_path.exists():
        continue

    try:
        df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
        if len(df) < 5:
            continue

        if "market_regime" not in df.columns:
            df["market_regime"] = current_regime_code

        last_date = df.index[-1].strftime("%Y-%m-%d")

        saved           = joblib.load(str(pkl_path))
        model           = saved["model"]
        feature_columns = saved.get("feature_columns", [])

        available_features = [c for c in feature_columns if c in df.columns]
        last_row = df[available_features].iloc[[-1]].values

        proba_up   = float(model.predict_proba(last_row)[0, 1])
        direction  = "BULLISH" if proba_up > 0.5 else "BEARISH"
        confidence = abs(proba_up - 0.5) * 2
        strength   = "STRONG" if confidence > 0.3 else ("MODERATE" if confidence > 0.15 else "weak")

        results.append({
            "ticker":     ticker,
            "date":       last_date,
            "direction":  direction,
            "prob_up":    proba_up,
            "confidence": confidence,
            "strength":   strength,
        })

    except Exception as e:
        errors.append(f"{ticker}: {str(e)[:60]}")

# ── Print Results ─────────────────────────────────────────────────────────────
print(f"\n[STEP 4] ✅ DONE — {len(results)} stocks predicted\n")
print("=" * 65)
print(f"  TODAY'S PREDICTIONS  ({datetime.now().strftime('%Y-%m-%d')})")
print(f"  Market Regime: {current_regime_label.upper()}")
print("=" * 65)

strong_bull = [r for r in results if r["direction"] == "BULLISH" and r["strength"] != "weak"]
strong_bear = [r for r in results if r["direction"] == "BEARISH" and r["strength"] != "weak"]
weak_all    = [r for r in results if r["strength"] == "weak"]

if strong_bull:
    print(f"\n  🟢 BULLISH — HIGH CONFIDENCE ({len(strong_bull)} stocks)")
    print(f"  {'Ticker':<16} {'Data Date':<12} {'Prob↑':>6} {'Conf':>7} {'Strength'}")
    print("  " + "-" * 55)
    for r in sorted(strong_bull, key=lambda x: x["confidence"], reverse=True):
        print(f"  {r['ticker']:<16} {r['date']:<12} {r['prob_up']:>6.3f} {r['confidence']:>7.3f} {r['strength']}")

if strong_bear:
    print(f"\n  🔴 BEARISH — HIGH CONFIDENCE ({len(strong_bear)} stocks)")
    print(f"  {'Ticker':<16} {'Data Date':<12} {'Prob↓':>6} {'Conf':>7} {'Strength'}")
    print("  " + "-" * 55)
    for r in sorted(strong_bear, key=lambda x: x["confidence"], reverse=True):
        prob_down = 1 - r["prob_up"]
        print(f"  {r['ticker']:<16} {r['date']:<12} {prob_down:>6.3f} {r['confidence']:>7.3f} {r['strength']}")

if weak_all:
    print(f"\n  ⚪ WEAK / UNCERTAIN — {len(weak_all)} stocks (no strong signal)")

print()
print("=" * 65)
print(f"  SUMMARY")
print(f"  Data Date (freshness)  : {results[0]['date'] if results else 'N/A'}")
print(f"  Total predicted        : {len(results)}")
print(f"  Strong BULLISH         : {len(strong_bull)}")
print(f"  Strong BEARISH         : {len(strong_bear)}")
print(f"  Weak / uncertain       : {len(weak_all)}")
if errors:
    print(f"  Errors                 : {len(errors)}")
print("=" * 65)
print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print()
