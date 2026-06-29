"""
dashboard/app.py — MarketPulse AI
====================================
Blueprint Part 18 File 1: Main Streamlit Entry Point.

Shows:
  1. Header + SEBI disclaimer banner
  2. Market status indicator (IST time)
  3. Summary stats (4 KPI cards)
  4. Top 5 highest-confidence signal cards
  5. Sidebar navigation to 4 pages

Run with: streamlit run dashboard/app.py
"""

import sqlite3
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title             = "MarketPulse AI",
    page_icon              = "📈",
    layout                 = "wide",
    initial_sidebar_state  = "expanded",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DATA_DIR
PREDICTIONS_DB = str(DATA_DIR / "predictions" / "predictions.db")
IST = pytz.timezone("Asia/Kolkata")

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_today_signals() -> pd.DataFrame:
    """Load latest predictions from Supabase or SQLite."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        from config.settings import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            # Fetch the latest date available
            date_res = supabase.table("predictions").select("date").order("date", desc=True).limit(1).execute()
            latest_date = date_res.data[0]["date"] if date_res.data else today

            res = supabase.table("predictions").select("*").eq("date", latest_date).order("final_confidence", desc=True).execute()
            return pd.DataFrame(res.data)
        else:
            conn = sqlite3.connect(PREDICTIONS_DB)
            # Fetch the latest date available
            date_df = pd.read_sql_query("SELECT MAX(date) as latest FROM predictions", conn)
            latest_date = date_df.iloc[0]["latest"] if not date_df.empty and date_df.iloc[0]["latest"] else today

            df   = pd.read_sql_query(
                "SELECT * FROM predictions WHERE date = ? ORDER BY final_confidence DESC",
                conn, params=(latest_date,)
            )
            conn.close()
            return df
    except Exception as e:
        st.error(f"Error loading signals: {e}. (Debug - URL: {'Found' if SUPABASE_URL else 'Missing'}, KEY: {'Found' if SUPABASE_KEY else 'Missing'})")
        return pd.DataFrame()


def market_status() -> tuple[str, str]:
    """Return (status_label, color) based on current IST time."""
    now  = datetime.now(IST)
    wday = now.weekday()  # 0=Monday
    hour, minute = now.hour, now.minute
    total_min = hour * 60 + minute

    if wday < 5 and (9 * 60 + 15) <= total_min <= (15 * 60 + 30):
        return "🟢  Market Open", "#00D4AA"
    return "⚫  Market Closed", "#6B7280"


def confidence_bar_html(conf: float) -> str:
    pct   = int(conf * 100)
    color = "#00D4AA" if conf >= 0.65 else ("#F59E0B" if conf >= 0.45 else "#6B7280")
    return (
        f"<div style='background:#1C2333;border-radius:4px;height:8px;width:100%'>"
        f"<div style='background:{color};border-radius:4px;height:8px;width:{pct}%'></div></div>"
        f"<small style='color:{color}'>{pct}% confidence</small>"
    )


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { padding-top: 0.5rem; }
    .signal-card {
        background: #1C2333;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        border-left: 4px solid #00D4AA;
    }
    .signal-card.bearish { border-left-color: #EF4444; }
    .signal-card.weak    { border-left-color: #6B7280; }
    .kpi-card {
        background: #1C2333;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .kpi-num  { font-size: 2.2rem; font-weight: 700; color: #00D4AA; }
    .kpi-lab  { font-size: 0.85rem; color: #9CA3AF; }
    .disclaimer-banner {
        background: linear-gradient(135deg,#7C2D12,#991B1B);
        border-radius: 10px;
        padding: 0.8rem 1.2rem;
        border-left: 4px solid #EF4444;
        margin-bottom: 1rem;
    }
    .header-badge {
        background: #00D4AA22;
        color: #00D4AA;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 MarketPulse AI")
    st.markdown("---")

    status_label, status_color = market_status()
    st.markdown(
        f"<span style='color:{status_color};font-weight:600'>{status_label}</span>",
        unsafe_allow_html=True,
    )
    now_ist = datetime.now(IST).strftime("%H:%M IST • %d %b %Y")
    st.caption(now_ist)

# ── Header ────────────────────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("# 📈 MarketPulse AI")
    st.markdown(
        "<span class='header-badge'>Research Prototype</span> &nbsp;"
        "<span class='header-badge'>Educational Purposes Only</span>",
        unsafe_allow_html=True,
    )
    st.markdown("**NIFTY 50 Signal Intelligence — Multi-Agent AI System**")

# ── SEBI Disclaimer ───────────────────────────────────────────────────────────
from agents.alert_generator import format_disclaimer
with st.expander("⚠️ **RESEARCH DISCLAIMER — Read Before Using**", expanded=True):
    st.markdown(
        f"<div class='disclaimer-banner'><p style='color:#FCA5A5;margin:0;font-size:0.88rem'>"
        f"{format_disclaimer()}</p></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

from config.settings import SUPABASE_URL, SUPABASE_KEY
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("🚨 **Configuration Error:** Supabase credentials are missing! Please check Streamlit Secrets for syntax errors (like accidental line breaks). The dashboard is currently reading an empty local database.")

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading today's signals..."):
    df = load_today_signals()

# ── Summary KPI Cards ─────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

total   = len(df)
bullish = int((df["predicted_direction"] == "bullish").sum()) if not df.empty else 0
bearish = int((df["predicted_direction"] == "bearish").sum()) if not df.empty else 0
last_run = df["created_at"].max()[:16] if not df.empty and "created_at" in df.columns else "—"

with k1:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-num'>{total}</div>"
        f"<div class='kpi-lab'>Total Signals Today</div></div>",
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-num' style='color:#00D4AA'>⬆ {bullish}</div>"
        f"<div class='kpi-lab'>Bullish Signals</div></div>",
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-num' style='color:#EF4444'>⬇ {bearish}</div>"
        f"<div class='kpi-lab'>Bearish Signals</div></div>",
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-num' style='font-size:1.2rem'>{last_run}</div>"
        f"<div class='kpi-lab'>Last Pipeline Run</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Top 5 Highest Confidence Signals ─────────────────────────────────────────
st.subheader("🔥 Top Signals Today")

if df.empty:
    st.info(
        "No signals generated yet today. "
        "Run `python -m agents.graph` or wait for the scheduler to trigger."
    )
else:
    top5 = df.head(5)
    for _, row in top5.iterrows():
        direction = row.get("predicted_direction", "neutral")
        conf      = float(row.get("final_confidence", 0))
        ticker    = row.get("ticker", "")
        strength  = row.get("signal_strength", "")
        css_class = "signal-card" + (" bearish" if direction == "bearish" else " weak" if strength == "weak" else "")
        icon      = "⬆" if direction == "bullish" else "⬇" if direction == "bearish" else "⟷"

        st.markdown(
            f"<div class='{css_class}'>"
            f"<b style='font-size:1.1rem'>{icon} {ticker}</b> &nbsp;"
            f"<span style='color:#9CA3AF;font-size:0.85rem'>{strength.title()} signal</span><br>"
            f"{confidence_bar_html(conf)}"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Quick distribution chart ──────────────────────────────────────────────────
if not df.empty and "predicted_direction" in df.columns:
    st.subheader("📊 Signal Distribution")
    col_a, col_b = st.columns(2)

    with col_a:
        counts = df["predicted_direction"].value_counts().reset_index()
        counts.columns = ["Direction", "Count"]
        fig = px.pie(
            counts, values="Count", names="Direction",
            color="Direction",
            color_discrete_map={"bullish": "#00D4AA", "bearish": "#EF4444", "neutral": "#6B7280"},
            title="Signal Direction Breakdown",
        )
        fig.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
                          font_color="#FAFAFA", title_font_size=14)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        strength_counts = df["signal_strength"].value_counts().reset_index()
        strength_counts.columns = ["Strength", "Count"]
        fig2 = px.bar(
            strength_counts, x="Strength", y="Count",
            color="Strength",
            color_discrete_map={"strong": "#00D4AA", "moderate": "#F59E0B", "weak": "#6B7280"},
            title="Signal Strength Breakdown",
        )
        fig2.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#1C2333",
                           font_color="#FAFAFA", title_font_size=14,
                           showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

st.caption("MarketPulse AI · Research Prototype · Not investment advice")
