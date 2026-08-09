"""
data/universe.py — Asset universe definitions and market metadata.
Single source of truth for all tickers, markets, and classifications.
"""
import datetime

# ── US EQUITIES ──────────────────────────────────────────────────────────
US_EQUITIES = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","GOOG","BRK-B","JPM",
    "JNJ","V","UNH","XOM","WMT","MA","PG","HD","CVX","MRK","ABBV","LLY",
    "PEP","COST","KO","BAC","MCD","CSCO","TMO","ACN","CRM","ABT","AVGO",
    "WFC","DHR","NEE","LIN","AMD","TXN","HON","PM","UPS","RTX","LOW",
    "QCOM","IBM","SBUX","ELV","GS","AMGN","MDLZ","BLK","DE","CAT","AXP",
    "INTC","SCHW","GILD","BMY","SYK","ZTS","C","SPGI","TJX","ADP",
    "MO","SO","DUK","CL","CME","TMUS","USB","EW","ICE","MMC",
    "AON","PLD","BSX","CI","NSC","ITW","PNC","APD","HUM","F",
    "GM","REGN","MRNA","NFLX","BA","DIS","GE","NKE","PYPL",
]

# ── EU EQUITIES ──────────────────────────────────────────────────────────
EU_EQUITIES = [
    # France (Euronext Paris)
    "MC.PA","TTE.PA","SAN.PA","AIR.PA","BNP.PA","SGO.PA","RI.PA",
    "SU.PA","CS.PA","OR.PA","KER.PA","STM.PA","CAP.PA","VIV.PA","DG.PA",
    # Germany (XETRA)
    "SAP.DE","SIE.DE","ALV.DE","MUV2.DE","DTE.DE","BMW.DE","RWE.DE",
    "BAYN.DE","BAS.DE","DBK.DE","VOW3.DE","MBG.DE","HNR1.DE","CON.DE",
    # Netherlands
    "ASML.AS","PHIA.AS","AD.AS","UNA.AS","HEIA.AS","NN.AS","RAND.AS",
    # Spain
    "ITX.MC","BBVA.MC","SAN.MC","TEF.MC","IBE.MC","NTGY.MC","REP.MC",
    # UK
    "SHEL.L","AZN.L","HSBA.L","BP.L","GSK.L","RIO.L","ULVR.L","VOD.L",
    # Switzerland
    "NESN.SW","ROG.SW","NOVN.SW","ABB.SW","ZURN.SW","ALC.SW",
]

# ── CHINA / HK EQUITIES ──────────────────────────────────────────────────
CHINA_EQUITIES = [
    "9988.HK","0700.HK","3690.HK","1810.HK","9618.HK",
    "0005.HK","0939.HK","1299.HK","2318.HK","0388.HK",
    "601318.SS","600036.SS","600519.SS","601166.SS","000858.SZ",
    "000333.SZ","000002.SZ","600276.SS","601398.SS","600900.SS",
]

# ── UAE EQUITIES ─────────────────────────────────────────────────────────
UAE_EQUITIES = [
    "EMAAR.AE","FAB.AE","DIB.AE","ADNOCDIST.AE","ALDAR.AE",
    "ADCB.AE","ENBD.AE","AIRARABIA.AE","DEWA.AE","IHC.AE","TAQA.AE",
]

# ── CRYPTO ───────────────────────────────────────────────────────────────
CRYPTO = [
    "BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD","ADA-USD",
    "AVAX-USD","DOT-USD","LINK-USD","MATIC-USD","UNI-USD","ATOM-USD",
    "LTC-USD","BCH-USD","FIL-USD","NEAR-USD","AAVE-USD","GRT-USD",
    "RNDR-USD","FET-USD","ARB-USD","OP-USD","APT-USD","SUI-USD","TIA-USD",
]

# ── MARKET MAPS ──────────────────────────────────────────────────────────
ASSET_MARKET_MAP: dict[str, str] = {}
for t in US_EQUITIES:  ASSET_MARKET_MAP[t] = "US"
for t in EU_EQUITIES:  ASSET_MARKET_MAP[t] = "EU"
for t in CHINA_EQUITIES: ASSET_MARKET_MAP[t] = "CHINA"
for t in UAE_EQUITIES: ASSET_MARKET_MAP[t] = "UAE"
for t in CRYPTO:       ASSET_MARKET_MAP[t] = "CRYPTO"

ASSET_CLASS_MAP: dict[str, str] = {}
for t in US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES:
    ASSET_CLASS_MAP[t] = "STOCKS"
for t in CRYPTO:
    ASSET_CLASS_MAP[t] = "CRYPTO"

ALL_STOCKS = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES
ALL_ASSETS  = ALL_STOCKS + CRYPTO

# ── BINANCE SYMBOL MAP — yfinance ticker → Binance perpetual ─────────────
BINANCE_PERP_MAP = {
    "BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT", "BNB-USD": "BNBUSDT",
    "SOL-USD": "SOLUSDT", "XRP-USD": "XRPUSDT", "ADA-USD": "ADAUSDT",
    "AVAX-USD":"AVAXUSDT","DOT-USD": "DOTUSDT", "LINK-USD":"LINKUSDT",
    "MATIC-USD":"MATICUSDT","UNI-USD":"UNIUSDT","ATOM-USD":"ATOMUSDT",
    "LTC-USD": "LTCUSDT", "BCH-USD": "BCHUSDT", "FIL-USD": "FILUSDT",
    "NEAR-USD":"NEARUSDT","AAVE-USD":"AAVEUSDT","GRT-USD": "GRTUSDT",
    "RNDR-USD":"RENDERUSDT","FET-USD":"FETUSDT","ARB-USD":"ARBUSDT",
    "OP-USD":  "OPUSDT",  "APT-USD": "APTUSDT", "SUI-USD": "SUIUSDT",
    "TIA-USD": "TIAUSDT",
}

# ── MARKET HOURS ─────────────────────────────────────────────────────────
def market_is_open(market: str) -> bool:
    """Check if a market is currently open (UTC)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    wd  = now.weekday()   # 0=Mon … 6=Sun
    h   = now.hour
    m   = now.minute
    hm  = h * 60 + m

    if market == "CRYPTO":
        return True   # 24/7

    if wd >= 5:   # Saturday / Sunday — all equity markets closed
        return False

    schedules = {
        "US":    (13 * 60 + 30,  20 * 60),        # 13:30–20:00 UTC
        "EU":    ( 7 * 60,       15 * 60 + 30),   # 07:00–15:30 UTC
        "CHINA": ( 1 * 60 + 30,   8 * 60),         # 01:30–08:00 UTC
        "UAE":   ( 6 * 60,       14 * 60),          # 06:00–14:00 UTC
    }
    if market not in schedules:
        return True
    lo, hi = schedules[market]
    return lo <= hm <= hi
