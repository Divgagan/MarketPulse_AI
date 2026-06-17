"""
agents/impact_scorer.py — MarketPulse AI
==========================================
Blueprint Part 14 File 1: Agent 4 — Impact Scorer.

Assesses severity and confidence of each stock-news pair using:
  1. ChromaDB RAG lookup — "Has similar news moved this stock before?"
  2. Groq LLM (Llama 3.3 70B) — "How severe is this impact? Rate 0-1."

ChromaDB serves as our long-term memory:
  - On first run: empty, all LLM calls run without precedent context
  - Over time: stores outcomes → future calls get historical precedent
  - store_outcome() is called by EOD pipeline after market close
    to record whether predictions were correct

Severity levels:
  minor    : Single-day noise, < 1% expected move (confidence < 0.5)
  moderate : Meaningful move expected, 1-3% (confidence 0.5-0.75)
  major    : High-impact event, > 3% move likely (confidence > 0.75)

Uses MODEL_PRIMARY (Llama 3.3 70B) — our most powerful model for
complex multi-factor reasoning. Only called for stocks that passed
all 3 earlier agent stages.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from agents.state import ImpactScore, MappedImpact, MarketPulseState
from config.tickers import ACTIVE_STOCKS
from config.sector_knowledge import MACRO_TRIGGERS
from config.settings import CHROMA_DIR, GROQ_API_KEY, MODEL_PRIMARY

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("impact_scorer")

# ── Module-level model initialization ─────────────────────────────────────────

# Groq LLM — MODEL_PRIMARY = Llama 3.3 70B for complex reasoning
try:
    from langchain_groq import ChatGroq
    groq_llm = ChatGroq(
        model=MODEL_PRIMARY,
        api_key=GROQ_API_KEY,
        temperature=0.1,     # Slight creativity for reasoning, but deterministic enough
        max_tokens=300,
    )
    GROQ_AVAILABLE = True
    logger.info(f"Groq LLM ready ({MODEL_PRIMARY}) for impact scoring.")
except Exception as e:
    groq_llm = None
    GROQ_AVAILABLE = False
    logger.warning(f"Groq LLM not available: {e}")

# ChromaDB — persistent vector store for historical news-impact memory
try:
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_or_create_collection(
        name="news_impact_history",
        metadata={"hnsw:space": "cosine"},  # Use cosine similarity
    )
    CHROMA_AVAILABLE = True
    logger.info(f"ChromaDB ready at {CHROMA_DIR} ({collection.count()} records)")
except Exception as e:
    chroma_client = None
    collection = None
    CHROMA_AVAILABLE = False
    logger.warning(f"ChromaDB not available: {e}")

# SentenceTransformer — embed headlines for ChromaDB similarity search
try:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    EMBEDDER_AVAILABLE = True
    logger.info("SentenceTransformer (all-MiniLM-L6-v2) loaded.")
except Exception as e:
    embedder = None
    EMBEDDER_AVAILABLE = False
    logger.warning(f"SentenceTransformer not available: {e}")

# Similarity threshold for historical precedent matching
SIMILARITY_THRESHOLD = 0.80


# ── ChromaDB RAG Functions ────────────────────────────────────────────────────

def query_historical_precedent(headline: str, ticker: str) -> str:
    """
    Search ChromaDB for past news articles similar to this headline
    that affected the same stock ticker.

    Args:
        headline: Article title to search for similar past events
        ticker:   NIFTY 50 ticker (filter by ticker in metadata)

    Returns:
        str: Human-readable precedent context for LLM prompt.
             "No close historical precedent found" if nothing relevant.
    """
    if not all([CHROMA_AVAILABLE, EMBEDDER_AVAILABLE, collection]):
        return "No historical precedent database available."

    try:
        # Embed the headline
        embedding = embedder.encode(headline).tolist()

        # Query ChromaDB with ticker filter
        results = collection.query(
            query_embeddings=[embedding],
            n_results=3,
            where={"ticker": ticker},
        )

        if not results["ids"] or not results["ids"][0]:
            return "No close historical precedent found."

        # Check similarity scores (ChromaDB returns distances, not similarities)
        distances   = results["distances"][0]
        documents   = results["documents"][0]
        metadatas   = results["metadatas"][0]

        # Distance to similarity: similarity = 1 - cosine_distance
        for i, dist in enumerate(distances):
            similarity = 1.0 - dist
            if similarity >= SIMILARITY_THRESHOLD:
                past_headline = documents[i]
                meta          = metadatas[i]
                outcome       = meta.get("actual_outcome", "unknown")
                direction     = meta.get("predicted_direction", "unknown")
                date          = meta.get("date", "unknown")

                return (
                    f"Historical precedent (similarity={similarity:.2f}): "
                    f"On {date}, similar news '{past_headline[:80]}' "
                    f"resulted in {outcome} for {ticker} "
                    f"(predicted: {direction})."
                )

        return "No close historical precedent found (similarity < threshold)."

    except Exception as e:
        logger.debug(f"ChromaDB query error for {ticker}: {e}")
        return "Historical precedent lookup failed."


def store_outcome(
    headline: str,
    ticker: str,
    predicted_direction: str,
    actual_outcome: str,
    confidence: float,
) -> None:
    """
    Store a news-impact outcome in ChromaDB for future RAG lookups.
    Called by EOD pipeline after market close when actual move is known.

    Args:
        headline:            Article title
        ticker:              Affected NIFTY 50 ticker
        predicted_direction: "bullish" / "bearish"
        actual_outcome:      e.g. "+2.3% (bullish confirmed)" or "-1.1% (bearish confirmed)"
        confidence:          Our model's confidence in the prediction (0.0-1.0)
    """
    if not all([CHROMA_AVAILABLE, EMBEDDER_AVAILABLE, collection]):
        return

    try:
        import hashlib
        doc_id    = hashlib.md5(f"{headline}_{ticker}".encode()).hexdigest()
        embedding = embedder.encode(headline).tolist()

        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[headline],
            metadatas=[{
                "ticker":              ticker,
                "predicted_direction": predicted_direction,
                "actual_outcome":      actual_outcome,
                "confidence":          str(confidence),
                "date":                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }],
        )
        logger.debug(f"Stored outcome for {ticker}: {actual_outcome}")
    except Exception as e:
        logger.warning(f"Failed to store outcome in ChromaDB: {e}")


# ── Impact Scoring ─────────────────────────────────────────────────────────────

def score_impact(mapped_impact: MappedImpact) -> List[ImpactScore]:
    """
    Score severity and confidence for each (ticker, direction) pair in a MappedImpact.

    Uses:
      1. ChromaDB RAG for historical context
      2. Groq LLM (70B) for multi-factor severity assessment

    Returns:
        List[ImpactScore] — one per affected ticker
    """
    headline         = mapped_impact["headline"]
    impact_direction = mapped_impact["impact_direction"]
    triggers         = mapped_impact["macro_triggers"]
    now_iso          = datetime.now(timezone.utc).isoformat()

    results: List[ImpactScore] = []

    for ticker, direction in impact_direction.items():
        # ── Get stock sector info ─────────────────────────────────────────────
        stock_info  = ACTIVE_STOCKS.get(ticker, {})
        sector      = stock_info.get("sector", "Unknown")
        company_name = stock_info.get("name", ticker)

        # ── RAG: Historical precedent ─────────────────────────────────────────
        precedent = query_historical_precedent(headline, ticker)

        # ── Build trigger context ─────────────────────────────────────────────
        trigger_context = ""
        for t in triggers:
            if t in MACRO_TRIGGERS:
                trigger_context += f"\n  - {t}: {MACRO_TRIGGERS[t].get('reasoning', '')[:100]}"

        # ── LLM Severity Assessment ───────────────────────────────────────────
        if GROQ_AVAILABLE and groq_llm:
            prompt = f"""You are a senior NIFTY 50 equity analyst.

Stock: {company_name} ({ticker}) — Sector: {sector}
News headline: "{headline}"
Expected direction: {direction}
Macro context:{trigger_context if trigger_context else " (none)"}
Historical precedent: {precedent}

Task: Rate the severity and confidence of this news impact on {ticker}.

Consider:
1. Is this news directly about {company_name} or indirectly via macro trigger?
2. How significant is the expected price move? (minor <1%, moderate 1-3%, major >3%)
3. Historical precedent — does past data support this?

Respond with ONLY valid JSON (no markdown, no explanation):
{{"severity": "minor/moderate/major", "confidence": 0.0-1.0, "reasoning": "one brief sentence"}}"""

            try:
                response  = groq_llm.invoke(prompt)
                content   = response.content.strip()
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)

                if json_match:
                    parsed     = json.loads(json_match.group())
                    severity   = parsed.get("severity", "minor")
                    confidence = float(parsed.get("confidence", 0.4))
                    reasoning  = parsed.get("reasoning", "")
                else:
                    severity, confidence, reasoning = "minor", 0.4, "LLM JSON parse failed"

            except Exception as e:
                logger.warning(f"  {ticker}: LLM scoring failed — {e}")
                severity, confidence, reasoning = "minor", 0.3, f"LLM error: {e}"

        else:
            # Fallback without LLM: use rule-based severity
            if triggers:
                severity, confidence = "moderate", 0.55
            else:
                severity, confidence = "minor", 0.35
            reasoning = "LLM unavailable — rule-based fallback"

        # Clamp confidence to [0.0, 1.0]
        confidence = round(max(0.0, min(1.0, confidence)), 4)

        score: ImpactScore = {
            "ticker":               ticker,
            "article_id":           mapped_impact["article_id"],
            "severity":             severity,
            "direction":            direction,
            "confidence":           confidence,
            "reasoning":            reasoning,
            "historical_precedent": precedent,
            "timestamp":            now_iso,
        }
        results.append(score)

        logger.info(
            f"  {ticker}: {direction.upper()} | {severity} | "
            f"conf={confidence:.2f} | {reasoning[:50]}"
        )

    return results


# ── LangGraph Node Function ────────────────────────────────────────────────────

def impact_scorer_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 4 node: Impact Scorer.

    Scores every (article, ticker) pair with severity + confidence.

    Args:
        state: MarketPulseState with mapped_impacts populated

    Returns:
        Updated state with state["impact_scores"] populated.
    """
    logger.info("=" * 55)
    logger.info("Agent 4: Impact Scorer — starting")
    logger.info("=" * 55)

    mapped_impacts  = state.get("mapped_impacts", [])
    all_scores: List[ImpactScore] = []
    errors = list(state.get("errors", []))

    logger.info(f"Scoring {len(mapped_impacts)} mapped impacts...")

    for mapped in mapped_impacts:
        n_tickers = len(mapped["impact_direction"])
        logger.info(
            f"  '{mapped['headline'][:50]}' → {n_tickers} stocks to score"
        )

        try:
            scores = score_impact(mapped)
            all_scores.extend(scores)
        except Exception as e:
            msg = f"Agent4: Failed to score '{mapped['headline'][:40]}': {e}"
            logger.error(msg)
            errors.append(msg)

    # Log aggregate stats
    severities = {"minor": 0, "moderate": 0, "major": 0}
    for s in all_scores:
        severities[s["severity"]] = severities.get(s["severity"], 0) + 1

    logger.info(
        f"Agent 4 complete: {len(all_scores)} impact scores "
        f"[minor={severities['minor']}, moderate={severities['moderate']}, "
        f"major={severities['major']}]"
    )

    return {
        **state,
        "impact_scores": all_scores,
        "errors":        errors,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m agents.impact_scorer
    logger.info("MarketPulse AI -- Impact Scorer Module")
    logger.info(f"  Groq LLM  : {'OK' if GROQ_AVAILABLE else 'NOT AVAILABLE'}")
    logger.info(f"  ChromaDB  : {'OK' if CHROMA_AVAILABLE else 'NOT AVAILABLE'} ({CHROMA_DIR})")
    logger.info(f"  Embedder  : {'OK' if EMBEDDER_AVAILABLE else 'NOT AVAILABLE'}")

    if CHROMA_AVAILABLE:
        logger.info(f"  DB records: {collection.count()}")

    # Test with one synthetic mapped impact
    test_impact: MappedImpact = {
        "article_id":          "test_001",
        "headline":            "RBI cuts repo rate by 25bps — third consecutive cut in 2025",
        "mentioned_companies": [],
        "macro_triggers":      ["rbi_rate_cut"],
        "affected_tickers":    ["HDFCBANK.NS", "BAJFINANCE.NS"],
        "impact_direction":    {"HDFCBANK.NS": "bullish", "BAJFINANCE.NS": "bullish"},
        "knowledge_source":    "macro_trigger",
    }

    scores = score_impact(test_impact)
    logger.info(f"\nTest scoring complete — {len(scores)} scores:")
    for s in scores:
        logger.info(
            f"  {s['ticker']}: {s['direction'].upper()} | "
            f"{s['severity']} | conf={s['confidence']:.2f}"
        )

    logger.info("Impact Scorer module OK.")
