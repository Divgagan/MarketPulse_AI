"""
agents/news_harvester.py — MarketPulse AI
==========================================
Blueprint Part 11: Agent 1 — News Harvester.

The first LangGraph agent node. Collects news from 6 free RSS feeds +
optional NewsAPI, deduplicates by URL hash, and stores raw articles.

Sources:
  1. Economic Times Markets RSS
  2. Moneycontrol Top News RSS
  3. LiveMint Markets RSS
  4. Business Standard Markets RSS
  5. NDTV Profit RSS
  6. Economic Times Default RSS
  + NewsAPI (if NEWSAPI_KEY is set in .env)

Deduplication:
  - MD5 hash of article URL = article ID
  - SQLite DB (data/predictions/articles.db) tracks all seen IDs
  - Duplicate URLs are silently skipped

LangGraph node:
  news_harvester_node(state) → returns updated state with:
    - state["raw_articles"]
    - state["articles_fetched_count"]

Resilience:
  - Each RSS feed is wrapped in try/except
  - If one feed fails, others continue
  - Failed feeds are logged as warnings in state["warnings"]
"""

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import feedparser

from agents.state import MarketPulseState, NewsArticle
from config.settings import NEWSAPI_KEY, DATA_DIR, SUPABASE_URL, SUPABASE_KEY

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("news_harvester")

# ── Database path (SQLite for deduplication) ──────────────────────────────────
DB_PATH = DATA_DIR / "predictions" / "articles.db"

# ── RSS Feed URLs ─────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "url":    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "source": "economic_times_markets",
    },
    {
        "url":    "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "source": "moneycontrol",
    },
    {
        "url":    "https://www.livemint.com/rss/markets",
        "source": "livemint",
    },
    {
        "url":    "https://www.business-standard.com/rss/markets-106.rss",
        "source": "business_standard",
    },
    {
        "url":    "https://feeds.feedburner.com/ndtvprofit-latest",
        "source": "ndtv_profit",
    },
    {
        "url":    "https://economictimes.indiatimes.com/rssfeedsdefault.cms",
        "source": "economic_times_default",
    },
]

# Max body chars to store (first paragraph is enough for NLP)
MAX_BODY_CHARS = 500


# ── SQLite Deduplication DB ────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create the SQLite articles deduplication table if it doesn't exist.
    Called once at startup — safe to call multiple times.
    Also purges articles older than 7 days so same URLs can be re-fetched daily.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id         TEXT NOT NULL,
                url        TEXT NOT NULL,
                title      TEXT,
                source     TEXT,
                fetched_at TEXT NOT NULL,
                fetch_date TEXT NOT NULL DEFAULT (date('now')),
                PRIMARY KEY (id, fetch_date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fetched ON articles (fetched_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fetch_date ON articles (fetch_date)")
        # Purge records older than 7 days so the same URLs can be re-fetched on new days
        conn.execute("DELETE FROM articles WHERE fetch_date < date('now', '-7 days')")
        conn.commit()
    finally:
        conn.close()


def is_duplicate(article_id: str) -> bool:
    """
    Check if an article ID (MD5 of URL) was already seen TODAY.
    Same article can be fetched again on a different day — so dedup
    is scoped to today's date only, not all-time.

    Args:
        article_id: MD5 hex string of the article URL

    Returns:
        True if already seen today, False if new
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.execute(
            "SELECT 1 FROM articles WHERE id = ? AND fetch_date = ?",
            (article_id, today)
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def mark_fetched(article_id: str, url: str, title: str, source: str) -> None:
    """
    Insert article into deduplication DB after fetching.
    Uses (id, fetch_date) as primary key so same URL is allowed on different days.

    Args:
        article_id : MD5 hash of URL
        url        : Full article URL
        title      : Article headline
        source     : Feed source name
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO articles (id, url, title, source, fetched_at, fetch_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (article_id, url, title, source, now_iso, today),
        )
        conn.commit()
    finally:
        conn.close()


def _make_article_id(url: str) -> str:
    """MD5 hash of URL — used as unique article identifier."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


# ── RSS Fetcher ────────────────────────────────────────────────────────────────

def fetch_rss_articles() -> List[NewsArticle]:
    """
    Fetch and deduplicate articles from all 6 RSS feeds.

    Returns:
        List[NewsArticle] — only new articles not seen before
    """
    init_db()
    articles: List[NewsArticle] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for feed_info in RSS_FEEDS:
        url    = feed_info["url"]
        source = feed_info["source"]

        try:
            logger.info(f"Fetching RSS: {source}")
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                logger.warning(f"  {source}: Feed parse error — {feed.bozo_exception}")
                continue

            new_count = 0
            for entry in feed.entries:
                article_url = entry.get("link", "")
                if not article_url:
                    continue

                article_id = _make_article_id(article_url)
                if is_duplicate(article_id):
                    continue

                # Extract title
                title = entry.get("title", "").strip()

                # Extract body (summary or description, truncated)
                body = (
                    entry.get("summary", "")
                    or entry.get("description", "")
                    or ""
                ).strip()
                body = body[:MAX_BODY_CHARS]

                # Extract published time
                published_at = entry.get("published", "")
                if not published_at:
                    published_at = now_iso

                article: NewsArticle = {
                    "id":           article_id,
                    "url":          article_url,
                    "title":        title,
                    "body":         body,
                    "source":       source,
                    "published_at": published_at,
                    "fetched_at":   now_iso,
                }

                articles.append(article)
                mark_fetched(article_id, article_url, title, source)
                new_count += 1

            logger.info(f"  {source}: {new_count} new articles")

        except Exception as e:
            logger.warning(f"  {source}: Failed to fetch — {e}")

    return articles


# ── NewsAPI Fetcher ────────────────────────────────────────────────────────────

def fetch_newsapi_articles() -> List[NewsArticle]:
    """
    Fetch articles from NewsAPI (optional — only if NEWSAPI_KEY is set).

    Searches for Indian financial news using queries:
      - Top business headlines for India
      - Keyword searches: NSE, NIFTY, Sensex, RBI, SEBI

    Returns:
        List[NewsArticle] — empty list if NEWSAPI_KEY not set
    """
    if not NEWSAPI_KEY:
        logger.info("NEWSAPI_KEY not set — skipping NewsAPI fetch (RSS only)")
        return []

    try:
        from newsapi import NewsApiClient
    except ImportError:
        logger.warning("newsapi-python not installed. Run: pip install newsapi-python")
        return []

    init_db()
    articles: List[NewsArticle] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        client = NewsApiClient(api_key=NEWSAPI_KEY)

        # Batch 1: Top Indian business headlines
        try:
            response = client.get_top_headlines(country="in", category="business", page_size=20)
            batch1 = response.get("articles", [])
        except Exception as e:
            logger.warning(f"NewsAPI top-headlines failed: {e}")
            batch1 = []

        # Batch 2: Search for NIFTY/NSE/RBI keywords
        search_queries = ["NSE NIFTY", "RBI rate", "SEBI India", "Sensex stock"]
        batch2 = []
        for query in search_queries:
            try:
                resp = client.get_everything(
                    q=query,
                    language="en",
                    sort_by="publishedAt",
                    page_size=10,
                )
                batch2.extend(resp.get("articles", []))
                time.sleep(0.5)  # Rate limiting — NewsAPI free tier: 100 req/day
            except Exception as e:
                logger.warning(f"NewsAPI search '{query}' failed: {e}")

        # Combine and deduplicate
        all_raw = batch1 + batch2
        new_count = 0

        for raw in all_raw:
            article_url = raw.get("url", "")
            if not article_url or article_url == "https://removed.com":
                continue

            article_id = _make_article_id(article_url)
            if is_duplicate(article_id):
                continue

            title = (raw.get("title") or "").strip()
            body  = (
                raw.get("content") or raw.get("description") or ""
            ).strip()[:MAX_BODY_CHARS]
            published_at = raw.get("publishedAt") or now_iso

            # Source name from NewsAPI nested dict
            source_name = raw.get("source", {}).get("name", "newsapi")

            article: NewsArticle = {
                "id":           article_id,
                "url":          article_url,
                "title":        title,
                "body":         body,
                "source":       f"newsapi_{source_name.lower().replace(' ', '_')}",
                "published_at": published_at,
                "fetched_at":   now_iso,
            }

            articles.append(article)
            mark_fetched(article_id, article_url, title, source_name)
            new_count += 1

        logger.info(f"NewsAPI: {new_count} new articles")

    except Exception as e:
        logger.error(f"NewsAPI fetch failed: {e}")

    return articles


# ── Supabase Sync ──────────────────────────────────────────────────────────────

def _sync_articles_to_supabase(articles: List[NewsArticle]) -> None:
    """
    Upload today's fetched articles to Supabase so the Streamlit Cloud
    dashboard can display them. Silently skips if credentials are missing.

    Args:
        articles: List of new NewsArticle dicts fetched this run
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.debug("Supabase credentials not set — skipping article cloud sync")
        return

    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        payload = [
            {
                "id":         a["id"],
                "url":        a["url"],
                "title":      a.get("title", ""),
                "source":     a.get("source", ""),
                "fetched_at": a.get("fetched_at", datetime.now(timezone.utc).isoformat()),
                "fetch_date": today,
            }
            for a in articles
        ]

        # Upsert — safe to call multiple times (no duplicates)
        supabase.table("articles").upsert(payload, on_conflict="id,fetch_date").execute()
        logger.info(f"  Cloud sync: {len(payload)} articles saved to Supabase")

    except Exception as e:
        logger.warning(f"  Supabase article sync failed (non-fatal): {e}")


# ── LangGraph Node Function ────────────────────────────────────────────────────

def news_harvester_node(state: MarketPulseState) -> MarketPulseState:
    """
    LangGraph Agent 1 node: News Harvester.

    Fetches from all RSS feeds + NewsAPI, deduplicates, and updates state.

    Args:
        state: MarketPulseState (passed by LangGraph)

    Returns:
        Updated MarketPulseState with:
          - state["raw_articles"]           : List of new NewsArticle dicts
          - state["articles_fetched_count"] : Total count
    """
    logger.info("=" * 55)
    logger.info("Agent 1: News Harvester — starting")
    logger.info("=" * 55)

    warnings = list(state.get("warnings", []))
    errors   = list(state.get("errors", []))
    all_articles: List[NewsArticle] = []

    # ── Fetch from RSS feeds ──────────────────────────────────────────────────
    try:
        rss_articles = fetch_rss_articles()
        all_articles.extend(rss_articles)
    except Exception as e:
        msg = f"Agent1: RSS fetch failed entirely — {e}"
        logger.error(msg)
        errors.append(msg)

    # ── Fetch from NewsAPI ────────────────────────────────────────────────────
    try:
        newsapi_articles = fetch_newsapi_articles()
        all_articles.extend(newsapi_articles)
    except Exception as e:
        msg = f"Agent1: NewsAPI fetch failed — {e}"
        logger.warning(msg)
        warnings.append(msg)

    # ── Final deduplication (in case RSS and NewsAPI returned same URL) ───────
    seen_ids: set = set()
    unique_articles: List[NewsArticle] = []
    for article in all_articles:
        if article["id"] not in seen_ids:
            seen_ids.add(article["id"])
            unique_articles.append(article)

    n_sources = len(RSS_FEEDS) + (1 if NEWSAPI_KEY else 0)
    logger.info(
        f"Agent 1 complete: {len(unique_articles)} new articles "
        f"from {n_sources} sources"
    )

    # ── Sync to Supabase so Streamlit Cloud dashboard can show articles ───────
    if unique_articles:
        _sync_articles_to_supabase(unique_articles)

    return {
        **state,
        "raw_articles":           unique_articles,
        "articles_fetched_count": len(unique_articles),
        "warnings":               warnings,
        "errors":                 errors,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m agents.news_harvester
    # Quick test — fetches from RSS feeds in real-time
    logger.info("MarketPulse AI -- News Harvester Module")
    logger.info("Running quick RSS fetch test (real network call)...")

    from agents.state import create_initial_state
    state = create_initial_state("manual")

    result = news_harvester_node(state)
    logger.info(f"Fetched: {result['articles_fetched_count']} new articles")

    if result["raw_articles"]:
        sample = result["raw_articles"][0]
        logger.info(f"Sample: [{sample['source']}] {sample['title'][:80]}...")
    else:
        logger.info("No new articles (all already seen or feeds unreachable)")

    logger.info("News Harvester module OK.")
