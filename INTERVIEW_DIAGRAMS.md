# MarketPulse AI — Interview Diagrams

Both diagrams are grounded entirely in the codebase.
Paste either block directly into any Mermaid renderer (mermaid.live, VS Code, Notion, etc.).

---

## Deliverable 1 — Architecture & Flow Diagram

```mermaid
flowchart TD

    %% ── TRIGGER ───────────────────────────────────────────────
    CRON["⏰ GitHub Actions Cron\n3:45 PM IST · Mon–Fri\n(cron: '15 10 * * 1-5')"]

    %% ── ML PIPELINE ───────────────────────────────────────────
    subgraph ML["ML Pipeline  (runs first, before agents)"]
        direction TB
        DC["1 · Fetch OHLCV prices\nyfinance → SQLite"]
        FE["2 · Engineer features\n~40 indicators via pandas-ta\nRSI · MACD · ATR · OBV…"]
        DC --> FE

        subgraph MODELS["Per-stock models  (×50 NIFTY stocks)"]
            direction LR
            LGBM["LightGBM classifier\nTimeSeriesSplit CV\nSHAP feature attribution"]
            HMM["HMM Regime Detector\nbull / bear / sideways\n(GaussianHMM on ^NSEI)"]
            CHR["Chronos-T5-Small\nZero-shot price trajectory\nforecast (Amazon)"]
        end

        FE --> MODELS

        BLEND["6 · Blend ML signals\n60% LightGBM\n30% Chronos\n10% HMM regime"]
        LGBM --> BLEND
        HMM  --> BLEND
        CHR  --> BLEND
    end

    %% ── NEWS PIPELINE ─────────────────────────────────────────
    subgraph NEWS["News Pipeline  (7 LangGraph agents via StateGraph)"]
        direction TB

        A1["Agent 1 · News Harvester\n6 RSS feeds + NewsAPI\nMD5 dedup via SQLite"]

        subgraph FILTER["Agent 2 · Relevance Filter  (4-stage gate)"]
            direction LR
            S1["Stage 1\nKeyword blocklist\nRejects cricket · Bollywood"]
            S2["Stage 2\nspaCy NER\nMust mention market entity"]
            S3["Stage 3\nFinBERT sentiment\nMust score ≥ 0.5"]
            S4["Stage 4\nLlama 3.1 8B on Groq\nFew-shot JSON gate"]
            S1 --> S2 --> S3 --> S4
        end

        A3["Agent 3 · Entity Mapper\nspaCy NER + macro trigger regex\n→ NIFTY 50 ticker + direction\n(LLM fallback if no match)"]

        A4["Agent 4 · Impact Scorer\nGroq Llama 3.3 70B\nSeverity: minor/moderate/major\nChromaDB RAG for precedent"]

        A5["Agent 5 · Market Monitor\nyfinance live prices\nValidates yesterday's calls\nDetects F&O expiry day"]

        A1 --> FILTER
        FILTER -- "0 articles → skip A3/A4" --> A5
        FILTER -- "articles passed" --> A3 --> A4 --> A5
    end

    %% ── MERGE ─────────────────────────────────────────────────
    A6["Agent 6 · Signal Aggregator\nMerge: 60% ML + 40% News\nMajor news can override ML\nConflict → reduce confidence 30%\nGroq 70B writes reasoning"]

    A7["Agent 7 · Alert Generator\nFormats SEBI-compliant text\nBullish ⬆ / Bearish ⬇ / Weak ⟷\nLogs to SQLite + Supabase"]

    %% ── STORAGE & DISPLAY ─────────────────────────────────────
    SB[("Supabase PostgreSQL\npredictions table\narticles table")]

    DASH["Streamlit Dashboard\nStreamlit Community Cloud\nStateless — reads Supabase\non every page load"]

    EMAIL["Email Alert\nSMTP via send_alerts.py\nSent after each EOD run"]

    %% ── CONNECTIONS ───────────────────────────────────────────
    CRON --> ML
    CRON --> NEWS

    BLEND --> A6
    A5    --> A6

    A6 --> A7
    A7 --> SB
    A7 --> EMAIL
    SB --> DASH
```

---

## Deliverable 2 — Database Design

### What is actually in the codebase

**Honest assessment of the schema situation:**

There are **two storage layers** and they have a **schema mismatch**:

| Layer | Tables | Defined in |
|---|---|---|
| **Supabase** (production) | `predictions`, `articles` | `supabase_setup.sql` — formal DDL exists |
| **SQLite** (local dev) | `predictions` only | Created ad-hoc in `signal_aggregator.py` and `market_monitor.py` via `CREATE TABLE IF NOT EXISTS` |

The **SQLite `predictions` table has more columns than Supabase** — specifically `actual_direction`, `actual_change_pct`, and `was_correct` (written by `validate_previous_predictions()` in `market_monitor.py`). These columns do **not exist in `supabase_setup.sql`**, so accuracy tracking is SQLite-only and never reaches the cloud dashboard.

The diagram below shows the actual Supabase schema (from `supabase_setup.sql`) **plus** the extra columns that only live in SQLite, clearly labelled.

```mermaid
erDiagram

    PREDICTIONS {
        int     id                  PK  "SERIAL — Supabase only"
        text    date                    "YYYY-MM-DD"
        text    ticker                  "e.g. RELIANCE.NS"
        text    company_name            "e.g. Reliance Industries"
        text    sector                  "e.g. Energy"
        text    predicted_direction     "bullish or bearish"
        real    final_confidence        "0.0 – 1.0"
        text    signal_strength         "strong / moderate / weak"
        text    alert_text              "SEBI-compliant formatted text"
        timestamp created_at            "UTC timestamp"
        text    actual_direction        "SQLite only — bullish or bearish"
        real    actual_change_pct       "SQLite only — next-day % move"
        int     was_correct             "SQLite only — 1 or 0"
    }

    ARTICLES {
        text    id          PK  "MD5 hash of URL"
        text    fetch_date  PK  "YYYY-MM-DD (composite PK)"
        text    url
        text    title
        text    source          "economic_times / moneycontrol / etc."
        text    fetched_at      "ISO datetime string"
    }
```

### Key design notes (grounded in code)

- **`predictions` has no FK to `articles`** — the pipeline stores signals and articles independently; there is no join between them in any query.
- **Composite PK on `articles(id, fetch_date)`** — same URL is allowed on different days (dedup is scoped to today only, per `init_db()` in `news_harvester.py`).
- **`actual_direction`, `actual_change_pct`, `was_correct` are Supabase-absent** — `market_monitor.py` writes these to SQLite via `UPDATE predictions SET actual_direction=? ...` and tries to sync to Supabase, but the Supabase table DDL in `supabase_setup.sql` doesn't have these columns. They would need to be `ALTER TABLE predictions ADD COLUMN` to exist in the cloud.
- **`company_name` and `sector` are in `supabase_setup.sql` but absent from the SQLite DDL** in `signal_aggregator.py` — they're only populated in the `save_predictions_to_db.py` Supabase payload.
- **No ChromaDB schema shown** — ChromaDB (used by Agent 4 for RAG) is a local vector store at `data/chroma_db/`. It has one collection: `news_impact_history`, with document = headline, metadata = `{ticker, predicted_direction, actual_outcome, confidence, date}`. It is never synced to Supabase.

---

*Diagrams generated 2026-07-16 from: `agents/graph.py`, `agents/state.py`, all 7 agent files, `ml/signal_combiner.py`, `ml/regime_detector.py`, `ml/chronos_forecaster.py`, `pipeline/eod_pipeline.py`, `.github/workflows/agent_pipeline.yml`, `supabase_setup.sql`, `save_predictions_to_db.py`.*
