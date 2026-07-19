import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Top 100 US Equities
TOP_100_TICKERS = [
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

# Top 25 Crypto
TOP_25_CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", 
    "TRX-USD", "AVAX-USD", "SHIB-USD", "DOT-USD", "LINK-USD", "BCH-USD", "NEAR-USD", 
    "LTC-USD", "UNI-USD", "XLM-USD", "ETC-USD", "ATOM-USD", "XMR-USD", "HBAR-USD", 
    "VET-USD", "MKR-USD", "AAVE-USD", "ALGO-USD"
]

def fetch_ticker_data_sync(ticker: str):
    """Fetch 1D and 1H data for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        df_1d = t.history(period="1y", interval="1d")
        df_1h = t.history(period="60d", interval="1h")
        
        if df_1d.empty or df_1h.empty:
            return ticker, None, None
            
        return ticker, df_1d, df_1h
    except Exception as e:
        return ticker, None, None

def get_market_data():
    """Wrapper to fetch market breadth (SPY) + top 100 concurrently using ThreadPool."""
    tickers_to_fetch = ["SPY"] + TOP_100_TICKERS
    
    data_dict = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(fetch_ticker_data_sync, tickers_to_fetch)
        for ticker, df_1d, df_1h in results:
            if df_1d is not None and df_1h is not None:
                data_dict[ticker] = {"1d": df_1d, "1h": df_1h}
                
    return data_dict

def get_crypto_data():
    """Wrapper to fetch top 25 Crypto concurrently. BTC is used as the market breadth filter."""
    tickers_to_fetch = list(set(["BTC-USD"] + TOP_25_CRYPTO))
    
    data_dict = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(fetch_ticker_data_sync, tickers_to_fetch)
        for ticker, df_1d, df_1h in results:
            if df_1d is not None and df_1h is not None:
                data_dict[ticker] = {"1d": df_1d, "1h": df_1h}
                
    return data_dict
