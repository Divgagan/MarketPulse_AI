-- MarketPulse AI: Supabase Table Setup
-- Copy and paste this entirely into the Supabase SQL Editor and click "Run"
-- Safe to run multiple times (all CREATE IF NOT EXISTS)

-- ── Predictions table ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT,
    sector TEXT,
    predicted_direction TEXT,
    final_direction TEXT,          -- alias used by agents
    final_probability_up REAL,     -- probability of upward move (0.0–1.0)
    final_confidence REAL,
    signal_strength TEXT,
    signals_agree BOOLEAN,
    valid_for_sessions INTEGER,
    market_regime TEXT,
    alert_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optional: index for faster date queries on the dashboard
CREATE INDEX IF NOT EXISTS idx_predictions_date   ON predictions(date);
CREATE INDEX IF NOT EXISTS idx_predictions_ticker ON predictions(ticker);

-- ── Articles table (for News Signals dashboard page) ─────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id         TEXT NOT NULL,
    url        TEXT NOT NULL,
    title      TEXT,
    source     TEXT,
    fetched_at TEXT NOT NULL,
    fetch_date TEXT NOT NULL,
    PRIMARY KEY (id, fetch_date)
);

-- Named unique constraint required for Supabase upsert to work correctly
-- (DROP first if you already created the table without it)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_articles_id_fetch_date'
    ) THEN
        ALTER TABLE articles
        ADD CONSTRAINT uq_articles_id_fetch_date UNIQUE (id, fetch_date);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_articles_fetch_date ON articles(fetch_date);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);
