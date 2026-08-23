import sqlite3
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    print("No supabase credentials")
    exit()

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
conn = sqlite3.connect("data/predictions/predictions.db")
cursor = conn.cursor()
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
cursor.execute("SELECT date, ticker, predicted_direction, final_confidence, signal_strength, alert_text, created_at FROM predictions WHERE date = ?", (today,))
rows = cursor.fetchall()

print(f"Found {len(rows)} predictions to sync for today ({today}).")
for r in rows:
    payload = {
        "date": r[0],
        "ticker": r[1],
        "predicted_direction": r[2],
        "final_confidence": r[3],
        "signal_strength": r[4],
        "alert_text": r[5],
        "created_at": r[6],
        "regime": "unknown"
    }
    sb.table("predictions").delete().eq("date", r[0]).eq("ticker", r[1]).execute()
    sb.table("predictions").insert(payload).execute()
    print(f"Synced {r[1]}")

print("Done.")
