"""
save_predictions_to_db.py - MarketPulse AI
Saves today's computed predictions into predictions.db so the dashboard shows them.
"""
import sys
import sqlite3
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.tickers import ACTIVE_STOCKS
from config.settings import PROCESSED_DIR, MODELS_DIR, SUPABASE_URL, SUPABASE_KEY

PRED_DB = Path("data/predictions/predictions.db")
TODAY   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

print(f"\nSaving today's predictions ({TODAY}) to predictions.db ...")

# ── Get real market regime ────────────────────────────────────────────────────
current_regime_code  = 1
current_regime_label = "sideways"
try:
    import yfinance as yf
    from ml.regime_detector import MarketRegimeDetector
    detector    = MarketRegimeDetector()
    regime_path = MODELS_DIR / "regime_model.pkl"
    if regime_path.exists():
        detector.load(str(regime_path))
        nifty = yf.download("^NSEI", period="6mo", progress=False, auto_adjust=True)
        if not nifty.empty:
            current_regime_label = detector.get_current_regime(nifty["Close"])
            regime_map = {"bear": 0, "sideways": 1, "bull": 2, "unknown": 1}
            current_regime_code = regime_map.get(str(current_regime_label).lower(), 1)
            print(f"  Market Regime: {current_regime_label.upper()}")
except Exception as e:
    print(f"  Regime detection failed ({e}) — using default sideways")

# ── Run predictions ───────────────────────────────────────────────────────────
predictions = []

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

        saved           = joblib.load(str(pkl_path))
        model           = saved["model"]
        feature_columns = saved.get("feature_columns", [])
        available       = [c for c in feature_columns if c in df.columns]
        last_row        = df[available].iloc[[-1]].values

        proba_up   = float(model.predict_proba(last_row)[0, 1])
        direction  = "bullish" if proba_up > 0.5 else "bearish"
        confidence = abs(proba_up - 0.5) * 2
        strength   = "strong" if confidence > 0.3 else ("moderate" if confidence > 0.15 else "weak")

        # Build alert text
        regime_emoji = {"bull": "🐂", "bear": "🐻", "sideways": "↔"}.get(
            str(current_regime_label).lower(), "↔")
        arrow = "⬆" if direction == "bullish" else "⬇"
        alert_text = (
            f"{arrow} {strength.upper()} {direction.upper()} — {ticker}\n"
            f"   Prob UP: {proba_up*100:.1f}% | Confidence: {confidence*100:.1f}%\n"
            f"   Regime: {regime_emoji} {str(current_regime_label).upper()}"
        )

        predictions.append({
            "date":               TODAY,
            "ticker":             ticker,
            "predicted_direction": direction,
            "final_confidence":   round(confidence, 4),
            "signal_strength":    strength,
            "alert_text":         alert_text,
            "actual_direction":   None,
            "actual_change_pct":  None,
            "was_correct":        None,
            "created_at":         datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        pass  # Skip silently

# ── Save to SQLite ────────────────────────────────────────────────────────────
conn   = sqlite3.connect(str(PRED_DB))
cursor = conn.cursor()

# Delete any existing predictions for today (avoid duplicates)
cursor.execute("DELETE FROM predictions WHERE date = ?", (TODAY,))
deleted = cursor.rowcount
if deleted:
    print(f"  Cleared {deleted} old prediction(s) for {TODAY}")

# Insert fresh predictions
for p in predictions:
    cursor.execute("""
        INSERT INTO predictions
          (date, ticker, predicted_direction, final_confidence, signal_strength,
           alert_text, actual_direction, actual_change_pct, was_correct, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        p["date"], p["ticker"], p["predicted_direction"], p["final_confidence"],
        p["signal_strength"], p["alert_text"], p["actual_direction"],
        p["actual_change_pct"], p["was_correct"], p["created_at"]
    ))

conn.commit()
conn.close()

# ── Save to Supabase (Cloud Database) ─────────────────────────────────────────
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        print("\n  Syncing to Supabase Cloud...")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Delete existing predictions for today (avoid duplicates)
        supabase.table("predictions").delete().eq("date", TODAY).execute()
        
        # Insert fresh predictions in batch
        if predictions:
            # Drop keys that aren't in Supabase schema or keep them matching
            supabase_payload = []
            for p in predictions:
                info = ACTIVE_STOCKS.get(p["ticker"], {})
                sp = {
                    "date": p["date"],
                    "ticker": p["ticker"],
                    "company_name": info.get("name", ""),
                    "sector": info.get("sector", ""),
                    "predicted_direction": p["predicted_direction"],
                    "final_confidence": p["final_confidence"],
                    "signal_strength": p["signal_strength"],
                    "alert_text": p["alert_text"],
                    "created_at": p["created_at"]
                }
                supabase_payload.append(sp)
            
            res = supabase.table("predictions").insert(supabase_payload).execute()
            print(f"  ☁️ Successfully synced {len(res.data)} predictions to Supabase.")
    except Exception as e:
        print(f"  ⚠️ Failed to sync to Supabase: {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
bullish  = [p for p in predictions if p["predicted_direction"] == "bullish"]
bearish  = [p for p in predictions if p["predicted_direction"] == "bearish"]
strong   = [p for p in predictions if p["signal_strength"] in ("strong", "moderate")]

print(f"\n  ✅ Saved {len(predictions)} predictions to predictions.db")
print(f"  🟢 Bullish : {len(bullish)}")
print(f"  🔴 Bearish : {len(bearish)}")
print(f"  ⚡ Strong/Moderate signals: {len(strong)}")
print()
print("  Top signals saved:")
top = sorted(predictions, key=lambda x: x["final_confidence"], reverse=True)[:5]
for p in top:
    arrow = "⬆" if p["predicted_direction"] == "bullish" else "⬇"
    print(f"    {arrow} {p['ticker']:<16} conf={p['final_confidence']:.3f}  ({p['signal_strength']})")

print()
print("  🔄 Dashboard will auto-refresh within 5 minutes (cache TTL=300s)")
print("  👉 Or press F5 / Ctrl+R on the dashboard to see signals NOW")
print()
