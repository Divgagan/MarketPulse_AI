"""
dashboard/pages/5_historical_predictions.py — MarketPulse AI
============================================================
Allows the user to select ANY past date using a calendar.
If predictions exist in the database, it shows them.
If they don't exist, it uses the trained models to retroactively
generate the predictions for that exact date "on the fly" and 
compares them to what actually happened the next day.
"""

import sys
import os
import sqlite3
import joblib
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.tickers import ACTIVE_STOCKS
from config.settings import DATA_DIR

st.set_page_config(page_title="Historical Verification · MarketPulse AI", page_icon="🕒", layout="wide")

PREDICTIONS_DB = str(DATA_DIR / "predictions" / "predictions.db")
PROCESSED_DIR  = DATA_DIR / "processed"
MODELS_DIR     = DATA_DIR / "models"

st.markdown("""
<style>
    .kpi-card {
        background: #1C2333; border-radius: 10px; padding: 1rem;
        text-align: center; border-bottom: 3px solid #6B7280;
    }
    .kpi-card.correct { border-bottom-color: #00D4AA; }
    .kpi-card.wrong { border-bottom-color: #EF4444; }
    .kpi-num { font-size: 2rem; font-weight: 700; }
    .kpi-lab { font-size: 0.85rem; color: #9CA3AF; }
</style>
""", unsafe_allow_html=True)

st.title("🕒 Time Machine & Verification")
st.caption("Pick any date from the past. The AI will reconstruct what it would have predicted on that day, and verify it against actual market movements.")

# ── 1. Helper Functions ───────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_predictions_from_db(target_date_str):
    """Try to load from Supabase or SQLite if the pipeline ran that day."""
    try:
        from config.settings import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            res = supabase.table("predictions").select("ticker, predicted_direction, final_confidence, signal_strength").eq("date", target_date_str).execute()
            return pd.DataFrame(res.data)
        else:
            conn = sqlite3.connect(PREDICTIONS_DB)
            df = pd.read_sql_query(
                "SELECT ticker, predicted_direction, final_confidence, signal_strength FROM predictions WHERE date = ?",
                conn, params=(target_date_str,)
            )
            conn.close()
            return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def compute_retroactive_predictions(target_date_str):
    """Compute predictions on the fly using historical feature CSVs and saved models."""
    target_date = pd.Timestamp(target_date_str)
    predictions = []
    
    # We need market regime. If not found, default to sideways (1)
    current_regime_code = 1
    
    for ticker in list(ACTIVE_STOCKS.keys()):
        csv_path = PROCESSED_DIR / f"{ticker}_features.csv"
        pkl_path = MODELS_DIR / f"{ticker}_lgb_predictor.pkl"
        
        if not csv_path.exists() or not pkl_path.exists():
            continue
            
        try:
            df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
            df.index = pd.to_datetime(df.index).normalize()
            
            # Find the row corresponding to target_date (or the closest prior trading day)
            before_or_on = df[df.index <= target_date]
            if before_or_on.empty:
                continue
                
            # Use the last available row on or before the target date
            last_row_df = before_or_on.iloc[[-1]].copy()
            actual_data_date = last_row_df.index[0].strftime("%Y-%m-%d")
            
            if "market_regime" not in last_row_df.columns:
                last_row_df["market_regime"] = current_regime_code
                
            saved = joblib.load(str(pkl_path))
            model = saved["model"]
            feature_columns = saved.get("feature_columns", [])
            
            available_features = [c for c in feature_columns if c in last_row_df.columns]
            features_array = last_row_df[available_features].values
            
            proba_up = float(model.predict_proba(features_array)[0, 1])
            direction = "BULLISH" if proba_up > 0.5 else "BEARISH"
            confidence = abs(proba_up - 0.5) * 2
            strength = "STRONG" if confidence > 0.3 else ("MODERATE" if confidence > 0.15 else "WEAK")
            
            predictions.append({
                "ticker": ticker,
                "predicted_direction": direction,
                "final_confidence": confidence,
                "signal_strength": strength,
                "_data_date_used": actual_data_date
            })
        except Exception:
            continue
            
    return pd.DataFrame(predictions)

@st.cache_data(ttl=3600)
def get_actual_outcome(ticker, pred_date_str):
    """
    Fetches the actual % return for the next trading day after pred_date_str.
    Uses yfinance directly so this works on Streamlit Cloud (no local CSV needed).
    Results cached for 1 hour.
    """
    try:
        import yfinance as yf
        from datetime import timedelta

        pred_date  = pd.Timestamp(pred_date_str)
        # Fetch a window: pred_date to pred_date + 5 days (covers next trading day)
        start      = pred_date.strftime("%Y-%m-%d")
        end        = (pred_date + timedelta(days=7)).strftime("%Y-%m-%d")

        df = yf.download(ticker, start=start, end=end,
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 2:
            return None, None

        df.index = pd.to_datetime(df.index).normalize()

        # Base close: on the prediction date (or last available before it)
        on_or_before = df[df.index <= pred_date]
        if on_or_before.empty:
            return None, None
        base_close = float(on_or_before["Close"].iloc[-1])

        # Next close: first trading day AFTER prediction date
        after = df[df.index > pred_date]
        if after.empty:
            return None, None
        next_close = float(after["Close"].iloc[0])

        pct_change = ((next_close - base_close) / base_close) * 100
        actual_dir = "UP" if pct_change > 0 else "DOWN"
        return actual_dir, round(pct_change, 2)

    except Exception:
        return None, None



# ── 2. UI: Calendar Input ────────────────────────────────────────────────────

# Let the user pick ANY date (defaulting to yesterday so we have outcome data)
default_date = datetime.now() - timedelta(days=1)
selected_date = st.date_input("Select a Date to go back in time:", value=default_date, max_value=datetime.now())
selected_date_str = selected_date.strftime("%Y-%m-%d")

st.markdown("---")

# ── 3. Data Processing ───────────────────────────────────────────────────────

with st.spinner(f"Firing up the time machine for {selected_date_str}..."):
    
    # 1. Try DB first
    df_preds = load_predictions_from_db(selected_date_str)
    source_msg = "✅ Loaded from Database (Pipeline ran on this day)"
    
    # 2. If missing, compute on the fly!
    if df_preds.empty:
        df_preds = compute_retroactive_predictions(selected_date_str)
        source_msg = "⏳ Computed On-The-Fly (Reconstructing past model states)"

    if df_preds.empty:
        st.error(f"Could not generate predictions for {selected_date_str}. Do you have data downloaded for this date range?")
        st.stop()
        
    st.info(source_msg)

# ── Batch fetch actual prices via yfinance (one call for all tickers) ─────────
@st.cache_data(ttl=3600)
def fetch_batch_outcomes(tickers_tuple, pred_date_str):
    """
    Downloads price data for ALL tickers in one yfinance call.
    Returns dict: {ticker: (actual_dir, pct_change)} or {ticker: (None, None)}
    """
    import yfinance as yf
    from datetime import timedelta

    pred_date = pd.Timestamp(pred_date_str)
    start     = pred_date.strftime("%Y-%m-%d")
    end       = (pred_date + timedelta(days=7)).strftime("%Y-%m-%d")

    outcomes = {}
    try:
        # Download all tickers at once — much faster than one-by-one
        raw = yf.download(
            list(tickers_tuple), start=start, end=end,
            progress=False, auto_adjust=True, group_by="ticker"
        )
        for ticker in tickers_tuple:
            try:
                if len(tickers_tuple) == 1:
                    df = raw
                else:
                    df = raw[ticker] if ticker in raw.columns.get_level_values(0) else pd.DataFrame()

                if df.empty or "Close" not in df.columns:
                    outcomes[ticker] = (None, None)
                    continue

                df.index = pd.to_datetime(df.index).normalize()
                on_or_before = df[df.index <= pred_date]
                after        = df[df.index  > pred_date]

                if on_or_before.empty or after.empty:
                    outcomes[ticker] = (None, None)
                    continue

                base_close = float(on_or_before["Close"].iloc[-1])
                next_close = float(after["Close"].iloc[0])
                pct        = ((next_close - base_close) / base_close) * 100
                outcomes[ticker] = ("UP" if pct > 0 else "DOWN", round(pct, 2))
            except Exception:
                outcomes[ticker] = (None, None)
    except Exception:
        # Fallback: return all None
        for ticker in tickers_tuple:
            outcomes[ticker] = (None, None)
    return outcomes

with st.spinner("Fetching actual market outcomes (live from Yahoo Finance)..."):
    all_tickers = tuple(df_preds["ticker"].tolist())
    outcomes_map = fetch_batch_outcomes(all_tickers, selected_date_str)

results = []
correct_count = 0
wrong_count = 0
verifiable_count = 0

for _, row in df_preds.iterrows():
    ticker   = row["ticker"]
    pred_dir = row["predicted_direction"].upper()

    actual_dir, actual_pct = outcomes_map.get(ticker, (None, None))

    is_correct = None
    if actual_dir:
        verifiable_count += 1
        if (pred_dir == "BULLISH" and actual_dir == "UP") or (pred_dir == "BEARISH" and actual_dir == "DOWN"):
            is_correct = True
            correct_count += 1
        else:
            is_correct = False
            wrong_count += 1

    results.append({
        "Ticker":        ticker,
        "Predicted":     pred_dir,
        "Confidence":    float(row["final_confidence"]),
        "Strength":      str(row["signal_strength"]).upper(),
        "Actual Change": actual_pct,
        "Actual Dir":    actual_dir,
        "Correct":       is_correct
    })

df_results = pd.DataFrame(results).sort_values(by="Confidence", ascending=False)



# ── 4. Dashboard View ────────────────────────────────────────────────────────

accuracy = (correct_count / verifiable_count * 100) if verifiable_count > 0 else 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"<div class='kpi-card'><div class='kpi-num'>{len(df_preds)}</div><div class='kpi-lab'>Total Predictions</div></div>", unsafe_allow_html=True)
with k2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-num'>{verifiable_count}</div><div class='kpi-lab'>Verifiable Outcomes</div></div>", unsafe_allow_html=True)
with k3:
    st.markdown(f"<div class='kpi-card correct'><div class='kpi-num' style='color:#00D4AA'>{correct_count}</div><div class='kpi-lab'>Correct Calls</div></div>", unsafe_allow_html=True)
with k4:
    color = "#00D4AA" if accuracy >= 50 else "#EF4444"
    st.markdown(f"<div class='kpi-card'><div class='kpi-num' style='color:{color}'>{accuracy:.1f}%</div><div class='kpi-lab'>Overall Accuracy</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Detailed Table
st.subheader("📊 Detailed Breakdown")

display_df = df_results.copy()
display_df["Confidence"] = display_df["Confidence"].apply(lambda x: f"{x:.3f}")
display_df["Actual Change"] = display_df["Actual Change"].apply(lambda x: f"{x:+.2f}%" if pd.notnull(x) else "Market Not Opened Yet")
display_df["Actual Dir"] = display_df["Actual Dir"].fillna("—")

def highlight_correct(val):
    if val is True: return 'background-color: #00D4AA22; color: #00D4AA'
    if val is False: return 'background-color: #EF444422; color: #EF4444'
    return ''

st.dataframe(
    display_df.style.map(highlight_correct, subset=['Correct']),
    use_container_width=True,
    height=500
)

# Performance by Strength
if verifiable_count > 0:
    st.subheader("📈 Accuracy Grouped by Signal Strength")
    strength_acc = []
    for strength in ["STRONG", "MODERATE", "WEAK"]:
        subset = df_results[(df_results["Strength"] == strength) & (df_results["Correct"].notnull())]
        if not subset.empty:
            acc = subset["Correct"].sum() / len(subset) * 100
            strength_acc.append({"Strength": strength, "Accuracy": acc, "Count": len(subset)})
            
    if strength_acc:
        fig = px.bar(
            pd.DataFrame(strength_acc), x="Strength", y="Accuracy", text="Count",
            title="Does higher confidence = better accuracy?",
            color="Accuracy", color_continuous_scale=["#EF4444", "#F59E0B", "#00D4AA"]
        )
        fig.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", font_color="#FAFAFA")
        st.plotly_chart(fig, use_container_width=True)
