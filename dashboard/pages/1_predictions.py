"""
dashboard/pages/1_predictions.py — MarketPulse AI
====================================================
Blueprint Part 18 File 2: Full Predictions Page.

Features:
  - Filter bar: All / Bullish / Bearish / Strong only / By sector
  - 2-column grid of signal cards with color-coded borders
  - Each card: ticker, direction arrow, probability bar, confidence,
    signal strength badge, news catalyst, SHAP features, timestamp
"""

import sqlite3
import sys, os
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.tickers import ACTIVE_STOCKS
from config.settings import DATA_DIR

st.set_page_config(page_title="Predictions · MarketPulse AI", page_icon="📊", layout="wide")

PREDICTIONS_DB = str(DATA_DIR / "predictions" / "predictions.db")

st.markdown("""
<style>
    .sig-card {
        background:#1C2333; border-radius:12px; padding:1.2rem;
        margin-bottom:1rem; border-left:5px solid #00D4AA;
    }
    .sig-card.bearish { border-left-color:#EF4444; }
    .sig-card.weak    { border-left-color:#6B7280; }
    .badge {
        display:inline-block; padding:2px 8px; border-radius:12px;
        font-size:0.75rem; font-weight:600; margin-right:4px;
    }
    .badge-bullish { background:#00D4AA22; color:#00D4AA; }
    .badge-bearish { background:#EF444422; color:#EF4444; }
    .badge-strong  { background:#7C3AED22; color:#A78BFA; }
    .badge-weak    { background:#6B728022; color:#9CA3AF; }
    .prob-bar-bg { background:#0E1117; border-radius:4px; height:10px; }
    .prob-bar    { border-radius:4px; height:10px; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Today's Predictions")
st.caption("All NIFTY 50 signals generated today, sorted by confidence.")


@st.cache_data(ttl=300)
def load_signals() -> pd.DataFrame:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        from config.settings import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            res = supabase.table("predictions").select("*").eq("date", today).order("final_confidence", desc=True).execute()
            df = pd.DataFrame(res.data)
        else:
            conn = sqlite3.connect(PREDICTIONS_DB)
            df   = pd.read_sql_query(
                "SELECT * FROM predictions WHERE date = ? ORDER BY final_confidence DESC",
                conn, params=(today,)
            )
            conn.close()
            
        if not df.empty:
            # Add sector info from ACTIVE_STOCKS
            df["sector"] = df["ticker"].apply(
                lambda t: ACTIVE_STOCKS.get(t, {}).get("sector", "Unknown")
            )
        return df
    except Exception as e:
        st.error(f"Error loading signals: {e}")
        return pd.DataFrame()


df = load_signals()

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown("### Filters")
fc1, fc2, fc3 = st.columns([2, 2, 3])

with fc1:
    dir_filter = st.selectbox("Direction", ["All", "Bullish", "Bearish"])
with fc2:
    str_filter = st.selectbox("Strength", ["All", "Strong Only", "Weak Excluded"])
with fc3:
    sectors    = ["All Sectors"] + sorted(df["sector"].unique().tolist()) if not df.empty else ["All Sectors"]
    sec_filter = st.selectbox("Sector", sectors)

# Apply filters
filtered = df.copy()
if not filtered.empty:
    if dir_filter == "Bullish":
        filtered = filtered[filtered["predicted_direction"] == "bullish"]
    elif dir_filter == "Bearish":
        filtered = filtered[filtered["predicted_direction"] == "bearish"]

    if str_filter == "Strong Only":
        filtered = filtered[filtered["signal_strength"] == "strong"]
    elif str_filter == "Weak Excluded":
        filtered = filtered[filtered["signal_strength"] != "weak"]

    if sec_filter != "All Sectors":
        filtered = filtered[filtered["sector"] == sec_filter]

st.markdown(f"**Showing {len(filtered)} signals**")
st.markdown("---")

# ── Signal cards grid (2 columns) ─────────────────────────────────────────────
if filtered.empty:
    st.info("No signals match your filters. Try changing the filter settings above.")
else:
    cols = st.columns(2)
    for i, (_, row) in enumerate(filtered.iterrows()):
        direction = row.get("predicted_direction", "neutral")
        conf      = float(row.get("final_confidence", 0) or 0)
        ticker    = row.get("ticker", "—")
        strength  = row.get("signal_strength", "weak")
        alert_txt = row.get("alert_text", "")
        created   = row.get("created_at", "")[:16] if row.get("created_at") else "—"

        info      = ACTIVE_STOCKS.get(ticker, {})
        company   = info.get("name", ticker)
        sector    = info.get("sector", "Unknown")

        css_class = "sig-card" + (" bearish" if direction == "bearish" else " weak" if strength == "weak" else "")
        icon      = "⬆" if direction == "bullish" else "⬇" if direction == "bearish" else "⟷"
        dir_badge = f"<span class='badge badge-{direction}'>{icon} {direction.upper()}</span>"
        str_badge = f"<span class='badge badge-{strength}'>{strength.upper()}</span>"

        prob = conf * 100
        bar_color = "#00D4AA" if direction == "bullish" else "#EF4444"

        card_html = f"""
        <div class='{css_class}'>
            <div style='display:flex;justify-content:space-between;align-items:center'>
                <div>
                    <b style='font-size:1.15rem'>{ticker}</b>
                    <span style='color:#9CA3AF;font-size:0.85rem'> · {company}</span>
                </div>
                <span style='color:#6B7280;font-size:0.75rem'>{created}</span>
            </div>
            <div style='color:#6B7280;font-size:0.78rem;margin:2px 0 6px'>{sector}</div>
            {dir_badge} {str_badge}
            <div style='margin-top:10px'>
                <div style='display:flex;justify-content:space-between;margin-bottom:4px'>
                    <span style='font-size:0.82rem;color:#9CA3AF'>Confidence</span>
                    <span style='font-size:0.82rem;color:{bar_color}'>{prob:.0f}%</span>
                </div>
                <div class='prob-bar-bg'>
                    <div class='prob-bar' style='width:{prob:.0f}%;background:{bar_color}'></div>
                </div>
            </div>
        </div>
        """
        with cols[i % 2]:
            st.markdown(card_html, unsafe_allow_html=True)
            if alert_txt:
                with st.expander("📋 Full Signal Details"):
                    st.code(alert_txt, language=None)

st.markdown("---")
st.caption("⚠ Research signals only · Not investment advice · MarketPulse AI")
