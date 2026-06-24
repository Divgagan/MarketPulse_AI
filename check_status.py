"""
Quick dashboard & prediction status check.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sqlite3
from pathlib import Path
from datetime import date, datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from config.settings import SUPABASE_URL, SUPABASE_KEY

PRED_DB = Path("data/predictions/predictions.db")
today   = str(date.today())

print("=" * 60)
print(f"  MarketPulse AI — Status Check")
print(f"  Today: {today}  (IST time: {datetime.now().strftime('%H:%M')})")
print("=" * 60)

# ── 1. SQLite local DB ─────────────────────────────────────────
print("\n[1] LOCAL SQLite predictions.db")
conn = sqlite3.connect(str(PRED_DB))
c = conn.cursor()
c.execute("SELECT DISTINCT date FROM predictions ORDER BY date DESC LIMIT 5")
dates = c.fetchall()
print("  Dates with predictions:", [d[0] for d in dates])

c.execute("SELECT COUNT(*) FROM predictions WHERE date = ?", (today,))
today_count = c.fetchone()[0]
print(f"  Predictions for TODAY ({today}): {today_count}")

if today_count == 0:
    c.execute("SELECT date, COUNT(*) FROM predictions GROUP BY date ORDER BY date DESC LIMIT 3")
    print("  Most recent dates:")
    for row in c.fetchall():
        print(f"    {row[0]}: {row[1]} predictions")
conn.close()

# ── 2. Supabase cloud DB ───────────────────────────────────────
print("\n[2] SUPABASE Cloud")
url_status = 'OK: Set' if SUPABASE_URL else 'MISSING'
key_status = 'OK: Set' if SUPABASE_KEY else 'MISSING'
print(f"  URL: {url_status}")
print(f"  KEY: {key_status}")

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        res = sb.table("predictions").select("date, ticker, predicted_direction, final_confidence") \
                .order("date", desc=True).limit(10).execute()
        
        if res.data:
            dates_seen = sorted(set(r["date"] for r in res.data), reverse=True)
            print(f"  Dates in Supabase: {dates_seen}")
            today_rows = [r for r in res.data if r["date"] == today]
            print(f"  Predictions for TODAY ({today}): {len(today_rows)}")
            if not today_rows:
                print(f"  ⚠️  NO predictions for today in Supabase!")
                print(f"  Most recent date: {dates_seen[0] if dates_seen else 'none'}")
            else:
                print(f"  Top 3 signals today:")
                top = sorted(today_rows, key=lambda x: x["final_confidence"], reverse=True)[:3]
                for r in top:
                    print(f"    {r['ticker']:<16} {r['predicted_direction']:<10} conf={r['final_confidence']:.3f}")
        else:
            print("  ❌ No data found in Supabase at all!")
    except Exception as e:
        print(f"  ❌ Supabase error: {e}")

# ── 3. Missing packages ────────────────────────────────────────
print("\n[3] MISSING PACKAGES (reason predictions = 0 locally)")
for pkg in ["lightgbm", "hmmlearn"]:
    try:
        __import__(pkg)
        print(f"  ✅ {pkg} installed")
    except ImportError:
        print(f"  ❌ {pkg} NOT installed — models cannot load!")

# ── 4. Pipeline schedule ───────────────────────────────────────
print("\n[4] PIPELINE SCHEDULE")
print("  GitHub Actions EOD pipeline runs at: 3:45 PM IST (Mon-Fri)")
print("  → Cron: '15 10 * * 1-5' (UTC)")
print(f"  Today is: {datetime.now().strftime('%A')}")
print("  Last run would generate predictions for NEXT trading day")

print("\n" + "=" * 60)
