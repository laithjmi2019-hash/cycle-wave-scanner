import yfinance as yf
import ta
from data_fetcher import US_EQUITIES, EU_EQUITIES, CHINA_EQUITIES, UAE_EQUITIES, CRYPTO
import concurrent.futures

TICKERS = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES + CRYPTO

def deep_scan():
    print("Starting Deep Relaxed Market Scan (Hunting for Tier-2 and Developing Setups)...")
    results = []
    
    def process_ticker(ticker):
        try:
            t = yf.Ticker(ticker)
            d1h = t.history(period="60d", interval="1h", prepost=False)
            if len(d1h) < 26: return None
            
            # Calc indicators
            d1h['rsi'] = ta.momentum.RSIIndicator(d1h['Close'], window=14).rsi()
            bb = ta.volatility.BollingerBands(close=d1h['Close'], window=20, window_dev=2.0)
            d1h['bb_lower'] = bb.bollinger_lband()
            d1h['bb_upper'] = bb.bollinger_hband()
            d1h['vol_sma_20'] = ta.trend.SMAIndicator(d1h['Volume'], window=20).sma_indicator()
            macd = ta.trend.MACD(d1h['Close'])
            d1h['macd_h'] = macd.macd_diff()
            
            c = d1h.iloc[-1]
            prev = d1h.iloc[-2]
            
            price = c['Close']
            rsi = c['rsi']
            
            # 1. Developing Sniper (Oversold, near band)
            if rsi < 30 and price <= (c['bb_lower'] * 1.01):
                return {"ticker": ticker, "type": "Developing Sniper (Oversold)", "price": price, "rsi": rsi, "info": f"Near Lower BB. RSI: {rsi:.1f}"}
                
            # 2. Developing Short (Overbought, near upper band)
            if rsi > 70 and price >= (c['bb_upper'] * 0.99):
                return {"ticker": ticker, "type": "Developing Short (Overbought)", "price": price, "rsi": rsi, "info": f"Near Upper BB. RSI: {rsi:.1f}"}
                
            # 3. Volume Surge
            if c['Volume'] > (c['vol_sma_20'] * 1.5) and c['macd_h'] > 0 and prev['macd_h'] <= 0:
                return {"ticker": ticker, "type": "Volume Surge Breakout", "price": price, "rsi": rsi, "info": f"Vol > 150%. MACD crossed positive."}
                
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        for r in executor.map(process_ticker, TICKERS):
            if r: results.append(r)
            
    # Sort and print
    print(f"\\nFOUND {len(results)} DEVELOPING OPPORTUNITIES:\\n")
    for r in sorted(results, key=lambda x: x['type']):
        print(f"[{r['type']}] {r['ticker']} - Price: {r['price']:.2f} | {r['info']}")

if __name__ == "__main__":
    deep_scan()
