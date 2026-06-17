-- MarketPulse AI: Supabase Table Setup
-- Copy and paste this entirely into the Supabase SQL Editor and click "Run"

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT,
    sector TEXT,
    predicted_direction TEXT,
    final_confidence REAL,
    signal_strength TEXT,
    alert_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optional: Create an index to make querying by date faster for the dashboard
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(date);
