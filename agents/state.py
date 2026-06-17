"""
agents/state.py — MarketPulse AI
====================================
Blueprint Part 10: LangGraph shared state definition.

Every agent node in the pipeline reads from and writes to this shared state.
LangGraph passes the state dict through each node in the graph.

State flow through 7 agents:
  [raw_articles]       ← Agent 1 (News Harvester)
       ↓
  [filtered_articles]  ← Agent 2 (Relevance Filter)
       ↓
  [mapped_impacts]     ← Agent 3 (Entity & Sector Mapper)
       ↓
  [impact_scores]      ← Agent 4 (Impact Scorer)
       ↓
  [current_prices]     ← Agent 5 (Market Monitor)  ← runs in parallel with ML
  [ml_predictions]     ← ML Pipeline (predictor + chronos + signal_combiner)
       ↓
  [final_signals]      ← Agent 6 (Signal Aggregator)
       ↓
  [alerts]             ← Agent 7 (Alert Generator)

TypedDict classes (7 total):
  NewsArticle, FilteredArticle, MappedImpact, ImpactScore,
  MLPrediction, FinalSignal, MarketPulseState
"""

from typing import TypedDict, List, Dict, Optional, Any, Annotated
import operator


# ── NewsArticle ───────────────────────────────────────────────────────────────

class NewsArticle(TypedDict):
    """
    Raw news article as fetched by Agent 1 (News Harvester).
    Deduplication is done using MD5 hash of the URL as id.
    """
    id:           str   # MD5 hash of URL — used for SQLite deduplication
    url:          str
    title:        str
    body:         str   # Truncated to 500 chars (first paragraph only)
    source:       str   # e.g. "economic_times", "moneycontrol", "newsapi"
    published_at: str   # ISO format datetime string
    fetched_at:   str   # When our system downloaded it (ISO format)


# ── FilteredArticle ───────────────────────────────────────────────────────────

class FilteredArticle(TypedDict):
    """
    Article after passing through Agent 2's 4-stage relevance pipeline.
    Records which stages it passed and what each stage found.
    Only articles where llm_is_relevant=True are forwarded to Agent 3.
    """
    article:             NewsArticle

    # Stage 1 — Keyword blocklist (cricket, Bollywood, etc.)
    passed_blocklist:    bool

    # Stage 2 — spaCy NER (must mention NIFTY entity or macro keyword)
    passed_ner:          bool

    # Stage 3 — FinBERT financial sentiment classification
    finbert_sentiment:   str    # "positive" / "negative" / "neutral"
    finbert_score:       float  # Confidence of FinBERT classification (0.0–1.0)

    # Stage 4 — Groq LLM final relevance confirmation (most expensive, last)
    llm_is_relevant:     bool
    llm_relevance_reason: str   # Brief reason from LLM

    # Combined relevance score across all stages (0.0–1.0)
    relevance_score:     float


# ── MappedImpact ──────────────────────────────────────────────────────────────

class MappedImpact(TypedDict):
    """
    Output of Agent 3 (Entity & Sector Mapper).
    Maps one news article to specific NIFTY 50 tickers and their expected direction.

    Three mapping methods (in order of priority):
      1. Direct company mention (spaCy NER → COMPANY_TO_TICKER lookup)
      2. Macro trigger detection (rule-based: "crude oil rise" → MACRO_TRIGGERS)
      3. LLM fallback (if neither above finds anything)
    """
    article_id:         str
    headline:           str
    mentioned_companies: List[str]   # Direct company name mentions (e.g. ["Reliance", "TCS"])
    macro_triggers:      List[str]   # Detected triggers (e.g. ["crude_oil_price_increase"])
    affected_tickers:    List[str]   # Final NIFTY 50 tickers affected (e.g. ["RELIANCE.NS"])
    impact_direction:    Dict[str, str]  # {ticker: "bullish" / "bearish" / "neutral"}
    knowledge_source:    str         # "direct_mention" / "macro_trigger" / "llm_reasoning"


# ── ImpactScore ───────────────────────────────────────────────────────────────

class ImpactScore(TypedDict):
    """
    Output of Agent 4 (Impact Scorer).
    Severity + confidence rating for one stock affected by one news article.
    Also includes RAG result from ChromaDB (historical precedent lookup).
    """
    ticker:               str
    article_id:           str
    severity:             str    # "minor" / "moderate" / "major"
    direction:            str    # "bullish" / "bearish" / "neutral"
    confidence:           float  # 0.0–1.0 (LLM confidence in its assessment)
    reasoning:            str    # Full LLM reasoning chain
    historical_precedent: str    # From ChromaDB RAG: "Similar news on 2024-01-15 → +2.3% for TCS"
    timestamp:            str    # ISO format


# ── MLPrediction ──────────────────────────────────────────────────────────────

class MLPrediction(TypedDict):
    """
    Complete ML signal for one stock from the daily ML pipeline.
    Combines LightGBM + Chronos + HMM Regime into one final signal.
    Produced by signal_combiner.combine_signals().
    """
    ticker:              str
    lgbm_probability_up: float   # Raw LightGBM probability (0.0–1.0)
    lgbm_direction:      str     # "bullish" / "bearish"
    chronos_direction:   str     # "bullish" / "bearish" / "neutral"
    chronos_confidence:  float   # 0.0–1.0
    market_regime:       str     # "bull" / "bear" / "sideways"
    final_probability_up: float  # Weighted ensemble probability
    final_direction:     str     # Final direction decision
    final_confidence:    float   # 0.0–1.0
    signals_agree:       bool    # True if LightGBM + Chronos + Regime all agree
    top_shap_features:   List[Dict]  # Top 5 SHAP features from explain_prediction()


# ── FinalSignal ───────────────────────────────────────────────────────────────

class FinalSignal(TypedDict):
    """
    Complete final signal for one stock after combining ML + News signals.
    Output of Agent 6 (Signal Aggregator).
    This is what gets stored in SQLite and displayed in the dashboard.
    """
    ticker:               str
    company_name:         str
    final_probability_up: float
    final_direction:      str       # "bullish" / "bearish"
    final_confidence:     float     # 0.0–1.0
    signal_strength:      str       # "strong" (>0.3) / "moderate" (>0.15) / "weak"
    news_signals:         List[ImpactScore]  # All news items affecting this stock
    ml_signal:            MLPrediction
    signals_agree:        bool      # News and ML agree?
    alert_text:           str       # SEBI-compliant formatted alert text
    generated_at:         str       # ISO format datetime
    valid_for_sessions:   int       # How many trading sessions this signal is valid


# ── MarketPulseState ──────────────────────────────────────────────────────────

class MarketPulseState(TypedDict):
    """
    The central shared state that flows through all 7 LangGraph agent nodes.

    LangGraph passes this dict to each node function. Each node returns
    an updated version of the state dict with its output fields populated.

    run_type determines which agents run:
      "news_cycle"  → Agents 1-4 only (every 30 minutes during market hours)
      "eod_full"    → All 7 agents + full ML pipeline (3:45 PM daily)
      "manual"      → On-demand run for testing / dashboard refresh
    """

    # ── Run metadata ──────────────────────────────────────────────────────────
    run_timestamp: str      # ISO format — when this pipeline run started
    run_type:      str      # "news_cycle" / "eod_full" / "manual"

    # ── Agent 1 output: News Harvester ────────────────────────────────────────
    raw_articles:          List[NewsArticle]
    articles_fetched_count: int

    # ── Agent 2 output: Relevance Filter ──────────────────────────────────────
    filtered_articles:     List[FilteredArticle]
    articles_filtered_count: int

    # ── Agent 3 output: Entity & Sector Mapper ────────────────────────────────
    mapped_impacts:        List[MappedImpact]

    # ── Agent 4 output: Impact Scorer ─────────────────────────────────────────
    impact_scores:         List[ImpactScore]

    # ── Agent 5 output: Market Monitor ────────────────────────────────────────
    current_prices:        Dict[str, float]   # {ticker: last_close_price}
    price_changes_today:   Dict[str, float]   # {ticker: % change from yesterday}

    # ── ML Pipeline output (runs in parallel with agents 5) ───────────────────
    ml_predictions:        List[MLPrediction]

    # ── Agent 6 output: Signal Aggregator ─────────────────────────────────────
    final_signals:         List[FinalSignal]

    # ── Agent 7 output: Alert Generator ───────────────────────────────────────
    alerts:                List[str]    # SEBI-compliant alert strings

    # ── Error tracking (accumulates across all agents) ────────────────────────
    errors:   List[str]    # Non-fatal errors (pipeline continues)
    warnings: List[str]    # Warnings (logged but don't stop pipeline)


# ── Default initial state factory ─────────────────────────────────────────────

def create_initial_state(run_type: str = "news_cycle", ml_predictions: list = None) -> MarketPulseState:
    """
    Create a clean initial MarketPulseState for a new pipeline run.

    Args:
        run_type: "news_cycle" / "eod_full" / "manual"
        ml_predictions: List of pre-computed ML predictions

    Returns:
        MarketPulseState with all fields initialized to empty/zero values.
    """
    from datetime import datetime, timezone
    return MarketPulseState(
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        run_type=run_type,
        raw_articles=[],
        articles_fetched_count=0,
        filtered_articles=[],
        articles_filtered_count=0,
        mapped_impacts=[],
        impact_scores=[],
        current_prices={},
        price_changes_today={},
        ml_predictions=ml_predictions or [],
        final_signals=[],
        alerts=[],
        errors=[],
        warnings=[],
    )


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("MarketPulse AI -- State Module")
    print("Verifying all TypedDict classes...")

    # Test create_initial_state
    state = create_initial_state("eod_full")
    print(f"  run_type    : {state['run_type']}")
    print(f"  run_timestamp: {state['run_timestamp']}")
    print(f"  raw_articles : {state['raw_articles']}")

    # Test constructing a sample NewsArticle
    article: NewsArticle = {
        "id":           "abc123",
        "url":          "https://economictimes.com/markets/article",
        "title":        "RBI cuts repo rate by 25bps",
        "body":         "The Reserve Bank of India cut the repo rate...",
        "source":       "economic_times",
        "published_at": "2025-06-15T10:00:00Z",
        "fetched_at":   "2025-06-15T10:01:30Z",
    }
    print(f"  NewsArticle : {article['title']}")

    # Test MLPrediction structure
    ml_pred: MLPrediction = {
        "ticker":              "HDFCBANK.NS",
        "lgbm_probability_up": 0.673,
        "lgbm_direction":      "bullish",
        "chronos_direction":   "bullish",
        "chronos_confidence":  0.72,
        "market_regime":       "bull",
        "final_probability_up": 0.701,
        "final_direction":     "bullish",
        "final_confidence":    0.402,
        "signals_agree":       True,
        "top_shap_features":   [
            {"feature_name": "rsi_14", "shap_value": 0.023, "direction": "positive"},
        ],
    }
    print(f"  MLPrediction: {ml_pred['ticker']} → {ml_pred['final_direction'].upper()}")

    print("\nAll TypedDict classes OK.")
    print("State module imports verified.")
