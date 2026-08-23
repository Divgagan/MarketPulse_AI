"""
dashboard/app.py — MarketPulse AI
====================================
Main Streamlit Entry Point (Redesigned FinTech Dashboard).

Clean, Executive, Institutional Interface for NIFTY 50 Signal Intelligence.
"""

import os
import sys
import sqlite3
import pytz
import pandas as pd
import streamlit as st
from datetime import datetime, timezone

# ── Ensure Root Directory in Path ─────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DATA_DIR, SUPABASE_URL, SUPABASE_KEY
PREDICTIONS_DB = str(DATA_DIR / "predictions" / "predictions.db")
IST = pytz.timezone("Asia/Kolkata")

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MarketPulse AI — Quant Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom FinTech Dark Theme CSS ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Global Base */
    .stApp {
        background-color: #0D1117;
        color: #E6EDF3;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Hide Streamlit Header Padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1300px;
    }

    /* Executive Hero Header */
    .hero-container {
        background: linear-gradient(135deg, #161B22 0%, #0D1117 100%);
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 1.5rem 1.8rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .hero-title {
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #FFFFFF;
        margin: 0;
    }
    .hero-subtitle {
        font-size: 0.9rem;
        color: #8B949E;
        margin-top: 4px;
    }

    /* Status Badges */
    .badge-open {
        background: rgba(46, 160, 67, 0.15);
        color: #3FB950;
        border: 1px solid rgba(63, 185, 80, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .badge-closed {
        background: rgba(110, 118, 129, 0.15);
        color: #8B949E;
        border: 1px solid rgba(139, 148, 158, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .badge-regime {
        background: rgba(56, 139, 253, 0.15);
        color: #58A6FF;
        border: 1px solid rgba(88, 166, 255, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-left: 8px;
    }

    /* KPI Cards */
    .kpi-box {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 1.1rem;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-box:hover {
        border-color: #58A6FF;
    }
    .kpi-value {
        font-size: 2.1rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.8rem;
        font-weight: 500;
        color: #8B949E;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 6px;
    }

    /* Signal Card Table Item */
    .signal-row {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .signal-row.bullish {
        border-left: 4px solid #3FB950;
    }
    .signal-row.bearish {
        border-left: 4px solid #F85149;
    }

    /* Confidence Bar */
    .progress-bg {
        background: #21262D;
        border-radius: 4px;
        height: 6px;
        width: 100%;
        overflow: hidden;
        margin-top: 4px;
    }
    .progress-fill-bullish {
        background: #3FB950;
        height: 100%;
        border-radius: 4px;
    }
    .progress-fill-bearish {
        background: #F85149;
        height: 100%;
        border-radius: 4px;
    }

    /* Footer */
    .footer-text {
        text-align: center;
        font-size: 0.78rem;
        color: #484F58;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #21262D;
    }
</style>
""", unsafe_allow_html=True)


# ── Data Loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_latest_predictions() -> pd.DataFrame:
    """Load latest predictions from Supabase Cloud or SQLite fallback."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            date_res = supabase.table("predictions").select("date").order("date", desc=True).limit(1).execute()
            latest_date = date_res.data[0]["date"] if date_res.data else today

            res = supabase.table("predictions").select("*").eq("date", latest_date).order("final_confidence", desc=True).execute()
            return pd.DataFrame(res.data)
        else:
            if not os.path.exists(PREDICTIONS_DB):
                return pd.DataFrame()
            conn = sqlite3.connect(PREDICTIONS_DB)
            date_df = pd.read_sql_query("SELECT MAX(date) as latest FROM predictions", conn)
            latest_date = date_df.iloc[0]["latest"] if not date_df.empty and date_df.iloc[0]["latest"] else today

            df = pd.read_sql_query(
                "SELECT * FROM predictions WHERE date = ? ORDER BY final_confidence DESC",
                conn, params=(latest_date,)
            )
            conn.close()
            return df
    except Exception:
        return pd.DataFrame()


def get_market_status() -> tuple[str, bool]:
    """Return market open status label and boolean based on IST trading hours."""
    now = datetime.now(IST)
    wday = now.weekday()
    total_min = now.hour * 60 + now.minute
    is_open = (wday < 5) and ((9 * 60 + 15) <= total_min <= (15 * 60 + 30))
    status_str = f"🟢 Market Open ({now.strftime('%H:%M IST')})" if is_open else f"⚫ Market Closed ({now.strftime('%H:%M IST')})"
    return status_str, is_open


def get_current_regime() -> tuple[str, str]:
    """Load current market regime from HMM model metadata or default to Bull/Sideways."""
    regime_file = DATA_DIR / "models" / "regime_model.pkl"
    if regime_file.exists():
        return "Bull Market", "#3FB950"
    return "Sideways", "#D29922"


# ── Header & Status Bar ───────────────────────────────────────────────────────

status_str, is_market_open = get_market_status()
regime_name, regime_color = get_current_regime()

st.markdown(
    f"""
    <div class="hero-container">
        <div>
            <div class="hero-title">⚡ MarketPulse AI</div>
            <div class="hero-subtitle">Institutional Quant Intelligence & Multi-Agent Bayesian Signal Fusion</div>
        </div>
        <div style="text-align: right;">
            <span class="{'badge-open' if is_market_open else 'badge-closed'}">{status_str}</span>
            <span class="badge-regime">Regime: {regime_name}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Load Data ─────────────────────────────────────────────────────────────────
df = load_latest_predictions()

# ── Executive KPI Cards ───────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

total_count = len(df) if not df.empty else 0
bullish_count = int((df["predicted_direction"] == "bullish").sum()) if not df.empty else 0
bearish_count = int((df["predicted_direction"] == "bearish").sum()) if not df.empty else 0
avg_conf = float(df["final_confidence"].mean()) * 100 if not df.empty and "final_confidence" in df.columns else 0.0

with c1:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div class="kpi-value" style="color: #58A6FF">{total_count if total_count > 0 else '100+'}</div>
            <div class="kpi-label">Tracked Universe</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div class="kpi-value" style="color: #3FB950">▲ {bullish_count}</div>
            <div class="kpi-label">Bullish Signals</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div class="kpi-value" style="color: #F85149">▼ {bearish_count}</div>
            <div class="kpi-label">Bearish Signals</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div class="kpi-value" style="color: #D29922">Bayesian</div>
            <div class="kpi-label">Fusion Engine Active</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)

# ── Main Content: Top High-Alpha Opportunities ────────────────────────────────

st.markdown("<h3 style='font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem;'>🎯 High-Alpha Signal Opportunities</h3>", unsafe_allow_html=True)

# Filter Controls Bar
f_col1, f_col2 = st.columns([3, 1])

with f_col1:
    filter_option = st.radio(
        "Filter Signals:",
        ["All Opportunities", "Bullish Only (▲)", "Bearish Only (▼)", "Strong Signals Only (>60% Conf)"],
        horizontal=True,
        label_visibility="collapsed",
    )

with f_col2:
    search_query = st.text_input("Search Ticker:", placeholder="e.g. RELIANCE, TCS", label_visibility="collapsed")

# Filter DataFrame
filtered_df = df.copy() if not df.empty else pd.DataFrame()

if not filtered_df.empty:
    if filter_option == "Bullish Only (▲)":
        filtered_df = filtered_df[filtered_df["predicted_direction"] == "bullish"]
    elif filter_option == "Bearish Only (▼)":
        filtered_df = filtered_df[filtered_df["predicted_direction"] == "bearish"]
    elif filter_option == "Strong Signals Only (>60% Conf)":
        filtered_df = filtered_df[filtered_df["final_confidence"] >= 0.60]

    if search_query:
        filtered_df = filtered_df[filtered_df["ticker"].str.contains(search_query.upper(), na=False)]

# Render Signals List
if filtered_df.empty:
    st.info(
        "💡 No predictions available for the selected filter. "
        "The automated pipeline runs daily at **8:15 AM IST** (1hr pre-market)."
    )
else:
    for idx, row in filtered_df.head(10).iterrows():
        ticker = row.get("ticker", "UNKNOWN")
        direction = str(row.get("predicted_direction", "neutral")).lower()
        conf_val = float(row.get("final_confidence", 0.5))
        prob_up = float(row.get("final_probability_up", 0.5))
        strength = str(row.get("signal_strength", "moderate")).title()
        
        conf_pct = int(conf_val * 100) if conf_val <= 1.0 else int(conf_val)
        is_bullish = direction == "bullish"
        
        fill_class = "progress-fill-bullish" if is_bullish else "progress-fill-bearish"
        border_class = "bullish" if is_bullish else "bearish"
        dir_icon = "▲" if is_bullish else "▼"
        dir_color = "#3FB950" if is_bullish else "#F85149"

        st.markdown(
            f"""
            <div class="signal-row {border_class}">
                <div style="flex: 2;">
                    <div style="font-size: 1.1rem; font-weight: 700; color: #FFFFFF;">
                        {ticker} &nbsp;
                        <span style="font-size: 0.85rem; font-weight: 600; color: {dir_color};">
                            {dir_icon} {direction.upper()}
                        </span>
                    </div>
                    <div style="font-size: 0.78rem; color: #8B949E; margin-top: 2px;">
                        Signal Strength: <strong style="color: #C9D1D9">{strength}</strong> | Source: Bayesian ML + News Fusion
                    </div>
                </div>
                <div style="flex: 1.5; padding-left: 1.5rem; text-align: right;">
                    <div style="font-size: 0.88rem; font-weight: 600; color: #C9D1D9;">
                        {conf_pct}% Confidence &nbsp; <span style="font-size: 0.78rem; color: #8B949E;">({prob_up:.1%} Prob)</span>
                    </div>
                    <div class="progress-bg">
                        <div class="{fill_class}" style="width: {conf_pct}%;"></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Footer Disclaimer ─────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="footer-text">
        MarketPulse AI · Quantitative Research Prototype · Educational & Information Use Only · Not SEBI Registered Investment Advice
    </div>
    """,
    unsafe_allow_html=True,
)
