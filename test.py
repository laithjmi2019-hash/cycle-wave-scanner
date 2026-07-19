from data_fetcher import fetch_ticker_data_sync
from analyzer import analyze_asset
import pandas as pd

t, d1d, d1h = fetch_ticker_data_sync("TSLA")
t2, spy1d, spy1h = fetch_ticker_data_sync("SPY")

if d1d is not None and d1h is not None and spy1d is not None:
    res = analyze_asset("TSLA", d1d, d1h, spy1d)
    print("Analysis Results:", res)
else:
    print("Data fetch failed.")
