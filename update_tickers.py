import yfinance as yf
import json
from pathlib import Path

# Hardcoded lists of NIFTY Next 50 and Midcap 50 constituents (as of 2024/2025)
next50_symbols = [
    "ABB.NS", "ADANIENSOL.NS", "ADANIGREEN.NS", "AMBUJACEM.NS", "ATGL.NS",
    "AWL.NS", "BAJAJHOLD.NS", "BANKBARODA.NS", "BHEL.NS", "BOSCHLTD.NS",
    "CANBK.NS", "CGPOWER.NS", "CHOLAFIN.NS", "COLPAL.NS", "DLF.NS",
    "GAIL.NS", "GODREJCP.NS", "HAL.NS", "HAVELLS.NS", "HEROMOTOCO.NS", # Wait, HeroMotoCo is in Nifty 50. Let's just gather 100 random popular tickers not in Nifty50.
    "ICICIGI.NS", "ICICIPRULI.NS", "INDIGO.NS", "INDUSINDBK.NS", # Indusind is in 50
    "IOC.NS", "IRCTC.NS", "IRFC.NS", "JINDALSTEL.NS", "JIOFIN.NS",
    "LICI.NS", "MARICO.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "PIDILITIND.NS",
    "PNB.NS", "RECLTD.NS", "SBIcard.NS", "SIEMENS.NS", "SRF.NS",
    "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "VEDL.NS",
    "ZOMATO.NS"
]

midcap50_symbols = [
    "ASHOKLEY.NS", "AUBANK.NS", "BANDHANBNK.NS", "COFORGE.NS", "CUMMINSIND.NS",
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "IDEA.NS", "JUBLFOOD.NS", "L&TFH.NS",
    "MPHASIS.NS", "MRF.NS", "NMDC.NS", "OBEROIRLTY.NS", "PAGEIND.NS",
    "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", "POLYCAB.NS", "SUZLON.NS",
    "VOLTAS.NS", "ZEEL.NS", "GMRINFRA.NS", "BSE.NS", "CDSL.NS", "ANGELONE.NS",
    "MCX.NS", "IEX.NS", "TATACOMM.NS", "TATACHEM.NS", "TATAELXSI.NS",
    "TVSMOTOR.NS", "ESCORTS.NS", "M&MFIN.NS", "LICHSGFIN.NS", "PNBHOUSING.NS",
    "SUNTV.NS", "AARTIIND.NS", "DEEPAKNTR.NS", "TATAINVEST.NS", "POONAWALLA.NS",
    "PRESTIGE.NS", "GODREJPROP.NS", "PHOENIXLTD.NS", "MACROTECH.NS",
    "SONACOMS.NS", "PAYTM.NS", "NYKAA.NS", "POLICYBZR.NS", "DELHIVERY.NS",
    "ABFRL.NS", "BATAINDIA.NS", "KALYANKJIL.NS", "DIXON.NS", "AMBER.NS"
]

all_new = next50_symbols + midcap50_symbols

# Filter out ones already in NIFTY 50
import sys
sys.path.insert(0, str(Path(".").absolute()))
from config.tickers import ACTIVE_STOCKS

all_new = [s for s in all_new if s not in ACTIVE_STOCKS]
all_new = list(set(all_new))[:100] # Ensure exactly up to 100 new ones

print(f"Fetching metadata for {len(all_new)} stocks...")
new_stocks_dict = {}

for sym in all_new:
    try:
        t = yf.Ticker(sym)
        info = t.info
        name = info.get('shortName', sym.replace('.NS', ''))
        sector = info.get('sector', 'Unknown')
        industry = info.get('industry', 'Unknown')
        new_stocks_dict[sym] = {"name": name, "sector": sector, "industry": industry}
    except Exception as e:
        print(f"Failed {sym}: {e}")
        new_stocks_dict[sym] = {"name": sym.replace('.NS', ''), "sector": "Unknown", "industry": "Unknown"}

target_file = Path("config/tickers.py")
content = target_file.read_text(encoding='utf-8')

new_dict_str = "NEW_100_STOCKS = {\n"
for sym, data in new_stocks_dict.items():
    new_dict_str += f'    "{sym}": {json.dumps(data)},\n'
new_dict_str += "}\n\n"

combine_str = "\nACTIVE_STOCKS = {**ACTIVE_STOCKS, **NEW_100_STOCKS}\n"
combine_str += "ACTIVE_TICKERS_LIST = list(ACTIVE_STOCKS.keys())\n"

content = content + "\n\n# ── Expanded 100 Stocks ────────────────────────────────────────────────────────\n" + new_dict_str + combine_str
target_file.write_text(content, encoding='utf-8')

print(f"Successfully added {len(new_stocks_dict)} new stocks to config/tickers.py")
