"""
agents/relevance_filter.py — MarketPulse AI
=============================================
Blueprint Part 12: Agent 2 — Relevance Filter.

4-stage pipeline that filters raw news articles.
Only articles passing ALL stages reach the expensive Groq LLM (Stage 4).
This saves API quota — 95%+ of cricket/Bollywood noise is discarded in Stage 1.

Stage Flow:
  Stage 1 — Keyword Blocklist  : discard cricket, Bollywood, etc.
  Stage 2 — spaCy NER          : must mention NIFTY entity or macro keyword
  Stage 3 — FinBERT Sentiment  : must be financial text (not tech/sports news)
  Stage 4 — Groq LLM check     : final confirmation with few-shot prompt

Filter stats (typical):
  100 raw articles → 40 pass Stage 1 → 25 pass Stage 2 →
  20 pass Stage 3 → 12 pass Stage 4 → 12 relevant articles

All heavy models (spaCy, FinBERT) are initialized at MODULE LEVEL.
This means they load once when the agents module is imported, not per-call.
Rule 8 in LLM_INSTRUCTIONS: never import heavy models inside functions.
"""

import json
import logging
import re
from typing import List, Optional, Tuple

from agents.state import FilteredArticle, MarketPulseState, NewsArticle
from config.sector_knowledge import KEYWORD_BLOCKLIST, MARKET_RELEVANT_ENTITIES
from config.settings import GROQ_API_KEY, MODEL_SECONDARY

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("relevance_filter")

# ── Module-level model initialization (load once, reuse forever) ───────────────

# spaCy NER model
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
    logger.info("spaCy en_core_web_sm loaded.")
except OSError:
    SPACY_AVAILABLE = False
    nlp = None
    logger.warning(
        "spaCy en_core_web_sm not found. "
        "Run: python -m spacy download en_core_web_sm"
    )
except ImportError:
    SPACY_AVAILABLE = False
    nlp = None
    logger.warning("spaCy not installed. Run: pip install spacy")

# FinBERT — financial sentiment classifier
try:
    from transformers import pipeline as hf_pipeline
    finbert = hf_pipeline(
        "text-classification",
        model="ProsusAI/finbert",
        device=-1,           # CPU — no GPU needed
        truncation=True,
        max_length=512,
    )
    FINBERT_AVAILABLE = True
    logger.info("FinBERT (ProsusAI/finbert) loaded.")
except Exception as e:
    finbert = None
    FINBERT_AVAILABLE = False
    logger.warning(f"FinBERT not available: {e}")

# Groq LLM for Stage 4 (Llama 3.1 8B — faster + cheaper than 70B for simple classification)
try:
    from langchain_groq import ChatGroq
    groq_llm = ChatGroq(
        model=MODEL_SECONDARY,
        api_key=GROQ_API_KEY,
        temperature=0,        # Deterministic for classification
        max_tokens=100,       # Only need short JSON response
    )
    GROQ_AVAILABLE = True
    logger.info(f"Groq LLM ready ({MODEL_SECONDARY}).")
except Exception as e:
    groq_llm = None
    GROQ_AVAILABLE = False
    logger.warning(f"Groq LLM not available: {e}")

# Pre-build lowercase sets for fast lookups
_BLOCKLIST_SET = {kw.lower() for kw in KEYWORD_BLOCKLIST}
_ENTITY_SET    = {ent.lower() for ent in MARKET_RELEVANT_ENTITIES}

# Direct macro keywords (bypass NER — just string match)
_MACRO_KEYWORDS = {
    "crude", "rupee", "dollar", "usdinr", "fii", "dii",
    "repo rate", "inflation", "cpi", "gdp", "exports", "imports",
    "federal reserve", "fed rate", "rbi", "sebi", "nifty", "sensex",
    "trade deficit", "brent", "wti", "foreign institutional",
    "domestic institutional",
}

# Few-shot examples for Stage 4 LLM prompt
_FEW_SHOT_EXAMPLES = """
Examples of RELEVANT articles (will move Indian stock prices):
1. "RBI cuts repo rate by 25bps, third cut in a row" → {"is_relevant": true, "reason": "Rate cut directly impacts banking and NBFC stocks"}
2. "Reliance Industries Q3 profit beats estimates by 15%" → {"is_relevant": true, "reason": "Major earnings beat for a top NIFTY stock"}
3. "Crude oil surges 4% as OPEC cuts production" → {"is_relevant": true, "reason": "Crude price impacts BPCL, ONGC, paint stocks, aviation"}
4. "FII bought Rs 8000 crore in Indian equities today" → {"is_relevant": true, "reason": "FII buying is a strong bullish signal for NIFTY"}
5. "SEBI issues new margin requirements for F&O traders" → {"is_relevant": true, "reason": "Regulatory change affects F&O volumes and stock volatility"}

Examples of NOT RELEVANT articles:
1. "India vs Australia cricket series schedule announced" → {"is_relevant": false, "reason": "Sports news, no market impact"}
2. "Bollywood actress announces new film project" → {"is_relevant": false, "reason": "Entertainment news"}
3. "Best tourist places to visit in Rajasthan" → {"is_relevant": false, "reason": "Travel content"}
4. "New recipe for biryani goes viral on social media" → {"is_relevant": false, "reason": "Food/social media, no market relevance"}
5. "Weather forecast: monsoon to arrive early this year" → {"is_relevant": false, "reason": "Weather without commodity/agriculture impact"}
"""


# ── Stage 1: Keyword Blocklist ─────────────────────────────────────────────────

def stage1_blocklist(article: NewsArticle) -> bool:
    """
    Stage 1: Reject articles containing any blocklist keyword.
    Fast string match — runs in microseconds.

    Args:
        article: NewsArticle dict

    Returns:
        True  = passes (no blocklist keyword found)
        False = rejected (blocklist keyword found)
    """
    text = (article["title"] + " " + article["body"]).lower()

    for keyword in _BLOCKLIST_SET:
        if keyword in text:
            logger.debug(f"  Stage1 REJECT: '{keyword}' found in '{article['title'][:50]}'")
            return False
    return True


# ── Stage 2: NER Entity Check ──────────────────────────────────────────────────

def stage2_entity_check(article: NewsArticle) -> bool:
    """
    Stage 2: Article must mention at least one market-relevant entity.

    Uses two methods:
      A. spaCy NER → extracts ORG/GPE entities → checks against MARKET_RELEVANT_ENTITIES
      B. Direct substring search for macro keywords (faster, no NER needed)

    Returns:
        True  = passes (relevant entity/keyword found)
        False = rejected (no market-relevant mention)
    """
    # Check area: title + first 300 chars of body
    text = (article["title"] + " " + article["body"][:300]).lower()

    # Method B: Direct macro keyword search (fast, no spaCy needed)
    for kw in _MACRO_KEYWORDS:
        if kw in text:
            return True

    # Also check entity set directly via substring
    for entity in _ENTITY_SET:
        if entity in text:
            return True

    # Method A: spaCy NER (only if spaCy is available and direct match failed)
    if SPACY_AVAILABLE and nlp is not None:
        try:
            doc = nlp(article["title"] + " " + article["body"][:300])
            for ent in doc.ents:
                if ent.label_ in ("ORG", "GPE", "MONEY", "PRODUCT"):
                    if ent.text.lower() in _ENTITY_SET:
                        return True
        except Exception as e:
            logger.debug(f"  Stage2 NER error: {e}")

    logger.debug(f"  Stage2 REJECT: no relevant entity in '{article['title'][:50]}'")
    return False


# ── Stage 3: FinBERT Sentiment ────────────────────────────────────────────────

def stage3_finbert(article: NewsArticle) -> Tuple[str, float]:
    """
    Stage 3: Run FinBERT financial sentiment classifier on article title.

    FinBERT is trained on financial text — it helps discard tech news, sports
    scores, or other non-financial text that slipped past Stage 2.

    Even neutral sentiment passes (e.g. "RBI holds rates" is neutral but relevant).
    Only truly non-financial text (very low FinBERT score) is rejected.

    Args:
        article: NewsArticle dict

    Returns:
        Tuple[str, float]: (sentiment_label, confidence_score)
        sentiment_label: "positive" / "negative" / "neutral"
    """
    if not FINBERT_AVAILABLE or finbert is None:
        # If FinBERT unavailable, pass all articles through (graceful degradation)
        return "neutral", 0.5

    try:
        result = finbert(article["title"][:512])[0]
        label  = result["label"].lower()   # "positive" / "negative" / "neutral"
        score  = float(result["score"])
        return label, score
    except Exception as e:
        logger.debug(f"  Stage3 FinBERT error: {e}")
        return "neutral", 0.5


# ── Stage 4: Groq LLM Final Check ────────────────────────────────────────────

def stage4_llm_check(article: NewsArticle) -> Tuple[bool, str]:
    """
    Stage 4: Ask Groq LLM (Llama 3.1 8B) whether this article can move Indian stock prices.

    Uses few-shot prompting with 5 relevant + 5 irrelevant examples.
    Only articles passing Stages 1-3 reach here (saves API quota).

    Args:
        article: NewsArticle dict

    Returns:
        Tuple[bool, str]: (is_relevant, reason)
    """
    if not GROQ_AVAILABLE or groq_llm is None:
        # If Groq unavailable, assume relevant (conservative — better to over-include)
        logger.warning("  Stage4: Groq unavailable — defaulting to relevant=True")
        return True, "Groq unavailable — defaulted to relevant"

    prompt = f"""You are a financial news analyst for Indian stock markets.

{_FEW_SHOT_EXAMPLES}

Now classify this article:
Title: "{article['title']}"
Source: {article['source']}
Snippet: "{article['body'][:200]}"

Question: Does this article have the potential to move Indian NIFTY 50 stock prices in the next 1-3 trading sessions?

Respond with ONLY valid JSON (no markdown, no explanation):
{{"is_relevant": true/false, "reason": "brief one-line reason"}}"""

    try:
        response = groq_llm.invoke(prompt)
        content  = response.content.strip()

        # Extract JSON from response (handle cases where LLM adds extra text)
        json_match = re.search(r'\{.*?\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            is_relevant = bool(parsed.get("is_relevant", False))
            reason      = str(parsed.get("reason", ""))
            return is_relevant, reason
        else:
            logger.warning(f"  Stage4: Could not parse LLM JSON: {content[:100]}")
            return True, "JSON parse failed — defaulted to relevant"

    except Exception as e:
        logger.warning(f"  Stage4 LLM error: {e}")
        return True, f"LLM error — defaulted to relevant"


# ── LangGraph Node Function ────────────────────────────────────────────────────

def relevance_filter_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 2 node: Relevance Filter.

    Runs each raw article through 4 stages in order.
    Stops at first failing stage (expensive stages protected by cheap gates).

    Args:
        state: MarketPulseState with raw_articles populated

    Returns:
        Updated state with:
          - state["filtered_articles"] : List[FilteredArticle]
          - state["articles_filtered_count"]: int
    """
    logger.info("=" * 55)
    logger.info("Agent 2: Relevance Filter — starting")
    logger.info("=" * 55)

    raw_articles    = state.get("raw_articles", [])
    filtered: List[FilteredArticle] = []
    warnings = list(state.get("warnings", []))

    # Stage counters
    s1_removed = s2_removed = s3_removed = s4_removed = 0

    logger.info(f"Processing {len(raw_articles)} raw articles...")

    for article in raw_articles:

        # ── Stage 1: Blocklist ────────────────────────────────────────────────
        passed_s1 = stage1_blocklist(article)
        if not passed_s1:
            s1_removed += 1
            continue

        # ── Stage 2: NER Entity Check ─────────────────────────────────────────
        passed_s2 = stage2_entity_check(article)
        if not passed_s2:
            s2_removed += 1
            continue

        # ── Stage 3: FinBERT ──────────────────────────────────────────────────
        finbert_label, finbert_score = stage3_finbert(article)
        # Pass if FinBERT unavailable (score=0.5) OR if score > 0.5 threshold
        passed_s3 = (finbert_score >= 0.5)
        if not passed_s3:
            s3_removed += 1
            continue

        # ── Stage 4: LLM Final Confirmation (most expensive) ──────────────────
        llm_relevant, llm_reason = stage4_llm_check(article)
        if not llm_relevant:
            s4_removed += 1

        # ── Build FilteredArticle record ──────────────────────────────────────
        relevance_score = 1.0 if llm_relevant else 0.3
        if finbert_score > 0.8:
            relevance_score = min(1.0, relevance_score + 0.1)

        fa: FilteredArticle = {
            "article":             article,
            "passed_blocklist":    passed_s1,
            "passed_ner":          passed_s2,
            "finbert_sentiment":   finbert_label,
            "finbert_score":       round(finbert_score, 4),
            "llm_is_relevant":     llm_relevant,
            "llm_relevance_reason": llm_reason,
            "relevance_score":     round(relevance_score, 4),
        }

        # Only include articles confirmed relevant by LLM
        if llm_relevant:
            filtered.append(fa)

    logger.info(
        f"Agent 2 complete: {len(raw_articles)} → {len(filtered)} relevant articles "
        f"(Stage1: {s1_removed} removed, Stage2: {s2_removed}, "
        f"Stage3: {s3_removed}, Stage4: {s4_removed})"
    )

    return {
        **state,
        "filtered_articles":      filtered,
        "articles_filtered_count": len(filtered),
        "warnings":               warnings,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m agents.relevance_filter
    logger.info("MarketPulse AI -- Relevance Filter Module")
    logger.info(f"  spaCy:   {'OK' if SPACY_AVAILABLE else 'NOT AVAILABLE'}")
    logger.info(f"  FinBERT: {'OK' if FINBERT_AVAILABLE else 'NOT AVAILABLE'}")
    logger.info(f"  Groq:    {'OK' if GROQ_AVAILABLE else 'NOT AVAILABLE'}")

    # Test with synthetic articles (no network needed)
    from agents.state import create_initial_state

    test_articles = [
        {
            "id": "001", "url": "https://test.com/1",
            "title": "RBI cuts repo rate by 25bps — third consecutive cut",
            "body":  "The Reserve Bank of India MPC voted 4-2 to reduce the repo rate.",
            "source": "test", "published_at": "2025-06-15T10:00:00Z", "fetched_at": "2025-06-15T10:01:00Z",
        },
        {
            "id": "002", "url": "https://test.com/2",
            "title": "India vs Australia cricket test match Day 2 highlights",
            "body":  "Virat Kohli scored 85 runs as India reached 340 for 4.",
            "source": "test", "published_at": "2025-06-15T10:00:00Z", "fetched_at": "2025-06-15T10:01:00Z",
        },
        {
            "id": "003", "url": "https://test.com/3",
            "title": "Crude oil rises 3% on OPEC production cut announcement",
            "body":  "Brent crude jumped to $85 per barrel after OPEC+ decision.",
            "source": "test", "published_at": "2025-06-15T10:00:00Z", "fetched_at": "2025-06-15T10:01:00Z",
        },
        {
            "id": "004", "url": "https://test.com/4",
            "title": "Bollywood actress launches new skincare brand",
            "body":  "The actress said she was inspired by her grandmother's recipes.",
            "source": "test", "published_at": "2025-06-15T10:00:00Z", "fetched_at": "2025-06-15T10:01:00Z",
        },
    ]

    state = create_initial_state("manual")
    state["raw_articles"] = test_articles
    state["articles_fetched_count"] = len(test_articles)

    result = relevance_filter_node(state)
    logger.info(f"Filtered: {result['articles_filtered_count']} relevant articles")
    for fa in result["filtered_articles"]:
        logger.info(
            f"  PASS: '{fa['article']['title'][:60]}' "
            f"(finbert={fa['finbert_sentiment']}, score={fa['finbert_score']:.2f})"
        )
    logger.info("Relevance Filter module OK.")
