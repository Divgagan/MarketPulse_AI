"""
dashboard/pages/4_model_performance.py — MarketPulse AI
=========================================================
Blueprint Part 18 File 5: Live Model Performance Page.

Features:
  - Rolling 30-day directional accuracy per model
  - Calibration plot: predicted probability vs actual hit rate
  - Confusion matrix
  - Recent predictions vs outcomes table (last 20)
  - System health: last run, API status, model retrain date
"""

import sqlite3
import sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import DATA_DIR, MODELS_DIR

st.set_page_config(page_title="Model Performance · MarketPulse AI", page_icon="🎯", layout="wide")

PREDICTIONS_DB = str(DATA_DIR / "predictions" / "predictions.db")

st.title("🎯 Model Performance & System Health")
st.caption("Live accuracy tracking, calibration analysis, and system status.")


@st.cache_data(ttl=300)
def load_all_predictions() -> pd.DataFrame:
    """Load all predictions with outcomes from SQLite."""
    try:
        conn = sqlite3.connect(PREDICTIONS_DB)
        df   = pd.read_sql_query(
            "SELECT * FROM predictions ORDER BY date DESC",
            conn,
        )
        conn.close()
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return pd.DataFrame()


df = load_all_predictions()

# ── Rolling 30-day accuracy chart ─────────────────────────────────────────────
st.subheader("📈 Rolling 30-Day Directional Accuracy")

if df.empty or "was_correct" not in df.columns or df["was_correct"].isna().all():
    # Simulated demo data
    st.info("Insufficient outcome data yet — showing demo trend (populates after live predictions + next-day validation).")
    dates = pd.date_range(end=datetime.now(), periods=60, freq="B")
    np.random.seed(99)
    demo_df = pd.DataFrame({
        "Date":        dates,
        "LightGBM":   np.clip(np.random.normal(0.64, 0.04, 60), 0.50, 0.80),
        "Chronos":    np.clip(np.random.normal(0.60, 0.05, 60), 0.48, 0.76),
        "Combined":   np.clip(np.random.normal(0.67, 0.03, 60), 0.55, 0.80),
    })
    fig = go.Figure()
    for col, color in [("Combined", "#00D4AA"), ("LightGBM", "#3B82F6"), ("Chronos", "#F59E0B")]:
        fig.add_trace(go.Scatter(x=demo_df["Date"], y=demo_df[col],
                                  name=col, line=dict(color=color, width=2)))
    fig.add_hline(y=0.5, line_dash="dash", line_color="#EF4444",
                  annotation_text="Random Baseline")
    fig.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#1C2333",
                      font_color="#FAFAFA", yaxis_title="Accuracy",
                      yaxis_range=[0.45, 0.85], hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

else:
    has_outcome = df[df["was_correct"].notna()].copy()
    has_outcome["week"] = has_outcome["date"].dt.to_period("W").dt.start_time
    weekly_acc = has_outcome.groupby("week")["was_correct"].mean().reset_index()
    weekly_acc.columns = ["Week", "Accuracy"]

    fig = px.line(weekly_acc, x="Week", y="Accuracy", markers=True,
                  title="Weekly Rolling Accuracy", color_discrete_sequence=["#00D4AA"])
    fig.add_hline(y=0.5, line_dash="dash", line_color="#EF4444", annotation_text="Baseline")
    fig.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#1C2333",
                      font_color="#FAFAFA", yaxis_range=[0.40, 0.85])
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Calibration Plot ──────────────────────────────────────────────────────────
st.subheader("🎯 Calibration Plot")
st.caption("A well-calibrated model: when it says 70% probability → 70% of those predictions are correct.")

has_both = df[(df["final_confidence"].notna()) & (df["was_correct"].notna())] if not df.empty else pd.DataFrame()

if has_both.empty:
    # Demo calibration
    prob_bins  = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
    actual_acc = [0.11, 0.22, 0.31, 0.42, 0.52, 0.61, 0.69, 0.78, 0.87]
    calib_df   = pd.DataFrame({"Predicted Probability": prob_bins, "Actual Accuracy": actual_acc})
    st.info("Demo calibration curve (populates with real data after 50+ outcomes).")
else:
    has_both["prob_bin"] = (has_both["final_confidence"] * 10).round() / 10
    calib_df = has_both.groupby("prob_bin")["was_correct"].mean().reset_index()
    calib_df.columns = ["Predicted Probability", "Actual Accuracy"]

fig_cal = go.Figure()
fig_cal.add_trace(go.Scatter(
    x=calib_df["Predicted Probability"], y=calib_df["Actual Accuracy"],
    name="MarketPulse AI", mode="lines+markers",
    line=dict(color="#00D4AA", width=2),
))
fig_cal.add_trace(go.Scatter(
    x=[0, 1], y=[0, 1], name="Perfect Calibration",
    line=dict(color="#6B7280", dash="dash"),
))
fig_cal.update_layout(
    paper_bgcolor="#0E1117", plot_bgcolor="#1C2333", font_color="#FAFAFA",
    xaxis_title="Predicted Probability", yaxis_title="Actual Accuracy",
    xaxis_range=[0, 1], yaxis_range=[0, 1],
)
st.plotly_chart(fig_cal, use_container_width=True)

st.markdown("---")

# ── Confusion Matrix ──────────────────────────────────────────────────────────
st.subheader("📋 Confusion Matrix")

if has_both.empty:
    tp, tn, fp, fn = 420, 380, 200, 220
    st.info("Demo confusion matrix. Populates with live prediction outcomes.")
else:
    has_both["pred_bull"] = (has_both["predicted_direction"] == "bullish").astype(int)
    has_both["act_bull"]  = (has_both["actual_direction"]  == "bullish").astype(int)
    tp = int(((has_both["pred_bull"] == 1) & (has_both["act_bull"] == 1)).sum())
    tn = int(((has_both["pred_bull"] == 0) & (has_both["act_bull"] == 0)).sum())
    fp = int(((has_both["pred_bull"] == 1) & (has_both["act_bull"] == 0)).sum())
    fn = int(((has_both["pred_bull"] == 0) & (has_both["act_bull"] == 1)).sum())

conf_mat = pd.DataFrame({
    "": ["Predicted Bullish", "Predicted Bearish"],
    "Actually Bullish": [tp, fn],
    "Actually Bearish": [fp, tn],
})

fig_cm = go.Figure(data=go.Heatmap(
    z=[[tp, fp], [fn, tn]],
    x=["Actually Bullish", "Actually Bearish"],
    y=["Predicted Bullish", "Predicted Bearish"],
    colorscale=[[0, "#1C2333"], [1, "#00D4AA"]],
    text=[[str(tp), str(fp)], [str(fn), str(tn)]],
    texttemplate="%{text}",
    textfont={"size": 18, "color": "white"},
))
fig_cm.update_layout(paper_bgcolor="#0E1117", font_color="#FAFAFA",
                     xaxis_title="Actual", yaxis_title="Predicted")
st.plotly_chart(fig_cm, use_container_width=True)

total_preds = tp + tn + fp + fn
if total_preds > 0:
    acc     = (tp + tn) / total_preds
    prec    = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall  = tp / (tp + fn) if (tp + fn) > 0 else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("Overall Accuracy", f"{acc:.1%}")
    m2.metric("Precision",        f"{prec:.1%}")
    m3.metric("Recall",           f"{recall:.1%}")

st.markdown("---")

# ── Recent predictions table ──────────────────────────────────────────────────
st.subheader("🕐 Last 20 Predictions vs Outcomes")

if df.empty:
    st.info("No predictions in database yet.")
else:
    recent = df.head(20)[["date", "ticker", "predicted_direction",
                           "final_confidence", "actual_direction",
                           "actual_change_pct", "was_correct"]].copy()
    recent["date"]             = recent["date"].dt.strftime("%Y-%m-%d")
    recent["final_confidence"] = recent["final_confidence"].apply(lambda x: f"{x:.0%}" if pd.notna(x) else "—")
    recent["actual_change_pct"]= recent["actual_change_pct"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "Pending")
    recent["was_correct"]      = recent["was_correct"].apply(
        lambda x: "✅" if x == 1 else ("❌" if x == 0 else "⏳ Pending")
    )
    recent.columns = ["Date", "Ticker", "Predicted", "Confidence",
                      "Actual Dir", "Actual Change", "Correct?"]
    st.dataframe(recent, use_container_width=True, hide_index=True)

st.markdown("---")

# ── System Health ─────────────────────────────────────────────────────────────
st.subheader("🖥 System Health")

h1, h2, h3, h4 = st.columns(4)

# Last run time — guard against empty df (max() returns NaT, strftime crashes)
last_run = df["date"].max().strftime("%Y-%m-%d") if not df.empty else "Never"
h1.metric("Last Pipeline Run", last_run)

# Prediction DB size
try:
    db_size = os.path.getsize(PREDICTIONS_DB) / 1024
    h2.metric("DB Size", f"{db_size:.0f} KB")
except Exception:
    h2.metric("DB Size", "—")

# Model files count
from config.tickers import ACTIVE_STOCKS
model_count = len(list(MODELS_DIR.glob("*_predictor.pkl"))) if MODELS_DIR.exists() else 0
h3.metric("Trained Models", f"{model_count} / {len(ACTIVE_STOCKS)}")

# ChromaDB records
try:
    import chromadb
    from config.settings import CHROMA_DIR
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    coll   = client.get_or_create_collection("news_impact_history")
    h4.metric("ChromaDB Records", coll.count())
except Exception:
    h4.metric("ChromaDB Records", "—")

# API status
st.markdown("#### API Status")
api_cols = st.columns(4)
APIs = [
    ("Groq API",     "GROQ_API_KEY"),
    ("Gemini API",   "GEMINI_API_KEY"),
    ("NewsAPI",      "NEWSAPI_KEY"),
    ("LangSmith",    "LANGCHAIN_API_KEY"),
]
from dotenv import load_dotenv
load_dotenv()

for col, (name, env_key) in zip(api_cols, APIs):
    key_set = bool(os.environ.get(env_key))
    col.markdown(
        f"{'🟢' if key_set else '🔴'} **{name}**<br>"
        f"<span style='color:#6B7280;font-size:0.78rem'>{'Configured' if key_set else 'Not set'}</span>",
        unsafe_allow_html=True,
    )

st.caption("⚠ Research prototype · Not investment advice · MarketPulse AI")
