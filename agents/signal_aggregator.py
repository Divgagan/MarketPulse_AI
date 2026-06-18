"""
agents/signal_aggregator.py — MarketPulse AI
=============================================
Blueprint Part 15 File 1: Agent 6 — Signal Aggregator.

The most important agent — combines all signals (news + ML) into final
per-stock predictions using Llama 3.3 70B for the final reasoning step.

For each stock that appears in either news or ML pipeline:
  1. Aggregate multiple news items into one consolidated news signal
     (weighted by recency, severity, confidence)
  2. Combine with ML signal using combine_with_news_signal()
  3. If combined confidence > CONFIDENCE_THRESHOLD → Groq 70B final reasoning
  4. Create FinalSignal TypedDict
  5. Store to SQLite for dashboard + Alert Generator

LangGraph node:
  signal_aggregator_node(state) → state with final_signals populated
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from agents.state import FinalSignal, ImpactScore, MLPrediction, MarketPulseState
from config.tickers import ACTIVE_STOCKS
from config.settings import (
    CONFIDENCE_THRESHOLD, DATA_DIR, GROQ_API_KEY, MODEL_PRIMARY,
)
from ml.signal_combiner import combine_with_news_signal

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("signal_aggregator")

# ── DB path for storing final signals ────────────────────────────────────────
PREDICTIONS_DB = DATA_DIR / "predictions" / "predictions.db"

# ── Module-level Groq LLM ────────────────────────────────────────────────────
try:
    from langchain_groq import ChatGroq
    groq_llm = ChatGroq(
        model=MODEL_PRIMARY,
        api_key=GROQ_API_KEY,
        temperature=0.1,
        max_tokens=400,
    )
    GROQ_AVAILABLE = True
    logger.info(f"Groq LLM ready ({MODEL_PRIMARY}) for signal aggregation.")
except Exception as e:
    groq_llm = None
    GROQ_AVAILABLE = False
    logger.warning(f"Groq LLM not available: {e}")


# ── DB Helper: Store final signal ─────────────────────────────────────────────

def _init_db() -> None:
    """Ensure predictions SQLite table exists."""
    PREDICTIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PREDICTIONS_DB))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                date                 TEXT NOT NULL,
                ticker               TEXT NOT NULL,
                predicted_direction  TEXT,
                final_confidence     REAL,
                signal_strength      TEXT,
                alert_text           TEXT,
                actual_direction     TEXT,
                actual_change_pct    REAL,
                was_correct          INTEGER,
                created_at           TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON predictions (date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON predictions (ticker)")
        conn.commit()
    finally:
        conn.close()


def _save_signal_to_db(signal: FinalSignal) -> None:
    """
    Persist a FinalSignal to SQLite AND Supabase.

    SQLite  : local fallback (for dev / dashboard on same machine).
    Supabase: cloud persistence — REQUIRED for GitHub Actions runs,
              since the runner's local filesystem is wiped after each run.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = {
        "date":                today,
        "ticker":              signal["ticker"],
        "predicted_direction": signal["final_direction"],
        "final_confidence":    signal["final_confidence"],
        "signal_strength":     signal["signal_strength"],
        "alert_text":          signal["alert_text"],
        "created_at":          signal["generated_at"],
    }

    # ── Write to local SQLite ─────────────────────────────────────────────────
    _init_db()
    try:
        conn = sqlite3.connect(str(PREDICTIONS_DB))
        conn.execute(
            """INSERT INTO predictions
               (date, ticker, predicted_direction, final_confidence,
                signal_strength, alert_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                row["date"], row["ticker"], row["predicted_direction"],
                row["final_confidence"], row["signal_strength"],
                row["alert_text"], row["created_at"],
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"SQLite save failed for {signal['ticker']}: {e}")

    # ── Write to Supabase (cloud persistence for GitHub Actions) ──────────────
    try:
        from config.settings import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            sb = create_client(SUPABASE_URL, SUPABASE_KEY)
            # upsert on (date, ticker) — prevents duplicate rows if pipeline re-runs
            sb.table("predictions").upsert(
                row,
                on_conflict="date,ticker",
            ).execute()
            logger.debug(f"Supabase upsert OK: {signal['ticker']} {today}")
    except Exception as e:
        logger.warning(f"Supabase save failed for {signal['ticker']}: {e}")


# ── Core Aggregation Function ─────────────────────────────────────────────────

def aggregate_stock_signals(
    ticker: str,
    news_impact_scores: List[ImpactScore],
    ml_prediction: Optional[MLPrediction],
    current_price: float,
) -> FinalSignal:
    """
    Combine all news + ML signals into one FinalSignal for a stock.

    Args:
        ticker:             NIFTY 50 ticker symbol
        news_impact_scores: All ImpactScore objects for this ticker
        ml_prediction:      MLPrediction from the ML pipeline (can be None)
        current_price:      Latest closing price (for context)

    Returns:
        FinalSignal TypedDict — complete signal with reasoning and alert text
    """
    stock_info   = ACTIVE_STOCKS.get(ticker, {})
    company_name = stock_info.get("name", ticker)
    now_iso      = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Aggregate multiple news signals into one ──────────────────────
    # Weight by: recency (position in list), severity, confidence
    severity_weight = {"major": 3.0, "moderate": 2.0, "minor": 1.0}
    total_weight    = 0.0
    weighted_prob   = 0.0

    for i, score in enumerate(news_impact_scores):
        # Recency weight: later items (more recent) get higher weight
        recency_w  = 1.0 + (i / max(len(news_impact_scores), 1)) * 0.5
        sev_w      = severity_weight.get(score.get("severity", "minor"), 1.0)
        conf       = float(score.get("confidence", 0.4))
        direction  = score.get("direction", "neutral")

        # Convert direction to probability
        if direction == "bullish":
            prob = 0.5 + conf * 0.5
        elif direction == "bearish":
            prob = 0.5 - conf * 0.5
        else:
            prob = 0.5

        w = recency_w * sev_w
        weighted_prob += prob * w
        total_weight  += w

    if total_weight > 0:
        news_prob  = weighted_prob / total_weight
        news_dir   = "bullish" if news_prob > 0.5 else ("bearish" if news_prob < 0.5 else "neutral")
        news_conf  = abs(news_prob - 0.5) * 2
        news_sev   = max(
            (s.get("severity", "minor") for s in news_impact_scores),
            key=lambda x: severity_weight.get(x, 0),
            default="minor",
        )
        consolidated_news = {
            "direction":  news_dir,
            "confidence": round(news_conf, 4),
            "severity":   news_sev,
            "reasoning":  "; ".join(
                s.get("reasoning", "")[:60] for s in news_impact_scores[:2]
            ),
        }
    else:
        consolidated_news = {"direction": "neutral", "confidence": 0.0,
                             "severity": "minor", "reasoning": "No news signals"}

    # ── Step 2: Combine with ML signal ────────────────────────────────────────
    if ml_prediction:
        ml_signal_dict = {
            "ticker":               ticker,
            "final_probability_up": ml_prediction.get("final_probability_up", 0.5),
            "final_direction":      ml_prediction.get("final_direction", "bearish"),
            "final_confidence":     ml_prediction.get("final_confidence", 0.0),
        }
        combined = combine_with_news_signal(ml_signal_dict, consolidated_news)
        final_prob  = combined["final_probability_up"]
        final_dir   = combined["final_direction"]
        final_conf  = combined["final_confidence"]
        conflicting = combined.get("conflicting_signals", False)
    else:
        # News-only signal (no ML prediction available)
        final_prob  = 0.5 + consolidated_news["confidence"] * 0.5 * (1 if news_dir == "bullish" else -1)
        final_dir   = consolidated_news["direction"]
        final_conf  = consolidated_news["confidence"] * 0.8  # Penalise news-only
        conflicting = False

    final_prob = max(0.01, min(0.99, final_prob))
    final_conf = max(0.0, min(1.0, final_conf))

    # ── Step 3: Signal strength ───────────────────────────────────────────────
    # Thresholds: weak < CONFIDENCE_THRESHOLD(0.55) ≤ moderate < 0.7 ≤ strong
    if final_conf < CONFIDENCE_THRESHOLD:
        strength = "weak"
    elif final_conf < 0.70:
        strength = "moderate"
    else:
        strength = "strong"

    # ── Step 4: Groq 70B final reasoning (only for signals above threshold) ───
    reasoning_chain = ""
    key_risks       = ""
    valid_sessions  = 2  # Default: signal valid for 2 trading sessions

    if final_conf >= CONFIDENCE_THRESHOLD and GROQ_AVAILABLE and groq_llm and ml_prediction:
        shap_features = ml_prediction.get("top_shap_features", [])[:3]
        shap_str = ", ".join(
            f"{f['feature_name']} ({f['direction']})" for f in shap_features
        ) if shap_features else "N/A"

        news_summary = "; ".join(
            f"{s.get('direction','?')} ({s.get('severity','?')}, conf={s.get('confidence',0):.2f})"
            for s in news_impact_scores[:3]
        ) or "No news"

        prompt = f"""You are a senior NIFTY 50 equity analyst.

Stock: {company_name} ({ticker})
Current price: ₹{current_price:.2f}
Market regime: {ml_prediction.get("market_regime", "unknown")}

Signals:
- News signals: {news_summary}
- ML prediction: {ml_prediction.get("final_direction","?")} (confidence={ml_prediction.get("final_confidence",0):.2f})
- Combined direction: {final_dir} (probability_up={final_prob:.3f})
- Top ML features: {shap_str}
- Conflicting signals: {conflicting}

Provide a concise final assessment. Return ONLY valid JSON:
{{
  "final_direction": "{final_dir}",
  "final_confidence": {round(final_conf, 3)},
  "reasoning_chain": "one paragraph explaining the key drivers",
  "key_risk_factors": "top 2 risks if this signal is wrong",
  "valid_for_sessions": 1 or 2 or 3
}}"""

        try:
            response    = groq_llm.invoke(prompt)
            content     = response.content.strip()
            json_match  = re.search(r'\{.*?\}', content, re.DOTALL)
            if json_match:
                parsed          = json.loads(json_match.group())
                reasoning_chain = parsed.get("reasoning_chain", "")
                key_risks       = parsed.get("key_risk_factors", "")
                valid_sessions  = int(parsed.get("valid_for_sessions", 2))
                # Respect LLM's confidence refinement
                llm_conf = float(parsed.get("final_confidence", final_conf))
                final_conf = round(max(0.0, min(1.0, llm_conf)), 4)
        except Exception as e:
            logger.warning(f"  {ticker}: Groq reasoning failed — {e}")

    # ── Step 5: Build alert_text (placeholder — Alert Generator fills this) ───
    conflict_tag = " | ⚡ Conflicting signals" if conflicting else ""
    alert_text   = (
        f"{'⬆' if final_dir == 'bullish' else '⬇'} "
        f"{final_dir.upper()} — {company_name} ({ticker}) | "
        f"prob_up={final_prob:.1%} | conf={final_conf:.2f}{conflict_tag}"
    )

    # ── Build FinalSignal ─────────────────────────────────────────────────────
    signal: FinalSignal = {
        "ticker":               ticker,
        "company_name":         company_name,
        "final_probability_up": round(final_prob, 4),
        "final_direction":      final_dir,
        "final_confidence":     final_conf,
        "signal_strength":      strength,
        "news_signals":         news_impact_scores,
        "ml_signal":            ml_prediction or {},
        "signals_agree":        not conflicting,
        "alert_text":           alert_text,
        "generated_at":         now_iso,
        "valid_for_sessions":   valid_sessions,
    }

    logger.info(
        f"  {ticker}: {final_dir.upper()} | prob={final_prob:.3f} | "
        f"conf={final_conf:.3f} | strength={strength} | agree={not conflicting}"
    )
    return signal


# ── LangGraph Node Function ────────────────────────────────────────────────────

def signal_aggregator_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 6 node: Signal Aggregator.

    Collects all tickers with news scores or ML predictions,
    calls aggregate_stock_signals() per ticker, sorts by confidence.

    Args:
        state: MarketPulseState with impact_scores and ml_predictions

    Returns:
        Updated state with state["final_signals"] populated.
    """
    logger.info("=" * 55)
    logger.info("Agent 6: Signal Aggregator — starting")
    logger.info("=" * 55)

    impact_scores   = state.get("impact_scores", [])
    ml_predictions  = state.get("ml_predictions", [])
    current_prices  = state.get("current_prices", {})
    errors          = list(state.get("errors", []))

    # ── Group impact scores by ticker ─────────────────────────────────────────
    scores_by_ticker: Dict[str, List[ImpactScore]] = {}
    for score in impact_scores:
        t = score.get("ticker", "")
        if t:
            scores_by_ticker.setdefault(t, []).append(score)

    # ── Build ML predictions lookup ───────────────────────────────────────────
    ml_by_ticker: Dict[str, MLPrediction] = {
        p.get("ticker", ""): p for p in ml_predictions if p.get("ticker")
    }

    # ── Union of all tickers from news + ML ───────────────────────────────────
    all_tickers = set(scores_by_ticker.keys()) | set(ml_by_ticker.keys())
    logger.info(
        f"Processing {len(all_tickers)} tickers "
        f"(news:{len(scores_by_ticker)}, ml:{len(ml_by_ticker)})"
    )

    final_signals: List[FinalSignal] = []

    for ticker in sorted(all_tickers):
        try:
            news_scores   = scores_by_ticker.get(ticker, [])
            ml_pred       = ml_by_ticker.get(ticker)
            current_price = current_prices.get(ticker, 0.0)

            signal = aggregate_stock_signals(
                ticker            = ticker,
                news_impact_scores = news_scores,
                ml_prediction     = ml_pred,
                current_price     = current_price,
            )
            final_signals.append(signal)

            # Persist to SQLite
            try:
                _save_signal_to_db(signal)
            except Exception as e:
                logger.debug(f"  {ticker}: DB save failed — {e}")

        except Exception as e:
            msg = f"Agent6: Failed for {ticker}: {e}"
            logger.error(msg)
            errors.append(msg)

    # ── Sort by confidence descending (strongest first) ───────────────────────
    final_signals.sort(key=lambda x: x["final_confidence"], reverse=True)

    # Stats
    bullish = sum(1 for s in final_signals if s["final_direction"] == "bullish")
    bearish = sum(1 for s in final_signals if s["final_direction"] == "bearish")
    strong  = sum(1 for s in final_signals if s["signal_strength"] == "strong")

    logger.info(
        f"Agent 6 complete: {len(final_signals)} signals "
        f"[bullish={bullish}, bearish={bearish}, strong={strong}]"
    )

    return {
        **state,
        "final_signals": final_signals,
        "errors":        errors,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("MarketPulse AI -- Signal Aggregator Module")
    logger.info(f"  Groq LLM: {'OK' if GROQ_AVAILABLE else 'NOT AVAILABLE'}")
    logger.info(f"  Confidence threshold: {CONFIDENCE_THRESHOLD}")

    # Quick test — no real data needed
    test_ml: MLPrediction = {
        "ticker":              "TCS.NS",
        "lgbm_probability_up": 0.68,
        "lgbm_direction":      "bullish",
        "chronos_direction":   "bullish",
        "chronos_confidence":  0.72,
        "market_regime":       "bull",
        "final_probability_up": 0.701,
        "final_direction":     "bullish",
        "final_confidence":    0.40,
        "signals_agree":       True,
        "top_shap_features":   [
            {"feature_name": "rsi_14", "shap_value": 0.023, "direction": "positive"},
            {"feature_name": "macd", "shap_value": 0.018, "direction": "positive"},
        ],
    }

    test_news: List[ImpactScore] = [
        {
            "ticker": "TCS.NS", "article_id": "test_001",
            "severity": "moderate", "direction": "bullish", "confidence": 0.72,
            "reasoning": "USD strengthening boosts TCS revenue in INR terms",
            "historical_precedent": "No precedent", "timestamp": "2025-06-15T10:00:00Z",
        }
    ]

    signal = aggregate_stock_signals("TCS.NS", test_news, test_ml, 2162.0)
    logger.info(f"\nTest signal: {signal['final_direction'].upper()} | conf={signal['final_confidence']:.3f}")
    logger.info("Signal Aggregator module OK.")
