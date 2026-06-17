"""
check_predictions.py - MarketPulse AI
Checks prediction history and retroactively runs yesterday's predictions.
Fix: injects market_regime column (from HMM model) before predicting.
"""
import sys
import sqlite3
import pandas as pd
import joblib
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

PRED_DB      = Path("data/predictions/predictions.db")
PROCESSED_DIR = Path("data/processed")
MODELS_DIR    = Path("data/models")

print()
print("=" * 70)
print("  MarketPulse AI -- Prediction History + Retroactive Check")
print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("=" * 70)

# ── 1. What's already saved in predictions.db ────────────────────────────────
print("\n[PART 1]  Saved Predictions in predictions.db")
print("-" * 70)
conn = sqlite3.connect(str(PRED_DB))
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]

cursor.execute("SELECT COUNT(*) FROM predictions")
count = cursor.fetchone()[0]
print(f"  Total saved predictions: {count}")

if count > 0:
    cursor.execute("""
        SELECT date, ticker, predicted_direction, final_confidence,
               signal_strength, actual_direction, actual_change_pct, was_correct
        FROM predictions ORDER BY date DESC, final_confidence DESC
    """)
    rows = cursor.fetchall()
    print(f"\n  {'Date':<12} {'Ticker':<16} {'Predicted':<10} {'Confidence':<12} {'Strength':<10} {'Actual':<10} {'Change%':<10} {'Correct?'}")
    print("  " + "-" * 85)
    for row in rows:
        date, ticker, pred_dir, conf, strength, actual_dir, actual_pct, correct = row
        actual_dir = actual_dir or "N/A (not verified)"
        actual_pct = f"{actual_pct:.2f}%" if actual_pct else "N/A"
        correct    = "YES" if correct else ("NO" if correct is not None else "N/A")
        print(f"  {date:<12} {ticker:<16} {pred_dir.upper():<10} {conf:<12.3f} {strength:<10} {str(actual_dir):<10} {actual_pct:<10} {correct}")
else:
    print("  No predictions saved yet.")
conn.close()

# ── 2. Get current market regime from HMM ────────────────────────────────────
print("\n[PART 2]  Detecting Current Market Regime (HMM)")
print("-" * 70)
current_regime = 1  # Default: sideways
try:
    from ml.regime_detector import MarketRegimeDetector
    import yfinance as yf
    detector     = MarketRegimeDetector()
    regime_path  = MODELS_DIR / "regime_model.pkl"
    if regime_path.exists():
        detector.load(str(regime_path))
        nifty = yf.download("^NSEI", period="6mo", progress=False, auto_adjust=True)
        if not nifty.empty:
            regime_label = detector.get_current_regime(nifty["Close"])
            regime_map   = {"bear": 0, "sideways": 1, "bull": 2, "unknown": 1}
            current_regime = regime_map.get(str(regime_label).lower(), 1)
            print(f"  Current regime: {regime_label} (code={current_regime})")
        else:
            print("  Could not fetch NIFTY data. Using default regime=1 (sideways)")
    else:
        print("  regime_model.pkl not found. Using default regime=1 (sideways)")
except Exception as e:
    print(f"  Regime detection failed: {e}. Using default=1 (sideways)")

# ── 3. Retroactive predictions for June 15 data (for June 16 market) ─────────
print("\n[PART 3]  Retroactive Predictions (June 16 -- what model would have said)")
print("          Using: last row of each stock's feature CSV + regime injection")
print("-" * 70)

from config.tickers import ACTIVE_STOCKS

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

        # --- Inject market_regime if missing ---
        if "market_regime" not in df.columns:
            df["market_regime"] = current_regime

        last_date = df.index[-1].strftime("%Y-%m-%d")

        # Load model and get saved feature columns
        saved           = joblib.load(str(pkl_path))
        model           = saved["model"]
        feature_columns = saved.get("feature_columns", [])

        # Use only features available in df
        available_features = [c for c in feature_columns if c in df.columns]
        last_row = df[available_features].iloc[[-1]].values

        proba_up   = float(model.predict_proba(last_row)[0, 1])
        proba_down = 1.0 - proba_up
        direction  = "BULLISH" if proba_up > 0.5 else "BEARISH"
        confidence = abs(proba_up - 0.5) * 2
        strength   = "strong" if confidence > 0.3 else ("moderate" if confidence > 0.15 else "weak")

        # What ACTUALLY happened (from the target column of the last row)
        actual_move = None
        actual_ret  = None
        if "target" in df.columns and len(df) >= 2:
            tgt = df["target"].iloc[-1]
            actual_move = "UP" if tgt == 1 else "DOWN"
        if "daily_return" in df.columns:
            actual_ret = round(df["daily_return"].iloc[-1] * 100, 2)

        # Was model correct?
        if actual_move and direction:
            pred_up = direction == "BULLISH"
            act_up  = actual_move == "UP"
            correct = "YES" if pred_up == act_up else "NO"
        else:
            correct = "?"

        results.append({
            "ticker":       ticker,
            "data_date":    last_date,
            "direction":    direction,
            "prob_up":      proba_up,
            "confidence":   confidence,
            "strength":     strength,
            "actual_move":  actual_move or "N/A",
            "actual_ret":   actual_ret,
            "correct":      correct,
        })

    except Exception as e:
        errors.append(f"{ticker}: {str(e)[:80]}")

# ── 4. Print results table ────────────────────────────────────────────────────
print(f"\n  {'Ticker':<16} {'Date':<12} {'Signal':<10} {'Prob↑':>6} {'Conf':>6} {'Str':<10} {'Actual':>7} {'Ret%':>7} {'OK?':>5}")
print("  " + "-" * 85)

# Sort by confidence descending
for r in sorted(results, key=lambda x: x["confidence"], reverse=True):
    ret_str = f"{r['actual_ret']:+.2f}%" if r["actual_ret"] is not None else "  N/A"
    print(
        f"  {r['ticker']:<16} {r['data_date']:<12} {r['direction']:<10} "
        f"{r['prob_up']:>6.3f} {r['confidence']:>6.3f} {r['strength']:<10} "
        f"{r['actual_move']:>7} {ret_str:>7} {r['correct']:>5}"
    )

# ── 5. Accuracy summary ───────────────────────────────────────────────────────
bullish = [r for r in results if r["direction"] == "BULLISH"]
bearish = [r for r in results if r["direction"] == "BEARISH"]
strong  = [r for r in results if r["strength"] == "strong"]
correct = [r for r in results if r["correct"] == "YES"]
wrong   = [r for r in results if r["correct"] == "NO"]

print()
print("=" * 70)
print("  SUMMARY")
print("=" * 70)
print(f"  Total stocks predicted : {len(results)}")
print(f"  BULLISH signals        : {len(bullish)}")
print(f"  BEARISH signals        : {len(bearish)}")
print(f"  STRONG signals (>30%)  : {len(strong)}")
if correct or wrong:
    acc = len(correct) / (len(correct) + len(wrong)) * 100
    print(f"  Correct predictions    : {len(correct)} / {len(correct)+len(wrong)} ({acc:.1f}%)")
if errors:
    print(f"  Errors / skipped       : {len(errors)}")
    for e in errors[:3]:
        print(f"    {e}")
print("=" * 70)
print()
