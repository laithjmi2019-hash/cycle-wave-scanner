import yfinance as yf
from analyzer import analyze_asset
from data_fetcher import US_EQUITIES, EU_EQUITIES, CHINA_EQUITIES, UAE_EQUITIES, CRYPTO

TICKERS = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES + CRYPTO

def manual_scan():
    print("Starting deep manual scan of 245 assets...")
    signals = []
    
    import concurrent.futures
    
    def process_ticker(ticker):
        try:
            t = yf.Ticker(ticker)
            d1d = t.history(period="1y", interval="1d", prepost=False)
            d1h = t.history(period="60d", interval="1h", prepost=False)
            if d1d.empty or d1h.empty:
                return None
            res = analyze_asset(ticker, d1d, d1h, None)
            if res and res["recommendation"] in ["LONG SNIPER", "SHORT SNIPER", "LONG MOMENTUM", "SHORT MOMENTUM"]:
                # Add current price for printing
                res["price"] = d1h['Close'].iloc[-1]
                return res
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(process_ticker, TICKERS)
        for r in results:
            if r is not None:
                signals.append(r)
                
    if signals:
        print(f"\nFOUND {len(signals)} OPPORTUNITIES:")
        for s in signals:
            print(f"[{s['recommendation']}] {s['ticker']} - Price: {s.get('price', 'N/A'):.2f} | RSI: {s['rsi']} | Target: {s['upside']} | Stop: {s['stop_loss']}")
            print(f"Reason: {s['reason']}\n")
    else:
        print("\nZERO perfect setups found matching V10 Institutional Criteria.")

if __name__ == "__main__":
    manual_scan()
