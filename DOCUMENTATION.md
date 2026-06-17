# MarketPulse AI: Comprehensive End-to-End Documentation

This document serves as the complete technical master guide for the MarketPulse AI project. It breaks down every component, how they interact, and the lifecycle of data as it moves through the system.

---

## 1. Executive Summary
MarketPulse AI is an autonomous, cloud-hosted financial intelligence system designed specifically for the Indian Stock Market (NIFTY 50). Instead of relying purely on technical analysis (math) or purely on fundamental analysis (news), the system combines both using a modern "Agentic AI" architecture. 

It reads thousands of news articles daily, extracts sentiment using Large Language Models (Llama-3), crunches mathematical stock indicators using Machine Learning (LightGBM), and synthesizes them into actionable, statistical trading signals. It then stores these signals in a cloud database, displays them on a live website, and emails the user an executive report—all automatically while the user is asleep.

---

## 2. Core Architecture Components

The system is composed of five distinct "pillars":
1. **The Multi-Agent AI System (LangGraph):** The brains that read the news.
2. **The Quantitative ML Pipeline:** The math that analyzes price history.
3. **The Cloud Database (Supabase):** The permanent memory storage.
4. **The User Interface (Streamlit):** The interactive website.
5. **The Automation Engine (GitHub Actions):** The robotic scheduler that triggers the pipeline.

---

## 3. Pillar I: The Multi-Agent System (LangGraph)

Instead of using one massive AI prompt, the system breaks the thinking process into 7 specialized "Agents" passing information to each other. This prevents hallucinations and increases accuracy.

- **Agent 1: The News Harvester:** Wakes up and downloads RSS feeds and NewsAPI data for the past 24 hours.
- **Agent 2: Relevance Filter:** Scans headlines and immediately discards generic noise (like politics or sports) to save AI processing tokens.
- **Agent 3: Entity & Sector Mapper:** Uses a hardcoded "Knowledge Graph" to map news to specific NIFTY 50 companies. (e.g., if news mentions "Automobile taxes", it maps it to Tata Motors and Mahindra).
- **Agent 4: Impact Scorer (Groq/Llama-3):** Reads the filtered articles and assigns a sentiment score (0.0 to 1.0) and direction (Bullish/Bearish).
- **Agent 5: Market Monitor:** Cross-references the news sentiment with live market opening prices.
- **Agent 6: Signal Aggregator:** The "Boss" Agent. It takes the sentiment from Agent 4 and the mathematical prediction from the ML Pipeline (Pillar II) and merges them into one final "Confidence Score".
- **Agent 7: Alert Generator:** Formats the final signals to be compliant with SEBI (Securities and Exchange Board of India) warnings and prepares them for the database.

---

## 4. Pillar II: The Quantitative ML Pipeline

While the LLMs read the news, the ML pipeline processes raw numbers.

- **Data Collection:** Uses `yfinance` to download years of historical NIFTY 50 price data (Open, High, Low, Close, Volume).
- **Feature Engineering (`pandas-ta`):** Calculates 50+ technical indicators like RSI (Relative Strength Index), MACD, Bollinger Bands, and Moving Averages.
- **Regime Detection (`hmmlearn`):** Uses a Hidden Markov Model to mathematically determine if the overall market is in a "Bull", "Bear", or "Sideways" regime.
- **Directional Prediction (`LightGBM`):** 138 custom-trained, highly optimized gradient boosting models evaluate the technical indicators and predict the probability (e.g., 65%) that a stock will go UP tomorrow.

---

## 5. Pillar III: Cloud Database (Supabase)

Because the system runs in the cloud and shuts down immediately after, it needs permanent storage.
- We use **Supabase**, an open-source alternative to Firebase built on PostgreSQL.
- The `eod_pipeline.py` script opens a connection to Supabase and inserts rows into the `predictions` table.
- This decoupling means the AI can write to the database from anywhere, and the website can read from it instantly without them having to run on the same computer.

---

## 6. Pillar IV: The Streamlit Dashboard

The frontend is built using **Streamlit Community Cloud**, a free hosting service for Python data apps.
- The app is completely "stateless". It holds no data itself. 
- When a user opens the URL on their laptop or mobile phone, the app queries Supabase for `today()`'s signals.
- It automatically adapts its layout (Sidebar, KPI metrics, Plotly Charts) to perfectly fit the screen size of the device viewing it.

---

## 7. Pillar V: Cloud Automation & CI/CD (GitHub Actions)

This is what makes the system 100% autonomous.
- **`.github/workflows/agent_pipeline.yml`**: A YAML file instructing GitHub's servers to wake up at exactly 10:15 AM UTC (3:45 PM IST).
- **Secrets Management:** The GitHub Action securely pulls your private API keys (`GROQ_API_KEY`, `SUPABASE_KEY`, `SENDER_EMAIL`) without exposing them to the public code.
- **The Daily Run:** 
  1. Installs Python and all heavy ML libraries (PyTorch, LightGBM).
  2. Runs `python -m pipeline.eod_pipeline`.
  3. Writes to Supabase.
  4. Runs `send_alerts.py` to trigger the Gmail SMTP server.
  5. Shuts down cleanly.

---

## 8. The Daily Lifecycle (Data Flow)

Here is exactly what happens every day at 3:45 PM IST:
1. **Trigger:** GitHub Actions starts the Ubuntu server.
2. **Fetch:** `yfinance` grabs closing prices; `feedparser` grabs news.
3. **Math:** LightGBM predicts probabilities based on indicators.
4. **Language:** Llama-3 reads the news and extracts sentiment.
5. **Merge:** The Aggregator agent combines Math + Language into a Final Signal.
6. **Store:** The signal is pushed to Supabase PostgreSQL.
7. **Display:** Streamlit UI automatically shows the new data.
8. **Alert:** A Python SMTP script emails the top 5 strongest signals to the user.
9. **Sleep:** The server turns off to save resources.

---

*End of Document. MarketPulse AI represents a state-of-the-art implementation of RAG (Retrieval-Augmented Generation), Agentic Workflows, and Quantitative Finance.*
