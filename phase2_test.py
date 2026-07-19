import time
from data_fetcher import get_market_data, fetch_ticker_data_sync
from analyzer import analyze_asset

def test_speed_and_logic():
    print("--- PHASE 2: Live Speed & Logic Audit ---")
    start_time = time.time()
    
    # 1. Speed Test (Top 100 + SPY)
    print("Fetching Top 100 Tickers asynchronously...")
    market_data = get_market_data()
    
    # Assuming SPY is successfully loaded
    spy_1d = market_data.get("SPY", {}).get("1d")
    if spy_1d is None:
        print("SPY data missing, aborting test.")
        return
        
    for ticker, data in market_data.items():
        if ticker == "SPY":
            continue
        analyze_asset(ticker, data["1d"], data["1h"], spy_1d)
        
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Total Execution Time for Top 100 Fetch + Vectorized Math: {execution_time:.2f} seconds")
    if execution_time > 15:
        print("WARNING: Execution time exceeded 15 seconds limit!")
    else:
        print("SUCCESS: Execution time is under 15 seconds.")
        
    print("\n--- LOGIC TEST ---")
    # 2. Logic Test for NVDA and TSLA
    for tkr in ["NVDA", "TSLA"]:
        if tkr in market_data:
            res = analyze_asset(tkr, market_data[tkr]["1d"], market_data[tkr]["1h"], spy_1d)
            print(f"\n[{tkr}] Results:")
            print(f"  Signal:      {res['signal']}")
            print(f"  Score:       {res['score']}")
            print(f"  Trend 1D:    {res['trend_1d']}")
            print(f"  Div 1H:      {res['div_1h']}")
            print(f"  FVG Tap:     {res['fvg_tap']}")
            print(f"  PA Trigger:  {res['pa_trigger']}")
            print(f"  Reason:      {res['reason']}")
        else:
            print(f"[{tkr}] Missing from market data!")

if __name__ == "__main__":
    test_speed_and_logic()
