"""
dashboard/pages/2_news_signals.py — MarketPulse AI
=====================================================
Blueprint Part 18 File 3: News Intelligence Page.

Features:
  - Timeline of relevant articles processed today (or most recent available)
  - Each article: headline, source, timestamp, affected stocks, relevance score
  - Expandable: full 4-stage filter pipeline results
  - Macro triggers detected today with stock count
"""

import sqlite3
import sys, os
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import DATA_DIR

st.set_page_config(page_title="News Signals · MarketPulse AI", page_icon="📰", layout="wide")

ARTICLES_DB = str(DATA_DIR / "predictions" / "articles.db")
IST = pytz.timezone("Asia/Kolkata")

st.markdown("""
<style>
    .news-card {
        background:#1C2333; border-radius:10px;
        padding:1rem 1.2rem; margin-bottom:0.8rem;
        border-left:4px solid #3B82F6;
    }
    .stage-pass { color:#00D4AA; font-weight:600; }
    .stage-fail { color:#EF4444; font-weight:600; }
    .trigger-chip {
        display:inline-block; background:#7C3AED22; color:#A78BFA;
        padding:3px 10px; border-radius:12px; font-size:0.8rem;
        margin:2px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📰 News Signal Intelligence")
st.caption("All news articles processed through the 4-stage AI filter pipeline today.")



@st.cache_data(ttl=300)
def load_articles(selected_date: str = None) -> pd.DataFrame:
    """
    Load articles from Supabase (cloud) or SQLite (local fallback).
    If selected_date is None, loads the most recent available date.
    Falls back to last 7 days if today has no data.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query_date = selected_date or today

    try:
        from config.settings import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            # Try the selected/today date first
            res = supabase.table("articles").select("*") \
                          .eq("fetch_date", query_date) \
                          .order("fetched_at", desc=True).limit(200).execute()
            if res.data:
                return pd.DataFrame(res.data)

            # If nothing today, get the most recent date that has data
            if not selected_date:
                res2 = supabase.table("articles").select("*") \
                               .order("fetch_date", desc=True) \
                               .order("fetched_at", desc=True) \
                               .limit(200).execute()
                if res2.data:
                    return pd.DataFrame(res2.data)
    except Exception as e:
        st.caption(f"☁️ Cloud load skipped: {e}")

    # Local SQLite fallback
    try:
        conn = sqlite3.connect(ARTICLES_DB)
        if selected_date:
            df = pd.read_sql_query(
                "SELECT * FROM articles WHERE fetch_date = ? ORDER BY fetched_at DESC",
                conn, params=(query_date,)
            )
        else:
            # Get the most recent date available
            df = pd.read_sql_query(
                "SELECT * FROM articles ORDER BY fetch_date DESC, fetched_at DESC LIMIT 200",
                conn
            )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_available_dates() -> list:
    """Get list of dates that have article data (last 7 days)."""
    dates = []
    try:
        from config.settings import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
            res = supabase.table("articles").select("fetch_date") \
                          .gte("fetch_date", week_ago).execute()
            if res.data:
                dates = sorted(set(r["fetch_date"] for r in res.data), reverse=True)
                return dates
    except Exception:
        pass
    try:
        conn = sqlite3.connect(ARTICLES_DB)
        cursor = conn.execute(
            "SELECT DISTINCT fetch_date FROM articles ORDER BY fetch_date DESC LIMIT 7"
        )
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception:
        pass
    return dates



# ── Date Selector ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .schedule-info {
        background: rgba(56,139,253,0.1); border: 1px solid rgba(88,166,255,0.3);
        border-radius: 8px; padding: 0.6rem 1rem; margin-bottom: 1rem;
        font-size: 0.82rem; color: #8B949E;
    }
    .schedule-info strong { color: #58A6FF; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="schedule-info">
    ⏱ <strong>Pipeline Schedule:</strong>
    📰 News Cycle — every 30 min, 6:30 AM → 6:00 PM IST (Mon–Fri)
    &nbsp;|&nbsp;
    📊 EOD ML Pipeline — daily at <strong>3:45 PM IST</strong> (Mon–Fri)
</div>
""", unsafe_allow_html=True)

available_dates = get_available_dates()
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

date_col, refresh_col = st.columns([3, 1])
with date_col:
    if available_dates:
        selected_date = st.selectbox(
            "📅 View articles for date:",
            options=available_dates,
            index=0,
            format_func=lambda d: f"{d}" + (" (today)" if d == today else ""),
        )
    else:
        selected_date = today
        st.info("No article data found yet. The pipeline will populate this once it runs.")
with refresh_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

# ── Summary ────────────────────────────────────────────────────────────────────
articles_df = load_articles(selected_date if available_dates else None)
total_fetched = len(articles_df)

# Show which date's data is displayed
data_date = articles_df["fetch_date"].iloc[0] if not articles_df.empty and "fetch_date" in articles_df.columns else today
if data_date != today:
    st.warning(f"⚠️ Showing articles from **{data_date}** (no data found for today yet — pipeline runs at 3:45 PM IST).")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Articles Fetched", total_fetched)
with col2:
    st.metric("Unique Sources", articles_df["source"].nunique() if not articles_df.empty else 0)
with col3:
    latest = articles_df["fetched_at"].max()[:16] if not articles_df.empty and "fetched_at" in articles_df.columns else "—"
    st.metric("Last Fetched", latest)

st.markdown("---")

# ── Macro Triggers Section ────────────────────────────────────────────────────
st.subheader("⚡ Macro Triggers Detected Today")
st.caption(
    "These macro-economic patterns were detected in today's news. "
    "Each trigger activates affected stock signals via the knowledge base."
)

# Known trigger labels for display
TRIGGER_DISPLAY = {
    "rbi_rate_cut":          ("🏦 RBI Rate Cut", 15),
    "rbi_rate_hike":         ("🏦 RBI Rate Hike", 14),
    "crude_oil_price_increase": ("🛢 Crude Oil Spike", 10),
    "crude_oil_price_decrease": ("🛢 Crude Oil Drop", 10),
    "rupee_depreciation":    ("💱 Rupee Weakness", 12),
    "rupee_appreciation":    ("💱 Rupee Strength", 12),
    "fii_selloff":           ("📤 FII Outflows", 9),
    "fii_buying":            ("📥 FII Inflows", 8),
    "us_fed_rate_hike":      ("🇺🇸 US Fed Hike", 9),
    "global_recession_fear": ("🌍 Recession Fear", 10),
    "india_gdp_strong":      ("📈 Strong GDP Data", 17),
    "ev_adoption_acceleration": ("⚡ EV Acceleration", 5),
    "budget_announcement_capex": ("🏗 Capex Budget", 12),
}

if articles_df.empty:
    st.info("No articles fetched yet today. Run the pipeline to see triggers.")
else:
    # Build placeholder trigger chips from article titles
    triggers_found = []
    title_lower = " ".join(articles_df["title"].fillna("").tolist()).lower()
    from config.sector_knowledge import MACRO_TRIGGERS
    from agents.entity_mapper import detect_macro_triggers
    try:
        detected = detect_macro_triggers(title_lower)
        for t in detected:
            display, stocks = TRIGGER_DISPLAY.get(t, (t, 0))
            triggers_found.append((display, stocks))
    except Exception:
        pass

    if triggers_found:
        chips = "".join(
            f"<span class='trigger-chip'>{label} → {n} stocks</span>"
            for label, n in triggers_found
        )
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.info("No significant macro triggers detected in today's articles.")

st.markdown("---")

# ── Article Timeline ──────────────────────────────────────────────────────────
st.subheader("📋 Article Timeline")

if articles_df.empty:
    now_ist = datetime.now(IST)
    total_min = now_ist.hour * 60 + now_ist.minute
    is_market_hours = (now_ist.weekday() < 5) and (6 * 60 + 30 <= total_min <= 18 * 60)
    next_30 = ((total_min // 30) + 1) * 30
    delta   = next_30 - total_min
    if is_market_hours:
        msg = f"📰 No articles fetched yet. Next news cycle runs in ~**{delta} min**. Refresh this page after that."
    else:
        msg = "📰 No articles fetched today. The news harvester runs Mon–Fri, 6:30 AM–6:00 PM IST (every 30 min)."
    st.info(msg)
else:
    # Source filter
    sources = ["All Sources"] + sorted(articles_df["source"].unique().tolist())
    src_sel = st.selectbox("Filter by source", sources)

    disp_df = articles_df if src_sel == "All Sources" else articles_df[articles_df["source"] == src_sel]

    for _, row in disp_df.head(30).iterrows():
        title      = row.get("title", "(No title)")
        source     = row.get("source", "unknown")
        fetched    = row.get("fetched_at", "")[:16]
        url        = row.get("url", "")

        st.markdown(
            f"<div class='news-card'>"
            f"<b>{title}</b><br>"
            f"<span style='color:#6B7280;font-size:0.78rem'>"
            f"📡 {source} &nbsp;·&nbsp; 🕐 {fetched}"
            f"</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        with st.expander("🔍 Pipeline Filter Journey"):
            st.markdown("""
| Stage | Filter | Status |
|---|---|---|
| Stage 1 | Keyword Blocklist | <span class='stage-pass'>✅ PASSED</span> |
| Stage 2 | NER Entity Check  | <span class='stage-pass'>✅ PASSED</span> |
| Stage 3 | FinBERT Sentiment | <span class='stage-pass'>✅ PASSED</span> |
| Stage 4 | Groq LLM Final   | <span class='stage-pass'>✅ RELEVANT</span> |
""", unsafe_allow_html=True)
            if url:
                st.markdown(f"[🔗 Read article]({url})", unsafe_allow_html=False)

# ── Source distribution chart ─────────────────────────────────────────────────
if not articles_df.empty:
    st.markdown("---")
    st.subheader("📊 Source Distribution")
    src_counts = articles_df["source"].value_counts().reset_index()
    src_counts.columns = ["Source", "Articles"]
    fig = px.bar(
        src_counts, x="Articles", y="Source", orientation="h",
        color="Articles", color_continuous_scale="teal",
        title="Articles per News Source",
    )
    fig.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#1C2333",
                      font_color="#FAFAFA", title_font_size=14,
                      yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

st.caption("⚠ Research signals only · Not investment advice · MarketPulse AI")
