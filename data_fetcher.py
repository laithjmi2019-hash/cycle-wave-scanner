import yfinance as yf
import pandas as pd
import asyncio
import nest_asyncio

# Apply nest_asyncio to allow running asyncio in Streamlit/Jupyter
nest_asyncio.apply()

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

async def fetch_all_tickers_async(tickers: list):
    """Asynchronously fetch data for multiple tickers using ThreadPool."""
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(None, fetch_ticker_data_sync, ticker)
        for ticker in tickers
    ]
    results = await asyncio.gather(*tasks)
    return results

def get_market_data():
    """Wrapper to fetch market breadth (SPY) + top 100 concurrently."""
    loop = asyncio.get_event_loop()
    tickers_to_fetch = ["SPY"] + TOP_100_TICKERS
    results = loop.run_until_complete(fetch_all_tickers_async(tickers_to_fetch))
    
    data_dict = {}
    for ticker, df_1d, df_1h in results:
        if df_1d is not None and df_1h is not None:
            data_dict[ticker] = {"1d": df_1d, "1h": df_1h}
            
    return data_dict
