"""
config/sector_knowledge.py — MarketPulse AI
=============================================
THE MOST CRITICAL FILE IN THE PROJECT.

This file contains all structured financial knowledge that the LangGraph agents
use for reasoning. Instead of asking the LLM to reason from scratch every time,
agents consult this file — making predictions reliable, consistent, and fast.

Contains:
  - MACRO_TRIGGERS          : Economic events → affected stocks (bullish/bearish)
  - TRADE_DEPENDENCY_MAP    : Trade exposure mapping per stock
  - NSE_CALENDAR_EVENTS     : Important market dates and their effects
  - KEYWORD_BLOCKLIST       : News keywords that indicate irrelevant articles
  - MARKET_RELEVANT_ENTITIES: Keywords/entities that make an article market-relevant
"""

# ── 1. MACRO TRIGGERS ─────────────────────────────────────────────────────────
# Maps an economic/macro event name to:
#   - description: human-readable explanation
#   - bullish: list of NIFTY 50 tickers that typically rise on this event
#   - bearish: list of NIFTY 50 tickers that typically fall on this event
#   - reasoning: WHY these stocks are affected (for LLM context)
#
# These are used by Agent 3 (entity_mapper) to auto-detect sector impacts
# without calling the LLM for every article.

MACRO_TRIGGERS = {

    "crude_oil_price_increase": {
        "description": "Crude oil price rises significantly (Brent/WTI spike)",
        "bullish": [
            "ONGC.NS",      # Upstream oil producer — higher revenue per barrel
            "RELIANCE.NS",  # Upstream E&P segment benefits; refining margins complex
            "COALINDIA.NS", # Energy substitute demand increases
        ],
        "bearish": [
            "BPCL.NS",      # OMC — crude is primary input cost, margins squeezed
            "HINDUNILVR.NS",# Palm oil, packaging (crude derivatives) costs rise
            "ASIANPAINT.NS",# Crude-based raw materials (VAM, TiO2) cost rise
            "TATAMOTORS.NS",# Higher fuel costs reduce vehicle demand
            "MARUTI.NS",    # Petrol price sensitivity reduces small car demand
            "HEROMOTOCO.NS",# Two-wheeler demand drops when fuel costs spike
            "INDUSINDBK.NS",# Indirect — inflation pressure on RBI rate decision
        ],
        "reasoning": (
            "Crude oil is India's largest import. Rising prices create inflation, "
            "weaken the rupee, squeeze OMC margins (BPCL), and raise costs for "
            "petrochemical-dependent companies (Asian Paints, HUL). Upstream "
            "producers (ONGC) benefit directly."
        ),
    },

    "crude_oil_price_decrease": {
        "description": "Crude oil price falls significantly",
        "bullish": [
            "BPCL.NS",      # OMC margins improve dramatically
            "HINDUNILVR.NS",# Raw material costs fall
            "ASIANPAINT.NS",# VAM and raw material cost relief
            "MARUTI.NS",    # Lower fuel prices boost vehicle demand sentiment
            "TATAMOTORS.NS",# Consumer confidence improves
            "HEROMOTOCO.NS",# Two-wheeler demand improves
            "INDUSINDBK.NS",# Inflation pressure eases, rate cut expectations
        ],
        "bearish": [
            "ONGC.NS",      # Revenue per barrel falls
            "RELIANCE.NS",  # E&P segment revenue pressure
        ],
        "reasoning": (
            "Lower crude reduces India's import bill, strengthens rupee, "
            "controls inflation, and improves margins for OMCs and "
            "crude-derivative users."
        ),
    },

    "rupee_depreciation": {
        "description": "Indian Rupee weakens against USD (USD/INR rises)",
        "bullish": [
            "TCS.NS",       # 80%+ revenue in USD — rupee fall = more INR revenue
            "INFOSYS.NS",   # Large USD revenue base
            "HCLTECH.NS",   # USD revenue dominant
            "WIPRO.NS",     # USD earnings boost
            "TECHM.NS",     # USD earnings boost
            "SUNPHARMA.NS", # Pharma exports heavily USD-denominated
            "DRREDDY.NS",   # US market is primary export destination
            "CIPLA.NS",     # Export revenue benefits
            "DIVISLAB.NS",  # API exports to global markets
        ],
        "bearish": [
            "BPCL.NS",      # Imports crude in USD — costs rise
            "ONGC.NS",      # USD-denominated crude import costs
            "TATAMOTORS.NS",# Imports components; JLR revenue partially offset
            "INDUSINDBK.NS",# Foreign currency borrowings become more expensive
        ],
        "reasoning": (
            "Rupee depreciation is a direct earnings boost for IT and pharma "
            "exporters — their USD revenue converts to more rupees. It hurts "
            "importers who pay in USD for crude, components, and raw materials."
        ),
    },

    "rupee_appreciation": {
        "description": "Indian Rupee strengthens against USD (USD/INR falls)",
        "bullish": [
            "BPCL.NS",      # Crude import costs fall in rupee terms
            "TATAMOTORS.NS",# Import component costs fall
            "INDUSINDBK.NS",# Foreign currency liabilities ease
        ],
        "bearish": [
            "TCS.NS",       # USD revenue converts to fewer rupees
            "INFOSYS.NS",   # USD earnings shrink in INR terms
            "HCLTECH.NS",   # Revenue headwind
            "WIPRO.NS",     # Revenue headwind
            "TECHM.NS",     # Revenue headwind
            "SUNPHARMA.NS", # Export revenue headwind
            "DRREDDY.NS",   # Export revenue headwind
            "CIPLA.NS",     # Export revenue headwind
            "DIVISLAB.NS",  # Export revenue headwind
        ],
        "reasoning": (
            "Rupee appreciation is the mirror image — IT and pharma exporters "
            "face an earnings headwind while importers benefit."
        ),
    },

    "rbi_rate_hike": {
        "description": "RBI increases repo rate (hawkish monetary policy)",
        "bullish": [],  # Few direct beneficiaries in NIFTY 50 from rate hikes
        "bearish": [
            "HDFCBANK.NS",  # NIM pressure; mortgage EMIs rise, loan growth slows
            "ICICIBANK.NS", # Same NIM and credit growth concerns
            "SBIN.NS",      # Rate hike squeezes loan book profitability
            "KOTAKBANK.NS", # Cost of funds rises
            "AXISBANK.NS",  # Loan repricing lag creates margin pressure
            "INDUSINDBK.NS",# High retail loan exposure sensitive to rates
            "BAJFINANCE.NS",# NBFC borrowing costs spike immediately
            "BAJAJFINSV.NS",# Holding company of Bajaj Finance — same impact
            "SHRIRAMFIN.NS",# Higher borrowing costs squeeze NIM
            "HDFCLIFE.NS",  # Bond prices fall, investment portfolio mark-to-market loss
            "SBILIFE.NS",   # Same bond portfolio impact
            "TATAMOTORS.NS",# Auto loans become costlier, demand dampens
            "MARUTI.NS",    # Car loan EMIs rise, dampening volume growth
            "LT.NS",        # Infrastructure project financing costs rise
        ],
        "reasoning": (
            "Rate hikes increase the cost of borrowing for banks, NBFCs, and "
            "consumers. Banks face NIM compression and slower loan growth. "
            "Rate-sensitive sectors like auto (loan-driven sales) and "
            "infrastructure suffer."
        ),
    },

    "rbi_rate_cut": {
        "description": "RBI reduces repo rate (dovish monetary policy)",
        "bullish": [
            "HDFCBANK.NS",  # Credit growth accelerates, NIM stabilizes
            "ICICIBANK.NS", # Loan demand revival
            "SBIN.NS",      # Government push on credit growth
            "KOTAKBANK.NS", # Lower cost of funds
            "AXISBANK.NS",  # Loan growth pickup
            "INDUSINDBK.NS",# Consumer loan demand revival
            "BAJFINANCE.NS",# NBFC borrowing costs fall — margins improve
            "BAJAJFINSV.NS",# Positive for entire financial services vertical
            "SHRIRAMFIN.NS",# Cost of funds drop improves profitability
            "TATAMOTORS.NS",# Lower auto loan EMIs boost vehicle demand
            "MARUTI.NS",    # Car affordability improves
            "HEROMOTOCO.NS",# Two-wheeler loan rates drop
            "LT.NS",        # Infrastructure financing becomes cheaper
            "NTPC.NS",      # Power project funding costs fall
            "ULTRACEMCO.NS",# Construction activity picks up
        ],
        "bearish": [],
        "reasoning": (
            "Rate cuts are broadly bullish — cheaper credit stimulates loan "
            "growth, improves NBFC margins, boosts auto demand, and enables "
            "more infrastructure investment."
        ),
    },

    "us_fed_rate_hike": {
        "description": "US Federal Reserve increases interest rates",
        "bullish": [],
        "bearish": [
            "TCS.NS",       # US client IT budgets get squeezed as cost of capital rises
            "INFOSYS.NS",   # Same — US tech spending slows
            "HCLTECH.NS",   # US clients delay discretionary IT projects
            "WIPRO.NS",     # Deal flow from US companies slows
            "TECHM.NS",     # US telecom/tech clients cut budgets
            "HDFCBANK.NS",  # FII outflows from EM bonds cause rupee pressure
            "ICICIBANK.NS", # FII outflows; rupee depreciation risk
            "ADANIPORTS.NS",# Global trade slowdown risk
            "TATASTEEL.NS", # Global steel demand weakens on recession fear
        ],
        "reasoning": (
            "US rate hikes trigger FII outflows from emerging markets including "
            "India (hot money returns to US treasuries). This weakens the rupee "
            "and hurts IT stocks as US companies cut tech budgets."
        ),
    },

    "india_china_tension": {
        "description": "India-China border tensions or geopolitical conflict",
        "bullish": [
            "HAL.NS",       # Defence orders accelerate on border threat
            "BEL.NS",       # Electronics/radar orders from Ministry of Defence
            "LT.NS",        # Defence manufacturing and border infrastructure
        ],
        "bearish": [
            "ADANIPORTS.NS",# Trade route disruption risk, China trade volumes
            "TATAMOTORS.NS",# EV supply chain (China-dependent components)
            "MARUTI.NS",    # Component sourcing from China may be disrupted
        ],
        "reasoning": (
            "Border tensions trigger increased defence spending, boosting HAL "
            "and BEL. Stocks dependent on China trade routes or Chinese-sourced "
            "components face supply chain risk."
        ),
    },

    "global_recession_fear": {
        "description": "Global recession fears, slowdown in major economies",
        "bullish": [
            "COALINDIA.NS", # Domestic demand, insulated from global trade
            "ITC.NS",       # Defensive FMCG, domestic consumption focus
            "HINDUNILVR.NS",# Defensive consumer staples
        ],
        "bearish": [
            "TCS.NS",       # Global IT spending contracts in recessions
            "INFOSYS.NS",   # Client budget cuts — BFSI sector slowdown
            "HCLTECH.NS",   # Global IT discretionary spend falls
            "WIPRO.NS",     # US and EU clients freeze projects
            "TECHM.NS",     # Telecom clients cut tech spend
            "TATASTEEL.NS", # Global steel demand collapses
            "JSWSTEEL.NS",  # Export-linked revenue falls
            "HINDALCO.NS",  # Aluminium demand falls globally
            "ADANIPORTS.NS",# Global trade volumes shrink
            "RELIANCE.NS",  # Petrochemical demand falls with global slowdown
        ],
        "reasoning": (
            "Global recessions reduce demand for Indian exports — IT services, "
            "metals, and chemicals. Defensive sectors (FMCG, domestic utilities) "
            "outperform as they are insulated from global demand."
        ),
    },

    "india_gdp_strong": {
        "description": "India GDP growth beats expectations or strong economic data",
        "bullish": [
            "HDFCBANK.NS",  # Credit growth accelerates with economic expansion
            "ICICIBANK.NS", # Same
            "SBIN.NS",      # Public sector credit to MSMEs and infra
            "AXISBANK.NS",  # Retail and corporate loan demand grows
            "BAJFINANCE.NS",# Consumer lending booms
            "MARUTI.NS",    # Vehicle demand grows with income
            "TATAMOTORS.NS",# Commercial and passenger vehicles
            "M&M.NS",       # Agri & UV segment
            "EICHERMOT.NS", # Premium bike demand grows
            "HEROMOTOCO.NS",# Mass market two-wheeler demand
            "HINDUNILVR.NS",# FMCG volumes grow with consumer income
            "ITC.NS",       # Cigarettes + Hotels + FMCG all benefit
            "BRITANNIA.NS", # Packaged food consumption rises
            "NESTLEIND.NS", # Premium food demand grows
            "TATACONSUM.NS",# Tea, coffee, salt consumption grows
            "LT.NS",        # Infra capex picks up with GDP growth
            "NTPC.NS",      # Power demand grows
            "ULTRACEMCO.NS",# Construction boom
        ],
        "bearish": [],
        "reasoning": (
            "Strong GDP growth is broadly positive — banks see more credit demand, "
            "auto sector benefits from rising income, FMCG volumes grow, and "
            "infrastructure investment accelerates."
        ),
    },

    "fii_selloff": {
        "description": "Foreign Institutional Investors selling Indian equities (outflows)",
        "bullish": [],
        "bearish": [
            "HDFCBANK.NS",  # Highest FII ownership — most vulnerable to outflows
            "ICICIBANK.NS", # High FII holding
            "INFOSYS.NS",   # High FII ownership, liquid large cap
            "TCS.NS",       # FIIs prefer large, liquid IT names
            "RELIANCE.NS",  # Largest market cap — FII selling is significant
            "BHARTIARTL.NS",# High FII ownership
            "KOTAKBANK.NS", # Premium banking stock — FIIs exit first
            "BAJFINANCE.NS",# High PE stock — FIIs exit high-multiple names
            "ADANIENT.NS",  # High volatility — FIIs reduce exposure
        ],
        "reasoning": (
            "FII outflows create selling pressure across large-cap NIFTY stocks. "
            "Stocks with highest FII ownership face the most selling. This also "
            "weakens the rupee which can create a negative feedback loop."
        ),
    },

    "fii_buying": {
        "description": "Foreign Institutional Investors buying Indian equities (inflows)",
        "bullish": [
            "HDFCBANK.NS",  # First choice for FII re-entry into Indian banks
            "ICICIBANK.NS", # Premium private bank — FII favourite
            "INFOSYS.NS",   # Quality IT pick for global investors
            "TCS.NS",       # Benchmark IT stock
            "RELIANCE.NS",  # Index heavyweight — FII buying moves NIFTY
            "BHARTIARTL.NS",# Telecom — stable cash flows
            "KOTAKBANK.NS", # Premium valuation FII likes
            "BAJFINANCE.NS",# High-growth NBFC — FII growth pick
        ],
        "bearish": [],
        "reasoning": (
            "FII inflows strengthen the rupee and drive large-cap index stocks "
            "higher. These are the first stocks bought when FIIs re-enter India."
        ),
    },

    "gold_price_rise": {
        "description": "Gold prices rise significantly globally",
        "bullish": [
            "TITAN.NS",     # Tanishq jewellery — gold price rise drives revenue
        ],
        "bearish": [
            "TITAN.NS",     # CONFLICTING: higher gold = higher input cost for jewellers
        ],
        "reasoning": (
            "Gold price rise is complex for TITAN. Higher gold price increases "
            "jewellery revenue (gold is priced in gold), but can reduce volume "
            "as consumers delay purchases. Net effect is often mildly positive "
            "as ASP (average selling price) rises."
        ),
    },

    "coal_price_rise": {
        "description": "International coal prices spike",
        "bullish": [
            "COALINDIA.NS", # Domestic coal producer — substitute demand rises
        ],
        "bearish": [
            "NTPC.NS",      # Primary fuel is coal — input cost spikes
            "POWERGRID.NS", # Indirect — power generation costs affect grid
            "TATASTEEL.NS", # Coking coal is key input for steel making
            "JSWSTEEL.NS",  # Same — imported coking coal cost rises
            "ULTRACEMCO.NS",# Coal is key fuel in cement kilns
            "GRASIM.NS",    # Cement and chemicals divisions use coal
        ],
        "reasoning": (
            "Rising coal prices hurt power generators (NTPC) and industries "
            "that use coal as fuel or raw material (steel, cement). "
            "Coal India benefits as a domestic alternative becomes more attractive."
        ),
    },

    "us_sanctions_on_country": {
        "description": "US imposes sanctions on a major country (Russia, China, Middle East)",
        "bullish": [
            "ONGC.NS",      # If Russia sanctioned — India may get discounted crude
        ],
        "bearish": [
            "ADANIPORTS.NS",# Trade route disruptions affect port volumes
            "BPCL.NS",      # Supply chain disruptions for crude sourcing
            "RELIANCE.NS",  # Petrochemical supply chains affected
        ],
        "reasoning": (
            "Sanctions impact depends on which country. Russia sanctions "
            "historically gave India discounted crude. China sanctions disrupt "
            "electronics supply chains. Middle East sanctions affect oil supply."
        ),
    },

    "budget_announcement_capex": {
        "description": "Union Budget announces major capital expenditure on infrastructure",
        "bullish": [
            "LT.NS",        # Largest EPC contractor — direct beneficiary
            "NTPC.NS",      # Power generation capex
            "POWERGRID.NS", # Transmission infrastructure spend
            "HAL.NS",       # Defence capex increases
            "BEL.NS",       # Defence electronics orders
            "ADANIENT.NS",  # Diversified infra plays
            "ADANIPORTS.NS",# Port & logistics infrastructure
            "ULTRACEMCO.NS",# Infrastructure construction = cement demand
            "GRASIM.NS",    # Cement and construction materials
            "TATASTEEL.NS", # Steel demand for infra projects
            "JSWSTEEL.NS",  # Same
            "HINDALCO.NS",  # Aluminium for construction and power transmission
        ],
        "bearish": [],
        "reasoning": (
            "Budget capex announcements trigger a re-rating of infrastructure, "
            "defence, and construction stocks. L&T is the biggest direct "
            "beneficiary as India's largest EPC contractor."
        ),
    },

    "semiconductor_shortage": {
        "description": "Global semiconductor/chip shortage affecting production",
        "bullish": [],
        "bearish": [
            "MARUTI.NS",    # Modern cars have 100+ chips — production cuts
            "TATAMOTORS.NS",# EV and ICE both semiconductor-dependent
            "M&M.NS",       # SUVs and electric vehicles chip-dependent
            "EICHERMOT.NS", # Modern bikes have ECUs and chips
            "HEROMOTOCO.NS",# Less affected but still impacted
        ],
        "reasoning": (
            "Modern vehicles have significant semiconductor content — from "
            "engine control units to infotainment systems. Chip shortages "
            "directly cause production halts and delivery backlogs."
        ),
    },

    "ev_adoption_acceleration": {
        "description": "Electric vehicle adoption accelerates in India",
        "bullish": [
            "TATAMOTORS.NS",# Tata EV is India's market leader (Nexon EV, Tiago EV)
            "M&M.NS",       # Aggressively entering EV space (XEV 9e, BE 6e)
            "NTPC.NS",      # EV charging infrastructure — power demand rises
            "POWERGRID.NS", # Grid demand increases with EV penetration
            "BAJFINANCE.NS",# EV loans — new financing category
        ],
        "bearish": [
            "HEROMOTOCO.NS",# ICE two-wheeler dominant — EV disruption threat
            "EICHERMOT.NS", # Premium ICE motorcycles face long-term EV risk
            "BPCL.NS",      # Fuel demand reduction long-term
            "HINDUNILVR.NS",# Indirect — petrol station convenience stores
        ],
        "reasoning": (
            "EV adoption accelerates a shift from ICE to electric powertrains. "
            "Tata Motors is best positioned in NIFTY 50. Traditional ICE-only "
            "players face structural demand risk over 5-10 year horizon."
        ),
    },
}


# ── 2. TRADE DEPENDENCY MAP ────────────────────────────────────────────────────
# Maps exposure categories to affected NIFTY 50 stocks.
# Used by Agent 3 to identify stocks affected by trade/currency news.

TRADE_DEPENDENCY_MAP = {

    "export_revenue_usd": {
        "description": "Stocks earning significant revenue in USD — benefit from rupee fall",
        "tickers": [
            "TCS.NS",       # ~80% revenue from US and Europe
            "INFOSYS.NS",   # ~60% revenue from North America
            "HCLTECH.NS",   # ~60% revenue from Americas
            "WIPRO.NS",     # ~55% revenue from Americas
            "TECHM.NS",     # ~45% revenue from Americas
            "SUNPHARMA.NS", # US generics market is largest segment
            "DRREDDY.NS",   # US is primary market (>40% revenue)
            "CIPLA.NS",     # US generics and South Africa exports
            "DIVISLAB.NS",  # API exports to US, Europe, Japan
        ],
    },

    "import_dependent_crude": {
        "description": "Stocks where crude oil or its derivatives are a major input cost",
        "tickers": [
            "BPCL.NS",      # Refines imported crude — largest cost item
            "HINDUNILVR.NS",# Palm oil, petrochemical derivatives
            "ASIANPAINT.NS",# VAM (vinyl acetate monomer), TiO2 from crude chain
        ],
    },

    "china_import_dependent": {
        "description": "Stocks with significant dependence on Chinese imports for components",
        "tickers": [
            "TATAMOTORS.NS",# EV battery cells, some electronic components
            "M&M.NS",       # EV components, some auto parts
            "MARUTI.NS",    # Electronic components, certain auto parts
        ],
    },

    "middle_east_exposure": {
        "description": "Stocks with significant exposure to Middle East trade or operations",
        "tickers": [
            "ADANIPORTS.NS",# Mundra port handles Middle East trade routes
            "BPCL.NS",      # Middle East crude sourcing
            "ONGC.NS",      # Middle East oil price benchmark (Brent) driver
            "RELIANCE.NS",  # Petrochemical trade with Middle East
        ],
    },

    "domestic_consumption_only": {
        "description": "Stocks almost entirely driven by domestic Indian demand — insulated from global shocks",
        "tickers": [
            "COALINDIA.NS", # Sells only in India
            "NTPC.NS",      # Domestic power generation
            "POWERGRID.NS", # Domestic power transmission
            "TITAN.NS",     # Domestic jewellery and watches market
            "BRITANNIA.NS", # Domestic FMCG
            "NESTLEIND.NS", # Primarily domestic food products
        ],
    },
}


# ── 3. NSE CALENDAR EVENTS ─────────────────────────────────────────────────────
# Important recurring market events and how they affect trading.
# Used by Feature Engineering (ml/feature_engineering.py) and agents.

NSE_CALENDAR_EVENTS = {

    "fo_expiry": {
        "description": (
            "Last Thursday of every month — F&O (Futures & Options) expiry. "
            "Causes significant intraday volatility and short-covering rallies. "
            "Affects all NIFTY 50 stocks. Typically sees reversal patterns "
            "intraday — stock can move sharply in either direction and then reverse. "
            "Signals generated near F&O expiry have lower reliability."
        ),
        "frequency": "Monthly — last Thursday",
        "signal_reliability_impact": "LOWER — high volatility distorts technical signals",
        "typical_pattern": "Short covering + position rollovers cause exaggerated moves",
    },

    "rbi_mpc": {
        "description": (
            "RBI Monetary Policy Committee meeting — held 6 times per year. "
            "Strongly affects banking stocks (HDFCBANK, ICICIBANK, SBIN, AXISBANK, "
            "KOTAKBANK, INDUSINDBK) and NBFCs (BAJFINANCE, BAJAJFINSV) 2-3 days "
            "before and on announcement day. Rate decisions are binary events — "
            "hike, hold, or cut. Bond yields move inversely, affecting HDFCLIFE "
            "and SBILIFE (insurance companies with large bond portfolios)."
        ),
        "frequency": "6-8 times per year (Feb, Apr, Jun, Aug, Oct, Dec)",
        "scheduled_dates_2024_2025": [
            "2024-02-08", "2024-04-05", "2024-06-07",
            "2024-08-08", "2024-10-09", "2024-12-06",
            "2025-02-07", "2025-04-09", "2025-06-06",
        ],
        "most_affected_sectors": ["Banking", "NBFC", "Insurance", "Real Estate"],
        "signal_reliability_impact": "HIGH IMPACT — position carefully 3 days before",
    },

    "union_budget": {
        "description": (
            "Union Budget — presented by Finance Minister on first Tuesday of February. "
            "The single biggest market-moving event of the year. "
            "Creates heightened uncertainty 1 week before as speculation peaks. "
            "On budget day, can move individual stocks 5-15%. "
            "Capex announcements bullish for infra (LT, NTPC, POWERGRID). "
            "Tax changes affect FMCG (ITC cigarette tax) and auto sector (GST slabs). "
            "Defence allocation affects HAL and BEL."
        ),
        "frequency": "Annual — first Tuesday of February",
        "signal_reliability_impact": (
            "VERY HIGH IMPACT — ML signals unreliable in budget week "
            "due to binary outcome uncertainty"
        ),
        "pre_budget_pattern": "Increased volatility, low signal confidence 7 days before",
    },

    "q_results_season": {
        "description": (
            "Quarterly earnings results season — occurs 4 times per year. "
            "April (Q4 results), July (Q1 results), October (Q2 results), "
            "January (Q3 results). Individual stock volatility spikes ±5-10% "
            "on result day based on earnings vs expectations. "
            "Nifty 50 results are staggered over 3-4 weeks. "
            "Strong results season lifts the entire sector (e.g., good TCS results "
            "lifts INFOSYS, WIPRO, HCLTECH sentiment)."
        ),
        "frequency": "Quarterly — April, July, October, January",
        "signal_reliability_impact": (
            "STOCK-SPECIFIC HIGH IMPACT — signals for specific stocks unreliable "
            "2-3 days around their result date"
        ),
        "result_months": [1, 4, 7, 10],  # January, April, July, October
    },

    "nifty_rebalancing": {
        "description": (
            "NIFTY 50 index rebalancing — semi-annual review by NSE Indices. "
            "NSE announces changes 4-6 weeks in advance. "
            "Stocks being ADDED to NIFTY 50 see buying pressure as index funds "
            "must purchase them (passive inflows). "
            "Stocks being REMOVED see selling pressure as index funds exit. "
            "Effect is front-run by arbitrageurs as soon as announcement is made."
        ),
        "frequency": "Semi-annual — typically March and September effective dates",
        "signal_reliability_impact": (
            "STOCK-SPECIFIC — only affects the specific stocks being added/removed"
        ),
    },
}


# ── 4. KEYWORD BLOCKLIST ───────────────────────────────────────────────────────
# If ANY word/phrase from this list appears in a news article headline or body,
# the article is IMMEDIATELY discarded in Stage 1 of the Relevance Filter.
# This saves LLM API calls by filtering obviously irrelevant content.
#
# Note: All entries are lowercase — comparison should be case-insensitive.

KEYWORD_BLOCKLIST = [
    # Sports
    "cricket", "ipl", "icc", "test match", "one day international", "odi",
    "t20", "world cup cricket", "bcci", "player of the match",
    "football", "fifa", "premier league", "isl", "kabaddi", "pro kabaddi",
    "sports score", "match result", "scorecard", "wicket", "century",
    "hat trick", "grand slam", "tennis", "badminton", "hockey",
    "olympics", "asian games", "commonwealth games",

    # Entertainment
    "bollywood", "tollywood", "kollywood", "mollywood",
    "film", "movie", "cinema", "box office", "ott release",
    "actor", "actress", "celebrity", "star", "superstar",
    "director", "producer", "item song", "trailer launch",
    "web series", "netflix show", "amazon prime show",
    "music album", "single release", "music video",
    "fashion week", "fashion show", "ramp walk",

    # Personal Life / Lifestyle
    "wedding", "divorce", "breakup", "relationship",
    "baby shower", "pregnancy", "birth announcement",
    "birthday party", "anniversary celebration",
    "recipe", "cooking", "food blog", "restaurant review",
    "travel blog", "vacation", "holiday destination", "tourist spot",
    "hotel review",

    # Astrology / Religion (unless involves a listed company)
    "astrology", "horoscope", "rashifal", "zodiac",
    "vastu", "feng shui", "numerology",
    "temple", "church", "mosque", "religious festival",
    "diwali offer",  # Unless it's a company sales report

    # Weather (generic — only extreme events matter for markets)
    # Note: flood, cyclone, drought are NOT blocked as they affect agriculture/FMCG
    "weather forecast", "rain forecast", "humidity",
    "temperature record", "heat wave advisory",

    # Purely political (no market impact)
    "election rally", "political speech", "party manifesto",
    "vote bank", "caste politics", "reservation politics",

    # Fitness / Health (personal, not pharma/hospital business)
    "fitness tip", "diet plan", "weight loss", "yoga pose",
    "gym workout",

    # Other irrelevant
    "viral video", "meme", "social media trend", "twitter trend",
    "instagram", "youtube views",
]


# ── 5. MARKET RELEVANT ENTITIES ───────────────────────────────────────────────
# For Stage 2 of the Relevance Filter — an article must mention at least one
# entity from this list (or a macro keyword) to pass NER check.
#
# The spaCy NER + keyword matching checks against this list.

MARKET_RELEVANT_ENTITIES = [

    # ── Regulators & Institutions ─────────────────────────────────────────────
    "RBI", "Reserve Bank of India",
    "SEBI", "Securities and Exchange Board of India",
    "Finance Ministry", "Ministry of Finance", "Finance Minister",
    "NSE", "National Stock Exchange",
    "BSE", "Bombay Stock Exchange",
    "IRDAI", "Insurance Regulatory",
    "PFRDA",
    "Federal Reserve", "Fed", "Jerome Powell",
    "European Central Bank", "ECB",
    "IMF", "World Bank",

    # ── Market Indices ────────────────────────────────────────────────────────
    "NIFTY", "NIFTY 50", "Nifty50",
    "Sensex", "BSE Sensex",
    "Bank Nifty", "Nifty Bank",
    "Nifty IT", "Nifty Pharma",

    # ── Macro / Economic Indicators ───────────────────────────────────────────
    "repo rate", "reverse repo", "CRR", "SLR",
    "inflation", "CPI", "WPI", "core inflation",
    "GDP", "gross domestic product",
    "IIP", "index of industrial production",
    "trade deficit", "trade surplus", "current account",
    "exports", "imports", "forex reserves",
    "fiscal deficit", "fiscal consolidation",

    # ── Currency / FX ─────────────────────────────────────────────────────────
    "rupee", "INR", "USDINR", "USD/INR",
    "dollar", "USD", "euro", "yen",
    "currency depreciation", "currency appreciation",
    "forex",

    # ── Commodities ───────────────────────────────────────────────────────────
    "crude oil", "Brent crude", "WTI crude", "crude price",
    "natural gas", "LNG",
    "coal", "coking coal", "thermal coal",
    "gold price", "silver price",
    "aluminium", "copper", "steel price",

    # ── Flows ─────────────────────────────────────────────────────────────────
    "FII", "Foreign Institutional Investor",
    "DII", "Domestic Institutional Investor",
    "FPI", "Foreign Portfolio Investor",
    "foreign institutional", "domestic institutional",
    "mutual fund", "AMFI",

    # ── Corporate Events ──────────────────────────────────────────────────────
    "quarterly results", "Q1 results", "Q2 results", "Q3 results", "Q4 results",
    "earnings", "revenue", "profit", "PAT", "EBITDA", "margins",
    "dividend", "bonus shares", "stock split", "buyback",
    "merger", "acquisition", "takeover", "demerger",
    "IPO", "FPO", "QIP", "rights issue",

    # ── NIFTY 50 Company Names (key variants) ─────────────────────────────────
    # IT
    "Tata Consultancy", "TCS", "Infosys", "HCL Technologies", "Wipro", "Tech Mahindra",
    # Banking
    "HDFC Bank", "ICICI Bank", "State Bank", "SBI", "Kotak", "Axis Bank", "IndusInd",
    # Financial
    "Bajaj Finance", "Bajaj Finserv", "HDFC Life", "SBI Life", "Shriram Finance",
    # Oil & Energy
    "Reliance Industries", "RIL", "ONGC", "Bharat Petroleum", "BPCL",
    # Power
    "NTPC", "Power Grid", "Coal India",
    # Auto
    "Maruti Suzuki", "Tata Motors", "Mahindra", "Eicher Motors", "Hero MotoCorp",
    # Pharma
    "Sun Pharma", "Dr Reddy", "Cipla", "Divi's", "Apollo Hospitals",
    # FMCG
    "Hindustan Unilever", "HUL", "ITC", "Nestle", "Britannia", "Tata Consumer",
    # Metals
    "Tata Steel", "JSW Steel", "Hindalco",
    # Infra/Cement
    "Larsen & Toubro", "L&T", "Adani Enterprises", "Adani Ports", "UltraTech", "Grasim",
    # Others
    "Titan", "Asian Paints", "Bharti Airtel", "Airtel", "HAL", "BEL",
    "Hindustan Aeronautics", "Bharat Electronics",
]


if __name__ == "__main__":
    # Sanity check -- run: python config/sector_knowledge.py
    print("-" * 55)
    print("MarketPulse AI -- Sector Knowledge Base Check")
    print("-" * 55)
    print(f"  MACRO_TRIGGERS loaded         : {len(MACRO_TRIGGERS)} triggers")
    print(f"  TRADE_DEPENDENCY_MAP loaded   : {len(TRADE_DEPENDENCY_MAP)} categories")
    print(f"  NSE_CALENDAR_EVENTS loaded    : {len(NSE_CALENDAR_EVENTS)} events")
    print(f"  KEYWORD_BLOCKLIST loaded      : {len(KEYWORD_BLOCKLIST)} keywords")
    print(f"  MARKET_RELEVANT_ENTITIES      : {len(MARKET_RELEVANT_ENTITIES)} entities")
    print()
    print("  Macro Triggers:")
    for trigger, data in MACRO_TRIGGERS.items():
        bullish_count = len(data.get("bullish", []))
        bearish_count = len(data.get("bearish", []))
        print(f"    {trigger:40s} | bullish: {bullish_count:2d} | bearish: {bearish_count:2d}")
    print("-" * 55)

# ── DYNAMIC SECTOR KNOWLEDGE EXPANSION ────────────────────────────────────────
# Automatically insert newly added active stocks into the macro triggers
# based on their sector mapping.

from config.tickers import ACTIVE_STOCKS

for ticker, data in ACTIVE_STOCKS.items():
    sec = data.get("sector", "")
    ind = data.get("industry", "")
    
    # Avoid duplicating existing tickers
    def add_to_trigger(trigger_name, direction):
        if trigger_name in MACRO_TRIGGERS and ticker not in MACRO_TRIGGERS[trigger_name][direction]:
            MACRO_TRIGGERS[trigger_name][direction].append(ticker)

    if sec == "Information Technology":
        add_to_trigger("rupee_depreciation", "bullish")
        add_to_trigger("us_fed_rate_cut", "bullish")
    
    if sec == "Pharmaceuticals" or sec == "Healthcare":
        add_to_trigger("rupee_depreciation", "bullish")
        
    if sec == "Banking" or sec == "Financial Services":
        add_to_trigger("rbi_rate_cut", "bullish")
        add_to_trigger("rbi_rate_hike", "bearish")
        
    if sec == "Automobile":
        add_to_trigger("crude_oil_price_decrease", "bullish")
        add_to_trigger("crude_oil_price_increase", "bearish")
        add_to_trigger("rbi_rate_cut", "bullish")
        
    if sec == "Oil Gas & Consumable Fuels":
        if "Refining" in ind or "Marketing" in ind:
            add_to_trigger("crude_oil_price_decrease", "bullish")
            add_to_trigger("crude_oil_price_increase", "bearish")
        else:
            add_to_trigger("crude_oil_price_increase", "bullish")
            add_to_trigger("crude_oil_price_decrease", "bearish")
