import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Top 100 US Equities
US_EQUITIES = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "TSLA", "AVGO",
    "LLY", "JPM", "UNH", "V", "XOM", "MA", "JNJ", "PG", "HD", "COST",
    "MRK", "ABBV", "CVX", "CRM", "AMD", "PEP", "NFLX", "BAC", "KO", "TMO",
    "ADBE", "WMT", "MCD", "DIS", "CSCO", "ABT", "INTU", "QCOM", "INTC", "VZ",
    "CMCSA", "DHR", "PFE", "NOW", "AMGN", "IBM", "TXN", "BA", "SPGI", "GE",
    "PM", "HON", "COP", "ISRG", "UNP", "CAT", "NKE", "RTX", "GS", "SYK",
    "LOW", "BLK", "PGR", "TJX", "MDT", "C", "AXP", "BSX", "VRTX", "CHTR",
    "LMT", "CB", "MMC", "GILD", "DE", "BMY", "ADP", "ADI", "SBUX", "MDLZ",
    "CVS", "PLD", "LRCX", "GPN", "CI", "ZTS", "MO", "T", "FI", "CME",
    "BDX", "DUK", "SO", "SLB", "EOG", "AON", "REGN", "CL", "ITW", "SHW"
]

# Top 75 EU Equities
EU_EQUITIES = [
    "ASML.AS", "MC.PA", "NVO", "SAP.DE", "SHEL.L", "AZN.L", "NOVN.SW", "ROG.SW", "TTE.PA", "HSBA.L",
    "OR.PA", "SAN.PA", "SIE.DE", "ULVR.L", "SU.PA", "IBE.MC", "AI.PA", "ALV.DE", "CDI.PA", "BP.L",
    "BNP.PA", "DTE.DE", "AIR.PA", "EL.PA", "CS.PA", "VCI.PA", "ITX.MC", "MUV2.DE", "ZURN.SW", "RIO.L",
    "ENEL.MI", "BATS.L", "IFX.DE", "GSK.L", "ADYEN.AS", "ISP.MI", "UBSG.SW", "BAS.DE", "INGA.AS", "ABI.BR",
    "DPW.DE", "GLEN.L", "REL.L", "ABN.AS", "SAF.PA", "PRU.L", "Kering.PA", "BMW.DE", "MBG.DE", "VOW3.DE",
    "CPG.L", "NG.L", "AD.AS", "SSE.L", "SGE.L", "BARC.L", "BPE.MI", "UCG.MI", "SGO.PA", "STLAM.MI",
    "BAYN.DE", "GBLB.BR", "HEIA.AS", "RWE.DE", "ALC.SW", "HOLN.SW", "LR.PA", "KONE.HE", "NOKIA.HE", "ERIC-B.ST",
    "VOLV-B.ST", "ATCO-A.ST", "INVE-B.ST", "NDA-FI.HE", "EQNR.OL"
]

# Top 25 Chinese Equities (Accessible via HK)
CHINA_EQUITIES = [
    "0700.HK", "9988.HK", "3690.HK", "1211.HK", "0939.HK", "1398.HK", "0941.HK", "0883.HK", "3988.HK", "1810.HK",
    "0386.HK", "2318.HK", "0857.HK", "1088.HK", "2020.HK", "1928.HK", "2382.HK", "0293.HK", "0020.HK", "1109.HK",
    "0175.HK", "0388.HK", "0005.HK", "1299.HK", "9618.HK"
]

# Top 25 UAE/Dubai Equities
UAE_EQUITIES = [
    "EMAAR.AE", "FAB.AE", "DIB.AE", "EMIRATESNBD.AE", "ADCB.AE", "IHC.AE", "TAQA.AE", "ALDAR.AE", "ADNOCDIST.AE", "ADNOCDRILL.AE",
    "FERTIGLOBE.AE", "BOROUGE.AE", "DEWA.AE", "SALIK.AE", "TECOM.AE", "EMPOWER.AE", "DFM.AE", "ARMX.AE", "AIRARABIA.AE", "TABREED.AE",
    "DU.AE", "EAND.AE", "AGTHIA.AE", "QHOLDING.AE", "MULTIPLY.AE"
]

# Top 25 Crypto
CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", 
    "TRX-USD", "AVAX-USD", "SHIB-USD", "DOT-USD", "LINK-USD", "BCH-USD", "NEAR-USD", 
    "LTC-USD", "UNI-USD", "XLM-USD", "ETC-USD", "ATOM-USD", "XMR-USD", "HBAR-USD", 
    "VET-USD", "MKR-USD", "AAVE-USD", "ALGO-USD"
]

def fetch_ticker_data_sync(ticker: str, fetch_15m: bool = False):
    """Fetch 1D, 1H, and optionally 15m data. prepost=False excludes pre/after-market noise."""
    try:
        t = yf.Ticker(ticker)
        df_1d = t.history(period="1y",  interval="1d",  prepost=False)
        df_1h = t.history(period="60d", interval="1h",  prepost=False)
        
        df_15m = None
        if fetch_15m:
            df_15m = t.history(period="7d", interval="15m", prepost=False)
            
        if df_1d.empty or df_1h.empty or (fetch_15m and df_15m.empty):
            return ticker, None, None, None
            
        return ticker, df_1d, df_1h, df_15m
    except Exception:
        return ticker, None, None, None

def get_regional_data(tickers, include_spy=True):
    """Generalized function to fetch any list of tickers concurrently."""
    tickers_to_fetch = list(tickers)
    if include_spy and "SPY" not in tickers_to_fetch:
        tickers_to_fetch.insert(0, "SPY")
        
    data_dict = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(lambda t: fetch_ticker_data_sync(t, fetch_15m=True), tickers_to_fetch)
        for ticker, df_1d, df_1h, df_15m in results:
            if df_1d is not None and df_1h is not None and df_15m is not None:
                data_dict[ticker] = {"1d": df_1d, "1h": df_1h, "15m": df_15m}
                
    return data_dict

def get_crypto_data():
    """Wrapper to fetch Crypto concurrently using BTC-USD as macro."""
    tickers_to_fetch = list(set(["BTC-USD"] + CRYPTO))
    
    data_dict = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(lambda t: fetch_ticker_data_sync(t, fetch_15m=True), tickers_to_fetch)
        for ticker, df_1d, df_1h, df_15m in results:
            if df_1d is not None and df_1h is not None and df_15m is not None:
                data_dict[ticker] = {"1d": df_1d, "1h": df_1h, "15m": df_15m}
                
    return data_dict
