import re
with open('config/sector_knowledge.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'# ── DYNAMIC SECTOR KNOWLEDGE EXPANSION.*', '', content, flags=re.DOTALL)

dynamic_code = '''
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
'''

with open('config/sector_knowledge.py', 'w', encoding='utf-8') as f:
    f.write(content.strip() + "\n" + dynamic_code)

print('Sector knowledge updated dynamically.')
