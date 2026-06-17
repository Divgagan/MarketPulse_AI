"""
config/nifty50_tickers.py — MarketPulse AI
===========================================
Complete NIFTY 50 ticker registry as of 2024.

Contains:
  - ACTIVE_STOCKS      : Full metadata dict for all 50 stocks
  - COMPANY_TO_TICKER   : Reverse mapping (company name variants → ticker)
  - SECTOR_GROUPS       : Stocks grouped by sector (for macro trigger lookups)

All tickers use the yfinance .NS suffix (NSE-listed).
"""

# ── NIFTY 50 Stock Registry ────────────────────────────────────────────────────
# Format: { "TICKER.NS": { "name": ..., "sector": ..., "industry": ... } }

ACTIVE_STOCKS = {

    # ── Information Technology ─────────────────────────────────────────────────
    "TCS.NS": {
        "name": "Tata Consultancy Services",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
    },
    "INFOSYS.NS": {
        "name": "Infosys Limited",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
    },
    "HCLTECH.NS": {
        "name": "HCL Technologies",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
    },
    "WIPRO.NS": {
        "name": "Wipro Limited",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
    },
    "TECHM.NS": {
        "name": "Tech Mahindra",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
    },

    # ── Banking ────────────────────────────────────────────────────────────────
    "HDFCBANK.NS": {
        "name": "HDFC Bank",
        "sector": "Banking",
        "industry": "Private Sector Bank",
    },
    "ICICIBANK.NS": {
        "name": "ICICI Bank",
        "sector": "Banking",
        "industry": "Private Sector Bank",
    },
    "SBIN.NS": {
        "name": "State Bank of India",
        "sector": "Banking",
        "industry": "Public Sector Bank",
    },
    "KOTAKBANK.NS": {
        "name": "Kotak Mahindra Bank",
        "sector": "Banking",
        "industry": "Private Sector Bank",
    },
    "AXISBANK.NS": {
        "name": "Axis Bank",
        "sector": "Banking",
        "industry": "Private Sector Bank",
    },
    "INDUSINDBK.NS": {
        "name": "IndusInd Bank",
        "sector": "Banking",
        "industry": "Private Sector Bank",
    },

    # ── Financial Services / NBFC ──────────────────────────────────────────────
    "BAJFINANCE.NS": {
        "name": "Bajaj Finance",
        "sector": "Financial Services",
        "industry": "Non-Banking Financial Company",
    },
    "BAJAJFINSV.NS": {
        "name": "Bajaj Finserv",
        "sector": "Financial Services",
        "industry": "Diversified Financial Services",
    },
    "HDFCLIFE.NS": {
        "name": "HDFC Life Insurance",
        "sector": "Financial Services",
        "industry": "Life Insurance",
    },
    "SBILIFE.NS": {
        "name": "SBI Life Insurance",
        "sector": "Financial Services",
        "industry": "Life Insurance",
    },
    "SHRIRAMFIN.NS": {
        "name": "Shriram Finance",
        "sector": "Financial Services",
        "industry": "Non-Banking Financial Company",
    },

    # ── Oil, Gas & Energy ──────────────────────────────────────────────────────
    "RELIANCE.NS": {
        "name": "Reliance Industries",
        "sector": "Oil Gas & Consumable Fuels",
        "industry": "Integrated Oil & Gas",
    },
    "ONGC.NS": {
        "name": "Oil and Natural Gas Corporation",
        "sector": "Oil Gas & Consumable Fuels",
        "industry": "Upstream Oil & Gas",
    },
    "BPCL.NS": {
        "name": "Bharat Petroleum Corporation",
        "sector": "Oil Gas & Consumable Fuels",
        "industry": "Oil Marketing & Refining",
    },

    # ── Power & Utilities ──────────────────────────────────────────────────────
    "NTPC.NS": {
        "name": "NTPC Limited",
        "sector": "Power",
        "industry": "Power Generation",
    },
    "POWERGRID.NS": {
        "name": "Power Grid Corporation of India",
        "sector": "Power",
        "industry": "Power Transmission",
    },
    "COALINDIA.NS": {
        "name": "Coal India",
        "sector": "Metals & Mining",
        "industry": "Coal Mining",
    },

    # ── Automobile ─────────────────────────────────────────────────────────────
    "MARUTI.NS": {
        "name": "Maruti Suzuki India",
        "sector": "Automobile",
        "industry": "Passenger Vehicles",
    },
    "TATAMOTORS.NS": {
        "name": "Tata Motors",
        "sector": "Automobile",
        "industry": "Passenger & Commercial Vehicles",
    },
    "M&M.NS": {
        "name": "Mahindra & Mahindra",
        "sector": "Automobile",
        "industry": "Utility Vehicles & Tractors",
    },
    "EICHERMOT.NS": {
        "name": "Eicher Motors",
        "sector": "Automobile",
        "industry": "Two-Wheelers & Commercial Vehicles",
    },
    "HEROMOTOCO.NS": {
        "name": "Hero MotoCorp",
        "sector": "Automobile",
        "industry": "Two-Wheelers",
    },

    # ── Pharmaceuticals ────────────────────────────────────────────────────────
    "SUNPHARMA.NS": {
        "name": "Sun Pharmaceutical Industries",
        "sector": "Pharmaceuticals",
        "industry": "Branded & Generic Pharmaceuticals",
    },
    "DRREDDY.NS": {
        "name": "Dr. Reddy's Laboratories",
        "sector": "Pharmaceuticals",
        "industry": "Generic Pharmaceuticals & APIs",
    },
    "CIPLA.NS": {
        "name": "Cipla",
        "sector": "Pharmaceuticals",
        "industry": "Generic Pharmaceuticals",
    },
    "DIVISLAB.NS": {
        "name": "Divi's Laboratories",
        "sector": "Pharmaceuticals",
        "industry": "API & CRAMS",
    },
    "APOLLOHOSP.NS": {
        "name": "Apollo Hospitals Enterprise",
        "sector": "Healthcare",
        "industry": "Hospitals & Healthcare Services",
    },

    # ── FMCG ───────────────────────────────────────────────────────────────────
    "HINDUNILVR.NS": {
        "name": "Hindustan Unilever",
        "sector": "Fast Moving Consumer Goods",
        "industry": "Household & Personal Products",
    },
    "ITC.NS": {
        "name": "ITC Limited",
        "sector": "Fast Moving Consumer Goods",
        "industry": "Cigarettes, Hotels, FMCG",
    },
    "NESTLEIND.NS": {
        "name": "Nestle India",
        "sector": "Fast Moving Consumer Goods",
        "industry": "Packaged Foods",
    },
    "BRITANNIA.NS": {
        "name": "Britannia Industries",
        "sector": "Fast Moving Consumer Goods",
        "industry": "Packaged Foods & Biscuits",
    },
    "TATACONSUM.NS": {
        "name": "Tata Consumer Products",
        "sector": "Fast Moving Consumer Goods",
        "industry": "Tea, Coffee & Food Products",
    },

    # ── Metals & Mining ────────────────────────────────────────────────────────
    "TATASTEEL.NS": {
        "name": "Tata Steel",
        "sector": "Metals & Mining",
        "industry": "Steel Manufacturing",
    },
    "JSWSTEEL.NS": {
        "name": "JSW Steel",
        "sector": "Metals & Mining",
        "industry": "Steel Manufacturing",
    },
    "HINDALCO.NS": {
        "name": "Hindalco Industries",
        "sector": "Metals & Mining",
        "industry": "Aluminium & Copper",
    },

    # ── Infrastructure & Construction ──────────────────────────────────────────
    "LT.NS": {
        "name": "Larsen & Toubro",
        "sector": "Capital Goods",
        "industry": "Engineering, Construction & EPC",
    },
    "ADANIENT.NS": {
        "name": "Adani Enterprises",
        "sector": "Capital Goods",
        "industry": "Diversified Conglomerate",
    },
    "ADANIPORTS.NS": {
        "name": "Adani Ports and Special Economic Zone",
        "sector": "Infrastructure",
        "industry": "Ports & Logistics",
    },
    "ULTRACEMCO.NS": {
        "name": "UltraTech Cement",
        "sector": "Cement & Construction Materials",
        "industry": "Cement",
    },
    "GRASIM.NS": {
        "name": "Grasim Industries",
        "sector": "Cement & Construction Materials",
        "industry": "Cement, VSF & Chemicals",
    },

    # ── Consumer Discretionary ─────────────────────────────────────────────────
    "TITAN.NS": {
        "name": "Titan Company",
        "sector": "Consumer Discretionary",
        "industry": "Jewellery, Watches & Eyewear",
    },
    "ASIANPAINT.NS": {
        "name": "Asian Paints",
        "sector": "Consumer Discretionary",
        "industry": "Paints & Coatings",
    },

    # ── Telecom ────────────────────────────────────────────────────────────────
    "BHARTIARTL.NS": {
        "name": "Bharti Airtel",
        "sector": "Telecommunication",
        "industry": "Wireless Telecom Services",
    },

    # ── Defence ────────────────────────────────────────────────────────────────
    "HAL.NS": {
        "name": "Hindustan Aeronautics Limited",
        "sector": "Defence",
        "industry": "Aerospace & Defence Manufacturing",
    },
    "BEL.NS": {
        "name": "Bharat Electronics Limited",
        "sector": "Defence",
        "industry": "Defence Electronics",
    },
}

# ── Sanity Check ───────────────────────────────────────────────────────────────
assert len(ACTIVE_STOCKS) == 50, f"Expected 50 stocks, got {len(ACTIVE_STOCKS)}"


# ── Reverse Mapping: Company Name → Ticker ─────────────────────────────────────
# At least 3 name variants per major company so the NER agents can match them.
# Keys are lowercase for case-insensitive matching in agents.

COMPANY_TO_TICKER = {

    # TCS
    "tcs": "TCS.NS",
    "tata consultancy": "TCS.NS",
    "tata consultancy services": "TCS.NS",
    "tata consultancy services limited": "TCS.NS",

    # Infosys
    "infosys": "INFOSYS.NS",
    "infy": "INFOSYS.NS",
    "infosys limited": "INFOSYS.NS",
    "infosys technologies": "INFOSYS.NS",

    # HCL Tech
    "hcltech": "HCLTECH.NS",
    "hcl technologies": "HCLTECH.NS",
    "hcl tech": "HCLTECH.NS",
    "hcl": "HCLTECH.NS",

    # Wipro
    "wipro": "WIPRO.NS",
    "wipro limited": "WIPRO.NS",
    "wipro technologies": "WIPRO.NS",

    # Tech Mahindra
    "tech mahindra": "TECHM.NS",
    "techm": "TECHM.NS",
    "tech mahindra limited": "TECHM.NS",

    # HDFC Bank
    "hdfc bank": "HDFCBANK.NS",
    "hdfcbank": "HDFCBANK.NS",
    "hdfc": "HDFCBANK.NS",
    "hdfc bank limited": "HDFCBANK.NS",

    # ICICI Bank
    "icici bank": "ICICIBANK.NS",
    "icicibank": "ICICIBANK.NS",
    "icici": "ICICIBANK.NS",
    "icici bank limited": "ICICIBANK.NS",

    # SBI
    "sbi": "SBIN.NS",
    "state bank of india": "SBIN.NS",
    "state bank": "SBIN.NS",
    "sbin": "SBIN.NS",

    # Kotak
    "kotak": "KOTAKBANK.NS",
    "kotak mahindra bank": "KOTAKBANK.NS",
    "kotak bank": "KOTAKBANK.NS",
    "kotakbank": "KOTAKBANK.NS",

    # Axis Bank
    "axis bank": "AXISBANK.NS",
    "axisbank": "AXISBANK.NS",
    "axis": "AXISBANK.NS",
    "axis bank limited": "AXISBANK.NS",

    # IndusInd Bank
    "indusind bank": "INDUSINDBK.NS",
    "indusindbk": "INDUSINDBK.NS",
    "indusind": "INDUSINDBK.NS",

    # Bajaj Finance
    "bajaj finance": "BAJFINANCE.NS",
    "bajfinance": "BAJFINANCE.NS",
    "bajaj fin": "BAJFINANCE.NS",
    "bajaj financial services": "BAJFINANCE.NS",

    # Bajaj Finserv
    "bajaj finserv": "BAJAJFINSV.NS",
    "bajajfinsv": "BAJAJFINSV.NS",
    "bajaj financial": "BAJAJFINSV.NS",

    # HDFC Life
    "hdfc life": "HDFCLIFE.NS",
    "hdfclife": "HDFCLIFE.NS",
    "hdfc life insurance": "HDFCLIFE.NS",

    # SBI Life
    "sbi life": "SBILIFE.NS",
    "sbilife": "SBILIFE.NS",
    "sbi life insurance": "SBILIFE.NS",

    # Shriram Finance
    "shriram finance": "SHRIRAMFIN.NS",
    "shriramfin": "SHRIRAMFIN.NS",
    "shriram": "SHRIRAMFIN.NS",

    # Reliance
    "reliance": "RELIANCE.NS",
    "ril": "RELIANCE.NS",
    "reliance industries": "RELIANCE.NS",
    "reliance industries limited": "RELIANCE.NS",
    "mukesh ambani company": "RELIANCE.NS",

    # ONGC
    "ongc": "ONGC.NS",
    "oil and natural gas": "ONGC.NS",
    "oil and natural gas corporation": "ONGC.NS",
    "oil india": "ONGC.NS",

    # BPCL
    "bpcl": "BPCL.NS",
    "bharat petroleum": "BPCL.NS",
    "bharat petroleum corporation": "BPCL.NS",

    # NTPC
    "ntpc": "NTPC.NS",
    "ntpc limited": "NTPC.NS",
    "national thermal power": "NTPC.NS",

    # Power Grid
    "powergrid": "POWERGRID.NS",
    "power grid": "POWERGRID.NS",
    "power grid corporation": "POWERGRID.NS",
    "pgcil": "POWERGRID.NS",

    # Coal India
    "coal india": "COALINDIA.NS",
    "coalindia": "COALINDIA.NS",
    "cil": "COALINDIA.NS",

    # Maruti
    "maruti": "MARUTI.NS",
    "maruti suzuki": "MARUTI.NS",
    "maruti suzuki india": "MARUTI.NS",
    "msil": "MARUTI.NS",

    # Tata Motors
    "tata motors": "TATAMOTORS.NS",
    "tatamotors": "TATAMOTORS.NS",
    "tml": "TATAMOTORS.NS",
    "tata motors limited": "TATAMOTORS.NS",

    # M&M
    "m&m": "M&M.NS",
    "mahindra": "M&M.NS",
    "mahindra and mahindra": "M&M.NS",
    "mahindra & mahindra": "M&M.NS",

    # Eicher Motors
    "eicher motors": "EICHERMOT.NS",
    "eichermot": "EICHERMOT.NS",
    "royal enfield": "EICHERMOT.NS",
    "eicher": "EICHERMOT.NS",

    # Hero MotoCorp
    "hero motocorp": "HEROMOTOCO.NS",
    "heromotoco": "HEROMOTOCO.NS",
    "hero honda": "HEROMOTOCO.NS",
    "hero moto": "HEROMOTOCO.NS",

    # Sun Pharma
    "sun pharma": "SUNPHARMA.NS",
    "sunpharma": "SUNPHARMA.NS",
    "sun pharmaceutical": "SUNPHARMA.NS",
    "sun pharmaceuticals": "SUNPHARMA.NS",

    # Dr. Reddy's
    "dr reddy": "DRREDDY.NS",
    "dr. reddy": "DRREDDY.NS",
    "drreddys": "DRREDDY.NS",
    "dr reddy's laboratories": "DRREDDY.NS",

    # Cipla
    "cipla": "CIPLA.NS",
    "cipla limited": "CIPLA.NS",
    "cipla pharma": "CIPLA.NS",

    # Divi's Lab
    "divi's laboratories": "DIVISLAB.NS",
    "divislab": "DIVISLAB.NS",
    "divis": "DIVISLAB.NS",
    "divi's lab": "DIVISLAB.NS",

    # Apollo Hospitals
    "apollo hospitals": "APOLLOHOSP.NS",
    "apollohosp": "APOLLOHOSP.NS",
    "apollo": "APOLLOHOSP.NS",
    "apollo hospitals enterprise": "APOLLOHOSP.NS",

    # HUL
    "hul": "HINDUNILVR.NS",
    "hindustan unilever": "HINDUNILVR.NS",
    "hindunilvr": "HINDUNILVR.NS",
    "unilever india": "HINDUNILVR.NS",

    # ITC
    "itc": "ITC.NS",
    "itc limited": "ITC.NS",
    "imperial tobacco": "ITC.NS",

    # Nestle India
    "nestle": "NESTLEIND.NS",
    "nestle india": "NESTLEIND.NS",
    "nestleind": "NESTLEIND.NS",
    "maggi company": "NESTLEIND.NS",

    # Britannia
    "britannia": "BRITANNIA.NS",
    "britannia industries": "BRITANNIA.NS",
    "britannia biscuits": "BRITANNIA.NS",

    # Tata Consumer
    "tata consumer": "TATACONSUM.NS",
    "tataconsum": "TATACONSUM.NS",
    "tata consumer products": "TATACONSUM.NS",
    "tata tea": "TATACONSUM.NS",

    # Tata Steel
    "tata steel": "TATASTEEL.NS",
    "tatasteel": "TATASTEEL.NS",
    "tsl": "TATASTEEL.NS",
    "tata steel limited": "TATASTEEL.NS",

    # JSW Steel
    "jsw steel": "JSWSTEEL.NS",
    "jswsteel": "JSWSTEEL.NS",
    "jsw": "JSWSTEEL.NS",
    "jindal south west": "JSWSTEEL.NS",

    # Hindalco
    "hindalco": "HINDALCO.NS",
    "hindalco industries": "HINDALCO.NS",
    "novelis": "HINDALCO.NS",

    # L&T
    "larsen and toubro": "LT.NS",
    "larsen & toubro": "LT.NS",
    "l&t": "LT.NS",
    "lt": "LT.NS",

    # Adani Enterprises
    "adani enterprises": "ADANIENT.NS",
    "adanient": "ADANIENT.NS",
    "adani": "ADANIENT.NS",

    # Adani Ports
    "adani ports": "ADANIPORTS.NS",
    "adaniports": "ADANIPORTS.NS",
    "apsez": "ADANIPORTS.NS",
    "adani port": "ADANIPORTS.NS",

    # UltraTech Cement
    "ultratech cement": "ULTRACEMCO.NS",
    "ultracemco": "ULTRACEMCO.NS",
    "ultratech": "ULTRACEMCO.NS",

    # Grasim
    "grasim": "GRASIM.NS",
    "grasim industries": "GRASIM.NS",
    "aditya birla grasim": "GRASIM.NS",

    # Titan
    "titan": "TITAN.NS",
    "titan company": "TITAN.NS",
    "tanishq": "TITAN.NS",
    "titan watches": "TITAN.NS",

    # Asian Paints
    "asian paints": "ASIANPAINT.NS",
    "asianpaint": "ASIANPAINT.NS",
    "asian paint": "ASIANPAINT.NS",

    # Bharti Airtel
    "airtel": "BHARTIARTL.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "bhartiartl": "BHARTIARTL.NS",
    "bharti": "BHARTIARTL.NS",

    # HAL
    "hal": "HAL.NS",
    "hindustan aeronautics": "HAL.NS",
    "hindustan aeronautics limited": "HAL.NS",

    # BEL
    "bel": "BEL.NS",
    "bharat electronics": "BEL.NS",
    "bharat electronics limited": "BEL.NS",
}


# ── Sector Groups ─────────────────────────────────────────────────────────────
# Used by macro trigger lookups — e.g., "rupee_depreciation" → bullish for IT_STOCKS

IT_STOCKS = [
    "TCS.NS", "INFOSYS.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
]

BANKING_STOCKS = [
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "INDUSINDBK.NS",
]

NBFC_STOCKS = [
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "SHRIRAMFIN.NS",
]

INSURANCE_STOCKS = [
    "HDFCLIFE.NS", "SBILIFE.NS",
]

OIL_GAS_STOCKS = [
    "RELIANCE.NS", "ONGC.NS", "BPCL.NS",
]

POWER_STOCKS = [
    "NTPC.NS", "POWERGRID.NS",
]

AUTO_STOCKS = [
    "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
]

PHARMA_STOCKS = [
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
]

HEALTHCARE_STOCKS = [
    "APOLLOHOSP.NS",
]

FMCG_STOCKS = [
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
]

METAL_STOCKS = [
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "COALINDIA.NS",
]

INFRA_STOCKS = [
    "LT.NS", "ADANIENT.NS", "ADANIPORTS.NS", "NTPC.NS", "POWERGRID.NS",
]

CEMENT_STOCKS = [
    "ULTRACEMCO.NS", "GRASIM.NS",
]

CONSUMER_DISCRETIONARY_STOCKS = [
    "TITAN.NS", "ASIANPAINT.NS",
]

TELECOM_STOCKS = [
    "BHARTIARTL.NS",
]

DEFENSE_STOCKS = [
    "HAL.NS", "BEL.NS",
]

# Convenience: all sector groups in one dict (used by agents for lookups)
SECTOR_GROUPS = {
    "IT": IT_STOCKS,
    "Banking": BANKING_STOCKS,
    "NBFC": NBFC_STOCKS,
    "Insurance": INSURANCE_STOCKS,
    "Oil & Gas": OIL_GAS_STOCKS,
    "Power": POWER_STOCKS,
    "Automobile": AUTO_STOCKS,
    "Pharmaceuticals": PHARMA_STOCKS,
    "Healthcare": HEALTHCARE_STOCKS,
    "FMCG": FMCG_STOCKS,
    "Metals": METAL_STOCKS,
    "Infrastructure": INFRA_STOCKS,
    "Cement": CEMENT_STOCKS,
    "Consumer Discretionary": CONSUMER_DISCRETIONARY_STOCKS,
    "Telecom": TELECOM_STOCKS,
    "Defence": DEFENSE_STOCKS,
}


if __name__ == "__main__":
    # Quick sanity check — run: python config/nifty50_tickers.py
    print("=" * 50)
    print(f"Total NIFTY50 stocks loaded : {len(ACTIVE_STOCKS)}")
    print(f"Total company name aliases  : {len(COMPANY_TO_TICKER)}")
    print(f"Total sector groups         : {len(SECTOR_GROUPS)}")
    print()
    print("Stocks by sector:")
    for sector, tickers in SECTOR_GROUPS.items():
        print(f"  {sector:30s} : {len(tickers)} stocks — {', '.join(tickers)}")
    print("=" * 50)


# ── Expanded 100 Stocks ────────────────────────────────────────────────────────
NEW_100_STOCKS = {
    "PNB.NS": {"name": "PUNJAB NATIONAL BANK", "sector": "Financial Services", "industry": "Banks - Regional"},
    "BSE.NS": {"name": "BSE LIMITED", "sector": "Financial Services", "industry": "Financial Data & Stock Exchanges"},
    "GODREJPROP.NS": {"name": "GODREJ PROPERTIES LTD", "sector": "Real Estate", "industry": "Real Estate - Development"},
    "SUZLON.NS": {"name": "SUZLON ENERGY LIMITED", "sector": "Industrials", "industry": "Specialty Industrial Machinery"},
    "GMRINFRA.NS": {"name": "GMRINFRA", "sector": "Unknown", "industry": "Unknown"},
    "MCX.NS": {"name": "MULTI COMMODITY EXCHANGE", "sector": "Financial Services", "industry": "Financial Data & Stock Exchanges"},
    "BATAINDIA.NS": {"name": "BATA INDIA LTD", "sector": "Consumer Cyclical", "industry": "Footwear & Accessories"},
    "JUBLFOOD.NS": {"name": "JUBILANT FOODWORKS LTD", "sector": "Consumer Cyclical", "industry": "Restaurants"},
    "MUTHOOTFIN.NS": {"name": "MUTHOOT FINANCE LIMITED", "sector": "Financial Services", "industry": "Credit Services"},
    "SIEMENS.NS": {"name": "SIEMENS LTD", "sector": "Industrials", "industry": "Specialty Industrial Machinery"},
    "BHEL.NS": {"name": "BHEL", "sector": "Industrials", "industry": "Specialty Industrial Machinery"},
    "NYKAA.NS": {"name": "FSN E COMMERCE VENTURES", "sector": "Consumer Cyclical", "industry": "Internet Retail"},
    "ZOMATO.NS": {"name": "ZOMATO", "sector": "Unknown", "industry": "Unknown"},
    "CUMMINSIND.NS": {"name": "CUMMINS INDIA LTD", "sector": "Industrials", "industry": "Specialty Industrial Machinery"},
    "TATAINVEST.NS": {"name": "TATA INVESTMENT CORP LTD", "sector": "Financial Services", "industry": "Asset Management"},
    "BAJAJHOLD.NS": {"name": "BAJAJHOLD", "sector": "Unknown", "industry": "Unknown"},
    "DELHIVERY.NS": {"name": "DELHIVERY LIMITED", "sector": "Industrials", "industry": "Integrated Freight & Logistics"},
    "RECLTD.NS": {"name": "REC LIMITED", "sector": "Financial Services", "industry": "Credit Services"},
    "MACROTECH.NS": {"name": "MACROTECH", "sector": "Unknown", "industry": "Unknown"},
    "ADANIGREEN.NS": {"name": "ADANI GREEN ENERGY LTD", "sector": "Utilities", "industry": "Utilities - Renewable"},
    "TATACHEM.NS": {"name": "TATA CHEMICALS LTD", "sector": "Basic Materials", "industry": "Chemicals"},
    "CDSL.NS": {"name": "CENTRAL DEPO SER (I) LTD", "sector": "Financial Services", "industry": "Capital Markets"},
    "SONACOMS.NS": {"name": "SONA BLW PRECISION FRGS L", "sector": "Consumer Cyclical", "industry": "Auto Parts"},
    "ESCORTS.NS": {"name": "ESCORTS KUBOTA LIMITED", "sector": "Industrials", "industry": "Farm & Heavy Construction Machinery"},
    "KALYANKJIL.NS": {"name": "KALYAN JEWELLERS IND LTD", "sector": "Consumer Cyclical", "industry": "Luxury Goods"},
    "BANKBARODA.NS": {"name": "BANK OF BARODA", "sector": "Financial Services", "industry": "Banks - Regional"},
    "AMBUJACEM.NS": {"name": "AMBUJA CEMENTS LTD", "sector": "Basic Materials", "industry": "Building Materials"},
    "IOC.NS": {"name": "INDIAN OIL CORP LTD", "sector": "Energy", "industry": "Oil & Gas Refining & Marketing"},
    "LICHSGFIN.NS": {"name": "LIC HOUSING FINANCE LTD", "sector": "Financial Services", "industry": "Mortgage Finance"},
    "ZEEL.NS": {"name": "ZEE ENTERTAINMENT ENT LTD", "sector": "Communication Services", "industry": "Broadcasting"},
    "POONAWALLA.NS": {"name": "POONAWALLA FINCORP LTD", "sector": "Financial Services", "industry": "Credit Services"},
    "ABFRL.NS": {"name": "ADITYA BIRLA FASHION & RT", "sector": "Consumer Cyclical", "industry": "Apparel Manufacturing"},
    "ABB.NS": {"name": "ABB INDIA LIMITED", "sector": "Industrials", "industry": "Specialty Industrial Machinery"},
    "ICICIPRULI.NS": {"name": "ICICI PRU LIFE INS CO LTD", "sector": "Financial Services", "industry": "Insurance - Life"},
    "AUBANK.NS": {"name": "AU SMALL FINANCE BANK LTD", "sector": "Financial Services", "industry": "Banks - Regional"},
    "L&TFH.NS": {"name": "L&TFH", "sector": "Unknown", "industry": "Unknown"},
    "IRCTC.NS": {"name": "INDIAN RAIL TOUR CORP LTD", "sector": "Consumer Cyclical", "industry": "Travel Services"},
    "M&MFIN.NS": {"name": "M&M FIN. SERVICES LTD", "sector": "Financial Services", "industry": "Credit Services"},
    "ASHOKLEY.NS": {"name": "ASHOK LEYLAND LTD", "sector": "Industrials", "industry": "Farm & Heavy Construction Machinery"},
    "COFORGE.NS": {"name": "COFORGE LIMITED", "sector": "Technology", "industry": "Information Technology Services"},
    "BOSCHLTD.NS": {"name": "BOSCH LIMITED", "sector": "Consumer Cyclical", "industry": "Auto Parts"},
    "TATAELXSI.NS": {"name": "TATA ELXSI LIMITED", "sector": "Technology", "industry": "Software - Application"},
    "UBL.NS": {"name": "UNITED BREWERIES LTD", "sector": "Consumer Defensive", "industry": "Beverages - Brewers"},
    "POLICYBZR.NS": {"name": "PB FINTECH LIMITED", "sector": "Financial Services", "industry": "Insurance Brokers"},
    "AWL.NS": {"name": "AWL AGRI BUSINESS LIMITED", "sector": "Consumer Defensive", "industry": "Packaged Foods"},
    "PHOENIXLTD.NS": {"name": "THE PHOENIX MILLS LTD", "sector": "Real Estate", "industry": "Real Estate - Diversified"},
    "PETRONET.NS": {"name": "PETRONET LNG LIMITED", "sector": "Energy", "industry": "Oil & Gas Refining & Marketing"},
    "INDIGO.NS": {"name": "INTERGLOBE AVIATION LTD", "sector": "Industrials", "industry": "Airlines"},
    "PFC.NS": {"name": "POWER FIN CORP LTD.", "sector": "Financial Services", "industry": "Credit Services"},
    "TRENT.NS": {"name": "TRENT LTD", "sector": "Consumer Cyclical", "industry": "Apparel Retail"},
    "IEX.NS": {"name": "INDIAN ENERGY EXC LTD", "sector": "Financial Services", "industry": "Capital Markets"},
    "ADANIENSOL.NS": {"name": "ADANI ENERGY SOLUTION LTD", "sector": "Utilities", "industry": "Utilities - Independent Power Producers"},
    "IDFCFIRSTB.NS": {"name": "IDFC FIRST BANK LIMITED", "sector": "Financial Services", "industry": "Banks - Regional"},
    "DEEPAKNTR.NS": {"name": "DEEPAK NITRITE LTD", "sector": "Basic Materials", "industry": "Chemicals"},
    "DLF.NS": {"name": "DLF LIMITED", "sector": "Real Estate", "industry": "Real Estate - Development"},
    "JIOFIN.NS": {"name": "JIO FIN SERVICES LTD", "sector": "Financial Services", "industry": "Asset Management"},
    "NAUKRI.NS": {"name": "INFO EDGE (I) LTD", "sector": "Communication Services", "industry": "Internet Content & Information"},
    "AMBER.NS": {"name": "AMBER ENTERPRISES (I) LTD", "sector": "Consumer Cyclical", "industry": "Furnishings, Fixtures & Appliances"},
    "AARTIIND.NS": {"name": "AARTI INDUSTRIES LTD", "sector": "Basic Materials", "industry": "Specialty Chemicals"},
    "PIDILITIND.NS": {"name": "PIDILITE INDUSTRIES LTD", "sector": "Basic Materials", "industry": "Specialty Chemicals"},
    "JINDALSTEL.NS": {"name": "JINDAL STEEL LIMITED", "sector": "Basic Materials", "industry": "Steel"},
    "OBEROIRLTY.NS": {"name": "OBEROI REALTY LIMITED", "sector": "Real Estate", "industry": "Real Estate - Development"},
    "MPHASIS.NS": {"name": "MPHASIS LIMITED", "sector": "Technology", "industry": "Information Technology Services"},
    "COLPAL.NS": {"name": "COLGATE PALMOLIVE LTD.", "sector": "Consumer Defensive", "industry": "Household & Personal Products"},
    "DIXON.NS": {"name": "DIXON TECHNO (INDIA) LTD", "sector": "Technology", "industry": "Consumer Electronics"},
    "ANGELONE.NS": {"name": "ANGEL ONE LIMITED", "sector": "Financial Services", "industry": "Capital Markets"},
    "VOLTAS.NS": {"name": "VOLTAS LTD", "sector": "Consumer Cyclical", "industry": "Furnishings, Fixtures & Appliances"},
    "GAIL.NS": {"name": "GAIL (INDIA) LTD", "sector": "Utilities", "industry": "Utilities - Regulated Gas"},
    "CHOLAFIN.NS": {"name": "CHOLAMANDALAM IN & FIN CO", "sector": "Financial Services", "industry": "Credit Services"},
    "PRESTIGE.NS": {"name": "PRESTIGE ESTATE LTD", "sector": "Real Estate", "industry": "Real Estate - Diversified"},
    "ICICIGI.NS": {"name": "ICICI LOMBARD GIC LIMITED", "sector": "Financial Services", "industry": "Insurance - Diversified"},
    "PNBHOUSING.NS": {"name": "PNB HOUSING FIN LTD.", "sector": "Financial Services", "industry": "Mortgage Finance"},
    "PAYTM.NS": {"name": "ONE 97 COMMUNICATIONS LTD", "sector": "Technology", "industry": "Software - Infrastructure"},
    "SUNTV.NS": {"name": "SUN TV NETWORK LIMITED", "sector": "Communication Services", "industry": "Broadcasting"},
    "HAVELLS.NS": {"name": "HAVELLS INDIA LIMITED", "sector": "Industrials", "industry": "Electrical Equipment & Parts"},
    "PAGEIND.NS": {"name": "PAGE INDUSTRIES LTD", "sector": "Consumer Cyclical", "industry": "Apparel Manufacturing"},
    "VEDL.NS": {"name": "VEDANTA LIMITED", "sector": "Basic Materials", "industry": "Other Industrial Metals & Mining"},
    "CANBK.NS": {"name": "CANARA BANK", "sector": "Financial Services", "industry": "Banks - Regional"},
    "MRF.NS": {"name": "MRF LTD", "sector": "Consumer Cyclical", "industry": "Auto Parts"},
    "ATGL.NS": {"name": "ADANI TOTAL GAS LIMITED", "sector": "Utilities", "industry": "Utilities - Regulated Gas"},
    "BANDHANBNK.NS": {"name": "BANDHAN BANK LIMITED", "sector": "Financial Services", "industry": "Banks - Regional"},
    "IRFC.NS": {"name": "INDIAN RAILWAY FIN CORP L", "sector": "Financial Services", "industry": "Credit Services"},
    "GODREJCP.NS": {"name": "GODREJ CONSUMER PRODUCTS", "sector": "Consumer Defensive", "industry": "Household & Personal Products"},
    "PERSISTENT.NS": {"name": "PERSISTENT SYSTEMS LTD", "sector": "Technology", "industry": "Information Technology Services"},
    "FEDERALBNK.NS": {"name": "FEDERAL BANK LTD", "sector": "Financial Services", "industry": "Banks - Regional"},
    "NMDC.NS": {"name": "NMDC LTD.", "sector": "Basic Materials", "industry": "Steel"},
    "LICI.NS": {"name": "LIFE INSURA CORP OF INDIA", "sector": "Financial Services", "industry": "Insurance - Life"},
    "TORNTPHARM.NS": {"name": "TORRENT PHARMACEUTICALS L", "sector": "Healthcare", "industry": "Drug Manufacturers - Specialty & Generic"},
    "TVSMOTOR.NS": {"name": "TVS MOTOR COMPANY  LTD", "sector": "Consumer Cyclical", "industry": "Auto Manufacturers"},
    "SRF.NS": {"name": "SRF LTD", "sector": "Industrials", "industry": "Conglomerates"},
    "MARICO.NS": {"name": "MARICO LIMITED", "sector": "Consumer Defensive", "industry": "Household & Personal Products"},
    "TATACOMM.NS": {"name": "TATA COMMUNICATIONS LTD", "sector": "Communication Services", "industry": "Telecom Services"},
    "IDEA.NS": {"name": "VODAFONE IDEA LIMITED", "sector": "Communication Services", "industry": "Telecom Services"},
    "POLYCAB.NS": {"name": "POLYCAB INDIA LIMITED", "sector": "Industrials", "industry": "Electrical Equipment & Parts"},
    "CGPOWER.NS": {"name": "CG POWER AND IND SOL LTD", "sector": "Industrials", "industry": "Electrical Equipment & Parts"},
    "SBIcard.NS": {"name": "SBI CARDS & PAY SER LTD", "sector": "Financial Services", "industry": "Credit Services"},
}


ACTIVE_STOCKS = {**ACTIVE_STOCKS, **NEW_100_STOCKS}
ACTIVE_TICKERS_LIST = list(ACTIVE_STOCKS.keys())
