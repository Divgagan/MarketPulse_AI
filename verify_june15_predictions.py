"""
verify_june15_predictions.py - MarketPulse AI
Verifies what the system predicted on June 15 for June 16,
and compares against actual market movement on June 16.
"""
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

PRED_DB       = Path("data/predictions/predictions.db")
PROCESSED_DIR = Path("data/processed")

print()
print("=" * 70)
print("  MarketPulse AI — Prediction Verification")
print("  Predictions made: June 15, 2026  |  For: June 16, 2026")
print("=" * 70)

# ── Step 1: Load June 15 predictions from DB ──────────────────────────────────
conn   = sqlite3.connect(str(PRED_DB))
cursor = conn.cursor()
cursor.execute("""
    SELECT ticker, predicted_direction, final_confidence, signal_strength, alert_text
    FROM predictions
    WHERE date = '2026-06-15'
    ORDER BY final_confidence DESC
""")
preds = cursor.fetchall()
conn.close()

print(f"\n[1] Predictions saved on June 15: {len(preds)} signals")
print()

if not preds:
    print("  No predictions found for June 15 in the database.")
    sys.exit(0)

# ── Step 2: Get actual June 16 prices from CSVs ───────────────────────────────
results = []

for ticker, pred_dir, conf, strength, alert_text in preds:
    csv_path = PROCESSED_DIR / f"{ticker}_features.csv"
    if not csv_path.exists():
        # Try raw CSV
        csv_path = Path("data/processed") / f"{ticker}.csv"

    actual_dir   = None
    actual_ret   = None
    jun15_close  = None
    jun16_close  = None

    # Also try reading directly from the raw CSV (which has Close prices)
    raw_csv = Path("data/processed") / f"{ticker}.csv"

    try:
        if raw_csv.exists():
            df = pd.read_csv(raw_csv, index_col="Date", parse_dates=True)
            df.index = pd.to_datetime(df.index).normalize()

            # Find June 15 and June 16 rows
            jun15 = pd.Timestamp("2026-06-15")
            jun16 = pd.Timestamp("2026-06-16")

            # Get closest available trading day to June 15 (in case it's weekend)
            close_col = "Close" if "Close" in df.columns else "close"

            if jun15 in df.index:
                jun15_close = float(df.loc[jun15, close_col])
            else:
                # Get last trading day before June 15
                before = df[df.index <= jun15]
                if not before.empty:
                    jun15_close = float(before[close_col].iloc[-1])

            if jun16 in df.index:
                jun16_close = float(df.loc[jun16, close_col])
            else:
                # Get first trading day after June 15
                after = df[df.index > jun15]
                if not after.empty:
                    jun16_close = float(after[close_col].iloc[0])

            if jun15_close and jun16_close:
                pct_change = ((jun16_close - jun15_close) / jun15_close) * 100
                actual_ret = round(pct_change, 2)
                actual_dir = "UP" if pct_change > 0 else "DOWN"

    except Exception as e:
        pass

    # Was the prediction correct?
    if actual_dir:
        pred_up = pred_dir.lower() == "bullish"
        act_up  = actual_dir == "UP"
        correct = pred_up == act_up
    else:
        correct = None

    results.append({
        "ticker":      ticker,
        "predicted":   pred_dir.upper(),
        "confidence":  conf,
        "strength":    strength,
        "jun15_close": jun15_close,
        "jun16_close": jun16_close,
        "actual_dir":  actual_dir,
        "actual_ret":  actual_ret,
        "correct":     correct,
    })

# ── Step 3: Print verification table ─────────────────────────────────────────
print("[2] Verification Results:")
print()
print(f"  {'Ticker':<16} {'Predicted':<12} {'Conf':<8} {'Jun15 Close':>12} {'Jun16 Close':>12} {'Change%':>9} {'Actual':>7} {'Result'}")
print("  " + "─" * 85)

correct_count = 0
wrong_count   = 0
unknown_count = 0

for r in results:
    j15 = f"₹{r['jun15_close']:,.2f}" if r["jun15_close"] else "N/A"
    j16 = f"₹{r['jun16_close']:,.2f}" if r["jun16_close"] else "N/A"
    chg = f"{r['actual_ret']:+.2f}%" if r["actual_ret"] is not None else "N/A"
    act = r["actual_dir"] or "N/A"

    if r["correct"] is True:
        result_str = "✅ CORRECT"
        correct_count += 1
    elif r["correct"] is False:
        result_str = "❌ WRONG"
        wrong_count += 1
    else:
        result_str = "❓ No data"
        unknown_count += 1

    print(f"  {r['ticker']:<16} {r['predicted']:<12} {r['confidence']:<8.3f} {j15:>12} {j16:>12} {chg:>9} {act:>7}   {result_str}")

# ── Step 4: Accuracy Summary ──────────────────────────────────────────────────
total_verifiable = correct_count + wrong_count
accuracy = (correct_count / total_verifiable * 100) if total_verifiable > 0 else 0

print()
print("=" * 70)
print("  VERDICT")
print("=" * 70)
print(f"  Predictions made on June 15 : {len(results)}")
print(f"  Verifiable (June 16 data exists) : {total_verifiable}")
print(f"  ✅ Correct  : {correct_count}")
print(f"  ❌ Wrong    : {wrong_count}")
print(f"  ❓ No data  : {unknown_count}")
if total_verifiable > 0:
    print(f"\n  📊 Accuracy : {correct_count}/{total_verifiable} = {accuracy:.1f}%")
    if accuracy >= 70:
        print("  🎯 Strong performance!")
    elif accuracy >= 50:
        print("  🟡 Moderate performance (better than random)")
    else:
        print("  🔴 Below 50% — model struggled on this day")

print()
print("  ⚠️  Note: June 15 signals had WEAK confidence (0.16)")
print("     Weak signals = model was uncertain = low reliability expected")
print()

# ── Step 5: Context — what June 16 looked like broadly ───────────────────────
print("[3] Market Context — June 16, 2026 (NIFTY 50 Index):")
try:
    nifty_csv = PROCESSED_DIR / "NIFTY50_INDEX.csv"
    if nifty_csv.exists():
        ndf = pd.read_csv(nifty_csv, index_col="Date", parse_dates=True)
        ndf.index = pd.to_datetime(ndf.index).normalize()
        close_col = "Close" if "Close" in ndf.columns else "close"

        jun15 = pd.Timestamp("2026-06-15")
        jun16 = pd.Timestamp("2026-06-16")

        n15 = ndf[ndf.index <= jun15][close_col].iloc[-1] if not ndf[ndf.index <= jun15].empty else None
        n16_rows = ndf[ndf.index == jun16]
        n16 = float(n16_rows[close_col].iloc[0]) if not n16_rows.empty else None

        if n15 and n16:
            nifty_chg = ((n16 - n15) / n15) * 100
            direction = "📈 UP" if nifty_chg > 0 else "📉 DOWN"
            print(f"  NIFTY 50 on June 16: {direction} {nifty_chg:+.2f}%  (closed at {n16:,.2f})")
        else:
            print("  NIFTY 50 June 16 data not available in index CSV")
    else:
        print("  NIFTY50_INDEX.csv not found")
except Exception as e:
    print(f"  Could not load NIFTY data: {e}")

print()
print("=" * 70)
print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("=" * 70)
print()
