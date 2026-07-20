import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import datetime

# ============================================================
# MARKET HOURS (UTC) — Only scan when market is open
# ============================================================
MARKET_HOURS = {
    "US":     (13, 30, 20, 0),   # 13:30–20:00 UTC
    "EU":     (7,  0,  16, 30),  # 07:00–16:30 UTC
    "CHINA":  (1,  30, 8,  0),   # 01:30–08:00 UTC
    "UAE":    (6,  0,  13, 0),   # 06:00–13:00 UTC
    "CRYPTO": None,              # 24/7
}

def market_is_open(market: str) -> bool:
    """Returns True if the given market is currently open."""
    if market == "CRYPTO" or MARKET_HOURS[market] is None:
        return True
    now = datetime.datetime.utcnow()
    oh, om, ch, cm = MARKET_HOURS[market]
    open_time  = now.replace(hour=oh, minute=om, second=0, microsecond=0)
    close_time = now.replace(hour=ch, minute=cm, second=0, microsecond=0)
    # On weekends, all equity markets are closed
    if now.weekday() >= 5:
        return False
    return open_time <= now <= close_time

# ============================================================
# TOP 100 US EQUITIES (cleaned — removed confirmed dead tickers)
# ============================================================
US_EQUITIES = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "TSLA", "AVGO",
    "LLY",  "JPM",  "UNH",  "V",    "XOM",  "MA",    "JNJ",  "PG",    "HD",   "COST",
    "MRK",  "ABBV", "CVX",  "CRM",  "AMD",  "PEP",   "NFLX", "BAC",   "KO",   "TMO",
    "ADBE", "WMT",  "MCD",  "DIS",  "CSCO", "ABT",   "INTU", "QCOM",  "INTC", "VZ",
    "CMCSA","DHR",  "PFE",  "NOW",  "AMGN", "IBM",   "TXN",  "BA",    "SPGI", "GE",
    "PM",   "HON",  "COP",  "ISRG", "UNP",  "CAT",   "NKE",  "RTX",   "GS",   "SYK",
    "LOW",  "BLK",  "PGR",  "TJX",  "MDT",  "C",     "AXP",  "BSX",   "VRTX", "CHTR",
    "LMT",  "CB",   "GILD", "DE",   "BMY",  "ADP",   "ADI",  "SBUX",  "MDLZ", "CVS",
    "PLD",  "LRCX", "CI",   "ZTS",  "MO",   "T",     "CME",  "BDX",   "DUK",  "SO",
    "SLB",  "EOG",  "AON",  "REGN", "CL",   "ITW",   "SHW",  "MMM",   "FDX",  "UPS"
]

# ============================================================
# TOP 50 EU EQUITIES (fixed dead tickers)
# ============================================================
EU_EQUITIES = [
    "ASML.AS", "MC.PA",   "NVO",     "SAP.DE",  "SHEL.L",  "AZN.L",   "NOVN.SW", "TTE.PA",  "HSBA.L",
    "OR.PA",   "SAN.PA",  "SIE.DE",  "ULVR.L",  "SU.PA",   "IBE.MC",  "AI.PA",   "ALV.DE",  "CDI.PA",  "BP.L",
    "BNP.PA",  "DTE.DE",  "AIR.PA",  "EL.PA",   "CS.PA",   "ITX.MC",  "MUV2.DE", "ZURN.SW", "RIO.L",
    "ENEL.MI", "BATS.L",  "IFX.DE",  "GSK.L",   "ADYEN.AS","ISP.MI",  "UBSG.SW", "BAS.DE",  "INGA.AS", "ABI.BR",
    "GLEN.L",  "REL.L",   "ABN.AS",  "SAF.PA",  "PRU.L",   "BMW.DE",  "MBG.DE",  "VOW3.DE",
    "NG.L",    "AD.AS",   "SSE.L",   "SGE.L",   "BARC.L",  "UCG.MI",  "SGO.PA",  "BAYN.DE", "HEIA.AS",
    "RWE.DE",  "ALC.SW",  "HOLN.SW", "LR.PA",   "NOKIA.HE","ERIC-B.ST","VOLV-B.ST","EQNR.OL", "KER.PA",  "DHL.DE"
]

# ============================================================
# TOP 25 CHINESE EQUITIES (HK listed)
# ============================================================
CHINA_EQUITIES = [
    "0700.HK", "9988.HK", "3690.HK", "1211.HK", "0939.HK", "1398.HK", "0941.HK",
    "0883.HK", "3988.HK", "1810.HK", "0386.HK", "2318.HK", "0857.HK", "1088.HK",
    "2020.HK", "1928.HK", "2382.HK", "0293.HK", "0020.HK", "1109.HK",
    "0175.HK", "0388.HK", "0005.HK", "1299.HK", "9618.HK"
]

# ============================================================
# UAE EQUITIES (only confirmed working tickers)
# ============================================================
UAE_EQUITIES = [
    "EMAAR.AE", "DIB.AE", "EMIRATESNBD.AE", "SALIK.AE", "TECOM.AE",
    "EMPOWER.AE", "DFM.AE", "ARMX.AE", "AIRARABIA.AE", "TABREED.AE", "DU.AE"
]

# ============================================================
# TOP 25 CRYPTO (24/7 — always active)
# ============================================================
CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD",  "XRP-USD",
    "DOGE-USD","ADA-USD", "TRX-USD", "AVAX-USD", "SHIB-USD",
    "DOT-USD", "LINK-USD","BCH-USD", "NEAR-USD",  "LTC-USD",
    "XLM-USD", "ETC-USD", "ATOM-USD","XMR-USD",   "HBAR-USD",
    "VET-USD", "MKR-USD", "AAVE-USD","ALGO-USD",  "FIL-USD"
]

# Asset → Market mapping for hours filter
ASSET_MARKET_MAP = {}
for t in US_EQUITIES:    ASSET_MARKET_MAP[t] = "US"
for t in EU_EQUITIES:    ASSET_MARKET_MAP[t] = "EU"
for t in CHINA_EQUITIES: ASSET_MARKET_MAP[t] = "CHINA"
for t in UAE_EQUITIES:   ASSET_MARKET_MAP[t] = "UAE"
for t in CRYPTO:         ASSET_MARKET_MAP[t] = "CRYPTO"

def fetch_ticker_data_sync(ticker: str):
    """Fetch 1D and 1H data for a ticker."""
    try:
        t    = yf.Ticker(ticker)
        d1d  = t.history(period="1y",  interval="1d", prepost=False)
        d1h  = t.history(period="60d", interval="1h", prepost=False)
        if d1d.empty or d1h.empty:
            return ticker, None, None, None
        return ticker, d1d, d1h, None
    except Exception:
        return ticker, None, None, None

def get_regional_data(tickers, include_spy=True):
    """Fetch a list of tickers concurrently."""
    to_fetch = list(tickers)
    if include_spy and "SPY" not in to_fetch:
        to_fetch.insert(0, "SPY")
    data = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        for ticker, d1d, d1h, _ in ex.map(fetch_ticker_data_sync, to_fetch):
            if d1d is not None and d1h is not None:
                data[ticker] = {"1d": d1d, "1h": d1h, "15m": None}
    return data

def get_crypto_data():
    """Fetch crypto tickers concurrently."""
    to_fetch = list(set(["BTC-USD"] + CRYPTO))
    data = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        for ticker, d1d, d1h, _ in ex.map(fetch_ticker_data_sync, to_fetch):
            if d1d is not None and d1h is not None:
                data[ticker] = {"1d": d1d, "1h": d1h, "15m": None}
    return data
