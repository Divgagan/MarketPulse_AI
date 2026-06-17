"""
agents/alert_generator.py — MarketPulse AI
============================================
Blueprint Part 15 File 2: Agent 7 — Alert Generator.

Generates SEBI-compliant, human-readable alert text for the dashboard.
Stores all signals to SQLite predictions table with timestamp.

CRITICAL SEBI COMPLIANCE RULE:
  NEVER use words: "buy", "sell", "invest", "recommend", "purchase", "acquire"
  Use signal intelligence language only.

Functions:
  - format_signal_text(signal)  : Formats one FinalSignal → alert string
  - format_disclaimer()         : Returns fixed SEBI disclaimer text
  - alert_generator_node(state) : LangGraph Agent 7 node
"""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import List

from agents.state import FinalSignal, MarketPulseState
from config.settings import DATA_DIR

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("alert_generator")

# SQLite path (shared with signal_aggregator)
PREDICTIONS_DB = DATA_DIR / "predictions" / "predictions.db"


# ── Confidence Bar Helper ──────────────────────────────────────────────────────

def _confidence_bar(confidence: float) -> str:
    """
    Generate a visual confidence bar using block characters.

    Args:
        confidence: float 0.0-1.0

    Returns:
        str: e.g. "████░░ High" or "██░░░░ Moderate"
    """
    if confidence >= 0.75:
        return "██████ Very High"
    elif confidence >= 0.65:
        return "████░░ High"
    elif confidence >= 0.55:
        return "██░░░░ Moderate"
    else:
        return "█░░░░░ Low"


# ── Function 1: Format Signal Text ────────────────────────────────────────────

def format_signal_text(signal: FinalSignal) -> str:
    """
    Generate a SEBI-compliant, human-readable alert string for one stock signal.

    Formats differ based on direction and signal_strength:
      - bullish strong   → ⬆ BULLISH SIGNAL with full breakdown
      - bearish strong   → ⬇ BEARISH SIGNAL with full breakdown
      - weak/any         → ⟷ WEAK SIGNAL — Insufficient conviction
      - conflicting      → ⚡ CONFLICTING SIGNALS — News and ML diverge

    Args:
        signal: FinalSignal TypedDict

    Returns:
        Formatted multi-line alert string
    """
    ticker       = signal["ticker"]
    company      = signal["company_name"]
    prob_up      = signal["final_probability_up"]
    direction    = signal["final_direction"]
    confidence   = signal["final_confidence"]
    strength     = signal["signal_strength"]
    agree        = signal["signals_agree"]
    sessions     = signal["valid_for_sessions"]
    ml_signal    = signal.get("ml_signal", {})
    news_signals = signal.get("news_signals", [])

    # ── Conflicting signal ────────────────────────────────────────────────────
    if not agree and confidence < 0.35:
        return (
            f"⚡ CONFLICTING SIGNALS — {ticker} ({company})\n"
            f"   News and technical indicators diverge on direction.\n"
            f"   Probability of upward movement: {prob_up:.0%}\n"
            f"   Confidence: {_confidence_bar(confidence)}\n"
            f"   Recommendation: Monitor — insufficient signal clarity."
        )

    # ── Weak signal ───────────────────────────────────────────────────────────
    if strength == "weak" or confidence < 0.15:
        return (
            f"⟷ WEAK SIGNAL — {ticker} ({company})\n"
            f"   Insufficient conviction for a directional call.\n"
            f"   Probability of upward movement: {prob_up:.0%}\n"
            f"   Confidence: {_confidence_bar(confidence)}\n"
            f"   Note: Signal strength below threshold. No high-confidence pattern detected."
        )

    # ── Strong / Moderate signals ─────────────────────────────────────────────
    direction_icon = "⬆" if direction == "bullish" else "⬇"
    direction_text = "BULLISH" if direction == "bullish" else "BEARISH"
    prob_display   = prob_up if direction == "bullish" else (1.0 - prob_up)

    # Top SHAP features (why the ML model says this)
    shap_features  = ml_signal.get("top_shap_features", [])[:2]
    if shap_features:
        key_drivers = ", ".join(
            f"{f['feature_name'].replace('_', ' ').title()} ({f['direction']})"
            for f in shap_features
        )
    else:
        key_drivers = "Technical pattern"

    # News catalyst (most severe/recent news headline)
    news_catalyst = ""
    if news_signals:
        best_news = max(
            news_signals,
            key=lambda s: {"major": 3, "moderate": 2, "minor": 1}.get(s.get("severity", "minor"), 0)
        )
        reason = best_news.get("reasoning", "")
        if reason:
            news_catalyst = f"\n   News catalyst: {reason[:80]}"

    # Corroborating signals count
    n_corroborating = len(news_signals) + (1 if ml_signal else 0)

    # Market regime
    regime = ml_signal.get("market_regime", "unknown")

    alert = (
        f"{direction_icon} {direction_text} SIGNAL — {ticker} ({company})\n"
        f"   Probability of {'upward' if direction == 'bullish' else 'downward'} movement: {prob_display:.0%}\n"
        f"   Signal strength: {strength.title()} | Corroborating signals: {n_corroborating}\n"
        f"   Market regime: {regime.title()}\n"
        f"   Key drivers: {key_drivers}"
        f"{news_catalyst}\n"
        f"   Valid for: Next {sessions} trading session(s)\n"
        f"   Confidence: {_confidence_bar(confidence)}"
    )

    return alert


# ── Function 2: Format Disclaimer ────────────────────────────────────────────

def format_disclaimer() -> str:
    """
    Return the fixed SEBI-compliant research disclaimer text.
    This appears at the bottom of every report and dashboard page.
    """
    return (
        "⚠ RESEARCH DISCLAIMER: MarketPulse AI is a student research project for "
        "educational and informational purposes only. Signals are statistical "
        "indicators, not investment advice. We are not SEBI-registered investment "
        "advisors. Do not use these signals for actual trading decisions. "
        "Past signal accuracy does not guarantee future results."
    )


# ── LangGraph Node Function ────────────────────────────────────────────────────

def alert_generator_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 7 node: Alert Generator (final node in graph).

    For each FinalSignal:
      1. Calls format_signal_text() to generate SEBI-compliant alert
      2. Injects alert_text back into the signal object
      3. Stores signal to SQLite predictions table
      4. Adds all formatted alerts to state["alerts"]

    Args:
        state: MarketPulseState with final_signals populated

    Returns:
        Updated state with:
          - state["alerts"]        : List of formatted alert strings
          - state["final_signals"] : Updated with alert_text fields
    """
    logger.info("=" * 55)
    logger.info("Agent 7: Alert Generator — starting")
    logger.info("=" * 55)

    final_signals = state.get("final_signals", [])
    alerts: List[str] = []
    errors = list(state.get("errors", []))

    bullish_count  = 0
    bearish_count  = 0
    weak_count     = 0
    conflict_count = 0

    updated_signals = []

    for signal in final_signals:
        try:
            # ── Generate SEBI-compliant alert text ────────────────────────────
            alert_text = format_signal_text(signal)

            # ── Inject alert_text back into signal ────────────────────────────
            updated_signal = dict(signal)
            updated_signal["alert_text"] = alert_text
            updated_signals.append(updated_signal)

            alerts.append(alert_text)

            # ── Update SQLite with alert_text ──────────────────────────────────
            try:
                conn = sqlite3.connect(str(PREDICTIONS_DB))
                conn.execute(
                    "UPDATE predictions SET alert_text=? "
                    "WHERE ticker=? AND date=?",
                    (
                        alert_text[:1000],
                        signal["ticker"],
                        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    ),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.debug(f"  {signal['ticker']}: DB alert_text update failed — {e}")

            # ── Stats ─────────────────────────────────────────────────────────
            if not signal["signals_agree"] and signal["final_confidence"] < 0.35:
                conflict_count += 1
            elif signal["signal_strength"] == "weak":
                weak_count += 1
            elif signal["final_direction"] == "bullish":
                bullish_count += 1
            else:
                bearish_count += 1

        except Exception as e:
            msg = f"Agent7: Alert generation failed for {signal.get('ticker', '?')}: {e}"
            logger.error(msg)
            errors.append(msg)
            updated_signals.append(signal)

    logger.info(
        f"Agent 7 complete: {len(alerts)} alerts generated — "
        f"⬆ Bullish={bullish_count} | ⬇ Bearish={bearish_count} | "
        f"⟷ Weak={weak_count} | ⚡ Conflicting={conflict_count}"
    )

    # ── Add disclaimer to state ────────────────────────────────────────────────
    alerts.append(format_disclaimer())

    return {
        **state,
        "final_signals": updated_signals,
        "alerts":        alerts,
        "errors":        errors,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("MarketPulse AI -- Alert Generator Module")

    # Test with synthetic signals
    test_signals = [
        {
            "ticker": "RELIANCE.NS", "company_name": "Reliance Industries",
            "final_probability_up": 0.73, "final_direction": "bullish",
            "final_confidence": 0.46, "signal_strength": "strong",
            "signals_agree": True, "valid_for_sessions": 2,
            "ml_signal": {
                "market_regime": "bull",
                "top_shap_features": [
                    {"feature_name": "rsi_14", "direction": "positive"},
                    {"feature_name": "macd_histogram", "direction": "positive"},
                ],
            },
            "news_signals": [
                {"severity": "moderate", "direction": "bullish",
                 "reasoning": "OPEC cut boosts upstream oil revenue for Reliance E&P segment",
                 "confidence": 0.72},
            ],
            "alert_text": "", "generated_at": "2025-06-15T10:00:00Z",
        },
        {
            "ticker": "BPCL.NS", "company_name": "Bharat Petroleum",
            "final_probability_up": 0.28, "final_direction": "bearish",
            "final_confidence": 0.44, "signal_strength": "strong",
            "signals_agree": True, "valid_for_sessions": 1,
            "ml_signal": {"market_regime": "bear", "top_shap_features": []},
            "news_signals": [],
            "alert_text": "", "generated_at": "2025-06-15T10:00:00Z",
        },
        {
            "ticker": "TCS.NS", "company_name": "Tata Consultancy Services",
            "final_probability_up": 0.51, "final_direction": "bullish",
            "final_confidence": 0.02, "signal_strength": "weak",
            "signals_agree": False, "valid_for_sessions": 1,
            "ml_signal": {"market_regime": "sideways", "top_shap_features": []},
            "news_signals": [],
            "alert_text": "", "generated_at": "2025-06-15T10:00:00Z",
        },
    ]

    state = {
        "final_signals": test_signals, "alerts": [],
        "errors": [], "warnings": [],
        "run_timestamp": "2025-06-15T10:00:00Z", "run_type": "manual",
        "raw_articles": [], "articles_fetched_count": 0,
        "filtered_articles": [], "articles_filtered_count": 0,
        "mapped_impacts": [], "impact_scores": [],
        "current_prices": {}, "price_changes_today": {},
        "ml_predictions": [],
    }

    result = alert_generator_node(state)

    logger.info(f"\n{'='*60}")
    for alert in result["alerts"]:
        logger.info(f"\n{alert}")
    logger.info(f"\n{'='*60}")
    logger.info("Alert Generator module OK.")
