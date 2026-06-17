"""
agents/entity_mapper.py — MarketPulse AI
==========================================
Blueprint Part 13: Agent 3 — Entity & Sector Mapper.

Maps filtered news articles to specific NIFTY 50 stock tickers
using three methods (in priority order):

  Method 1 — Direct company mention:
    spaCy NER finds ORG entities → COMPANY_TO_TICKER dict lookup
    Also does substring match against company names in ACTIVE_STOCKS

  Method 2 — Macro trigger detection:
    Rule-based regex patterns on lowercased text → MACRO_TRIGGERS lookup
    14 triggers: crude_oil_price_increase, rupee_depreciation, rbi_rate_cut etc.
    Each trigger maps to bullish/bearish ticker lists in sector_knowledge.py

  Method 3 — LLM fallback (most expensive, last resort):
    Only used if Methods 1+2 find no affected stocks
    Asks Groq LLM: "Which NIFTY 50 stocks are affected by: {headline}?"
    Passes ACTIVE_STOCKS list as context

LangGraph node:
  entity_mapper_node(state) → state with mapped_impacts populated
"""

import json
import logging
import re
from typing import Dict, List, Optional

from agents.state import FilteredArticle, MappedImpact, MarketPulseState
from config.tickers import COMPANY_TO_TICKER, ACTIVE_STOCKS
from config.sector_knowledge import MACRO_TRIGGERS, TRADE_DEPENDENCY_MAP
from config.settings import GROQ_API_KEY, MODEL_SECONDARY

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("entity_mapper")

# ── Module-level initialization ───────────────────────────────────────────────

# spaCy (reuse the same loaded model — don't load twice)
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    nlp = None
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available — entity mapper will use string matching only")

# Groq LLM (LLM fallback for articles with no matched stocks)
try:
    from langchain_groq import ChatGroq
    groq_llm = ChatGroq(
        model=MODEL_SECONDARY,
        api_key=GROQ_API_KEY,
        temperature=0,
        max_tokens=300,
    )
    GROQ_AVAILABLE = True
except Exception as e:
    groq_llm = None
    GROQ_AVAILABLE = False
    logger.warning(f"Groq not available for entity mapper: {e}")

# Pre-build lowercase COMPANY_TO_TICKER for fast matching
_COMPANY_TO_TICKER_LOWER = {k.lower(): v for k, v in COMPANY_TO_TICKER.items()}

# Build a name→ticker map from ACTIVE_STOCKS for additional matching
_NIFTY50_NAMES_LOWER: Dict[str, str] = {}
for ticker, info in ACTIVE_STOCKS.items():
    name = info.get("name", "")
    if name:
        _NIFTY50_NAMES_LOWER[name.lower()] = ticker
        # Also add short name variants
        short = name.split()[0].lower()   # e.g. "reliance" from "Reliance Industries"
        if len(short) > 4:               # avoid short noise words
            _NIFTY50_NAMES_LOWER[short] = ticker

# NIFTY50 tickers list (formatted for LLM prompt)
_NIFTY50_LIST_STR = "\n".join(
    f"  {ticker}: {info.get('name', ticker)}"
    for ticker, info in ACTIVE_STOCKS.items()
)


# ── Macro Trigger Patterns ────────────────────────────────────────────────────
# Each pattern is: (regex_condition_A, optional_regex_condition_B, trigger_name)
# Both conditions must match if B is specified.

_MACRO_PATTERNS = [
    # Crude oil
    (r"crude.oil", r"(rise|up|spike|high|surge|jump|soar)", "crude_oil_price_increase"),
    (r"crude.oil", r"(fall|down|drop|low|decline|crash|slump)", "crude_oil_price_decrease"),
    (r"brent.crude", r"(rise|up|spike|high|surge|jump)", "crude_oil_price_increase"),
    (r"brent.crude", r"(fall|down|drop|low|decline)", "crude_oil_price_decrease"),

    # Rupee / FX
    (r"rupee", r"(weaken|depreciat|fall|low|slide|plunge|tumble)", "rupee_depreciation"),
    (r"rupee", r"(strengthen|appreciat|rise|high|surge|jump)", "rupee_appreciation"),
    (r"usdinr", r"(rise|high|jump)", "rupee_depreciation"),
    (r"usdinr", r"(fall|low|drop)", "rupee_appreciation"),

    # RBI rates
    (r"(repo.rate|rbi.rate|rbi.policy)", r"(hike|increas|rais|tighten)", "rbi_rate_hike"),
    (r"(repo.rate|rbi.rate|rbi.policy)", r"(cut|decreas|lower|reduc|dovish)", "rbi_rate_cut"),
    (r"rbi.holds", None, None),           # Neutral — no trigger

    # US Fed
    (r"(federal.reserve|us.fed|fed.rate|fomc)", r"(hike|increas|rais|tighten)", "us_fed_rate_hike"),

    # FII flows
    (r"fii", r"(sell|outflow|exit|withdrew|dump)", "fii_selloff"),
    (r"fii", r"(buy|inflow|invest|purchas|enter)", "fii_buying"),
    (r"(foreign.institutional|foreign.portfolio|fpi)", r"(sell|outflow|exit)", "fii_selloff"),
    (r"(foreign.institutional|foreign.portfolio|fpi)", r"(buy|inflow|invest)", "fii_buying"),

    # India-China
    (r"(india.china|india.*china.*border|china.*india.*tension)", r"(tension|conflict|border|dispute|military)", "india_china_tension"),

    # GDP
    (r"(india.gdp|gdp.growth|economic.growth)", r"(strong|beat|exceed|surpass|above)", "india_gdp_strong"),

    # Sanctions
    (r"sanction", r"(russia|china|iran|country|nation)", "us_sanctions_on_country"),

    # Budget
    (r"(union.budget|budget.2025|budget.speech)", r"(capex|infrastructure|spend|invest)", "budget_announcement_capex"),

    # Coal
    (r"coal", r"(price|rise|spike|high|surge)", "coal_price_rise"),

    # Global recession
    (r"(recession|economic.slowdown|global.slowdown)", r"(fear|risk|concern|warn)", "global_recession_fear"),

    # EV
    (r"electric.vehicle|ev.adoption|ev.sales", None, "ev_adoption_acceleration"),

    # Semiconductor
    (r"(semiconductor|chip.shortage|chip.supply)", None, "semiconductor_shortage"),
]


# ── Function 1: Extract Direct Company Mentions ────────────────────────────────

def extract_direct_mentions(text: str) -> List[str]:
    """
    Find NIFTY 50 tickers directly mentioned in the article.

    Two methods:
      A. String matching against COMPANY_TO_TICKER (company names)
      B. spaCy NER → ORG entities → lookup in COMPANY_TO_TICKER

    Args:
        text: article title + body (lowercased)

    Returns:
        List of matched NIFTY 50 ticker symbols (deduplicated)
    """
    tickers: set = set()
    text_lower = text.lower()

    # Method A: Direct substring match against all known company names
    for company_lower, ticker in _COMPANY_TO_TICKER_LOWER.items():
        if company_lower in text_lower:
            tickers.add(ticker)

    # Also check ACTIVE_STOCKS names
    for name_lower, ticker in _NIFTY50_NAMES_LOWER.items():
        if name_lower in text_lower:
            tickers.add(ticker)

    # Method B: spaCy NER for ORG entities (catches variants like "RIL" for Reliance)
    if SPACY_AVAILABLE and nlp is not None:
        try:
            doc = nlp(text[:500])    # Limit to 500 chars for speed
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    ent_lower = ent.text.lower().strip()
                    # Look up spaCy-detected org in our company map
                    if ent_lower in _COMPANY_TO_TICKER_LOWER:
                        tickers.add(_COMPANY_TO_TICKER_LOWER[ent_lower])
        except Exception as e:
            logger.debug(f"NER error in extract_direct_mentions: {e}")

    return list(tickers)


# ── Function 2: Detect Macro Triggers ────────────────────────────────────────

def detect_macro_triggers(text: str) -> List[str]:
    """
    Detect macro/economic trigger patterns in article text using regex.

    Args:
        text: article title + body (should be lowercased already)

    Returns:
        List of detected trigger names (keys in MACRO_TRIGGERS)
    """
    text_lower = text.lower()
    detected: set = set()

    for pattern in _MACRO_PATTERNS:
        pattern_a, pattern_b, trigger_name = pattern

        if trigger_name is None:
            continue  # Explicit neutral patterns (like "rbi holds") — skip

        # Check pattern A
        if not re.search(pattern_a, text_lower):
            continue

        # Check pattern B if specified
        if pattern_b and not re.search(pattern_b, text_lower):
            continue

        detected.add(trigger_name)

    return list(detected)


# ── Function 3: Lookup Affected Stocks from Knowledge Graph ───────────────────

def lookup_affected_stocks(
    triggers: List[str],
    direct_mentions: List[str],
) -> Dict[str, str]:
    """
    Map detected triggers + direct mentions → {ticker: direction} dict.

    Direct mentions take priority (override trigger-based direction).
    When a trigger is bullish+bearish for the same ticker (rare), bearish wins.

    Args:
        triggers:        List of detected macro trigger names
        direct_mentions: List of tickers directly mentioned in article

    Returns:
        Dict: {ticker: "bullish" / "bearish" / "neutral"}
    """
    result: Dict[str, str] = {}

    # Step 1: Populate from MACRO_TRIGGERS knowledge graph
    for trigger in triggers:
        if trigger not in MACRO_TRIGGERS:
            continue

        trigger_data = MACRO_TRIGGERS[trigger]
        bullish_tickers = trigger_data.get("bullish", [])
        bearish_tickers = trigger_data.get("bearish", [])

        for ticker in bullish_tickers:
            if ticker not in result:
                result[ticker] = "bullish"

        for ticker in bearish_tickers:
            # Bearish overrides if previously set to bullish (conservative)
            result[ticker] = "bearish"

    # Step 2: Add directly mentioned tickers (direction set to neutral if unknown)
    for ticker in direct_mentions:
        if ticker not in result:
            result[ticker] = "neutral"  # Direct mention but no trigger direction

    return result


# ── LLM Fallback ──────────────────────────────────────────────────────────────

def _llm_fallback_mapping(article: FilteredArticle) -> Dict[str, str]:
    """
    Last resort: ask Groq LLM which NIFTY 50 stocks are affected.
    Only called when Methods 1+2 return zero matches.

    Returns:
        Dict: {ticker: "bullish" / "bearish" / "neutral"}
        Empty dict if LLM unavailable or call fails.
    """
    if not GROQ_AVAILABLE or groq_llm is None:
        return {}

    headline = article["article"]["title"]
    body_snippet = article["article"]["body"][:200]

    prompt = f"""You are a NIFTY 50 stock market analyst.

Here is the full list of NIFTY 50 stocks:
{_NIFTY50_LIST_STR}

News article:
Title: "{headline}"
Snippet: "{body_snippet}"

Question: Which NIFTY 50 stocks from the list above are directly or indirectly affected by this news?
For each affected stock, state whether the impact is bullish or bearish.

Return ONLY valid JSON in this exact format:
{{"TICKER.NS": "bullish", "TICKER2.NS": "bearish"}}

If no NIFTY 50 stock is clearly affected, return: {{}}
Do not explain. Return only JSON."""

    try:
        response = groq_llm.invoke(prompt)
        content  = response.content.strip()

        # Extract JSON from response
        json_match = re.search(r'\{.*?\}', content, re.DOTALL)
        if not json_match:
            return {}

        parsed = json.loads(json_match.group())

        # Validate: only include tickers that are actually in ACTIVE_STOCKS
        valid = {}
        for ticker, direction in parsed.items():
            ticker = ticker.strip()
            if ticker in ACTIVE_STOCKS and direction.lower() in ("bullish", "bearish", "neutral"):
                valid[ticker] = direction.lower()

        logger.info(f"  LLM fallback found {len(valid)} stocks: {list(valid.keys())[:5]}")
        return valid

    except Exception as e:
        logger.warning(f"  LLM fallback mapping failed: {e}")
        return {}


# ── LangGraph Node Function ────────────────────────────────────────────────────

def entity_mapper_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 3 node: Entity & Sector Mapper.

    Maps each filtered article to specific NIFTY 50 tickers and their
    expected directional impact.

    Args:
        state: MarketPulseState with filtered_articles populated

    Returns:
        Updated state with state["mapped_impacts"] populated.
    """
    logger.info("=" * 55)
    logger.info("Agent 3: Entity & Sector Mapper — starting")
    logger.info("=" * 55)

    filtered_articles = state.get("filtered_articles", [])
    mapped_impacts: List[MappedImpact] = []
    errors = list(state.get("errors", []))

    direct_total = trigger_total = llm_total = empty_total = 0

    for fa in filtered_articles:
        article  = fa["article"]
        headline = article["title"]
        full_text = headline + " " + article["body"]

        # ── Method 1: Direct company mentions ────────────────────────────────
        direct_mentions = extract_direct_mentions(full_text)

        # ── Method 2: Macro trigger detection ────────────────────────────────
        triggers = detect_macro_triggers(full_text)

        # ── Map to {ticker: direction} ────────────────────────────────────────
        impact_direction = lookup_affected_stocks(triggers, direct_mentions)

        # ── Method 3: LLM fallback if nothing found ───────────────────────────
        knowledge_source = "direct_mention" if direct_mentions else "macro_trigger" if triggers else None

        if not impact_direction:
            impact_direction = _llm_fallback_mapping(fa)
            knowledge_source = "llm_reasoning" if impact_direction else None
            if impact_direction:
                llm_total += 1
            else:
                empty_total += 1
        elif direct_mentions and triggers:
            knowledge_source = "direct_mention"  # Direct mention takes priority label
            direct_total += 1
        elif direct_mentions:
            direct_total += 1
        else:
            trigger_total += 1

        # ── Build MappedImpact object ─────────────────────────────────────────
        affected_tickers = list(impact_direction.keys())

        impact: MappedImpact = {
            "article_id":         article["id"],
            "headline":           headline,
            "mentioned_companies": direct_mentions,
            "macro_triggers":     triggers,
            "affected_tickers":   affected_tickers,
            "impact_direction":   impact_direction,
            "knowledge_source":   knowledge_source or "none",
        }

        mapped_impacts.append(impact)

        logger.info(
            f"  '{headline[:55]}...' → "
            f"{len(affected_tickers)} stocks "
            f"({knowledge_source or 'no_match'}) "
            f"triggers={triggers}"
        )

    logger.info(
        f"Agent 3 complete: {len(mapped_impacts)} articles mapped "
        f"[direct={direct_total}, trigger={trigger_total}, "
        f"llm={llm_total}, empty={empty_total}]"
    )

    return {
        **state,
        "mapped_impacts": mapped_impacts,
        "errors":         errors,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m agents.entity_mapper
    logger.info("MarketPulse AI -- Entity Mapper Module")
    logger.info(f"  spaCy:   {'OK' if SPACY_AVAILABLE else 'NOT AVAILABLE'}")
    logger.info(f"  Groq:    {'OK' if GROQ_AVAILABLE else 'NOT AVAILABLE'}")
    logger.info(f"  NIFTY50: {len(ACTIVE_STOCKS)} stocks loaded")
    logger.info(f"  Macro triggers: {len(MACRO_TRIGGERS)} patterns")

    # Test cases
    tests = [
        "RBI cuts repo rate by 25bps, banks expected to pass on benefit",
        "Crude oil spikes 4% on OPEC production cut",
        "FII sold Rs 5000 crore in Indian equities amid US Fed rate hike fears",
        "Reliance Industries Q4 profit beats estimates by 12%",
        "Rupee depreciates to 84.5 against dollar on FII outflows",
        "TCS and Infosys benefit from US dollar strengthening",
    ]

    for headline in tests:
        text = headline.lower()
        mentions  = extract_direct_mentions(headline)
        triggers  = detect_macro_triggers(text)
        direction = lookup_affected_stocks(triggers, mentions)

        logger.info(f"\n  '{headline[:60]}'")
        logger.info(f"    Direct: {mentions}")
        logger.info(f"    Triggers: {triggers}")
        logger.info(f"    Stocks: {len(direction)} affected")
        if direction:
            sample = list(direction.items())[:4]
            logger.info(f"    Sample: {sample}")

    logger.info("\nEntity Mapper module OK.")
