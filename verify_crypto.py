"""
INDEPENDENT CRYPTO VERIFICATION SCAN
Raw indicator verification - completely independent of analyzer.py
Shows ALL values so we can manually verify if V11 logic is correct.
"""
import yfinance as yf
import pandas as pd
import ta
import warnings
warnings.filterwarnings("ignore")

CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD",  "XRP-USD",
    "DOGE-USD","ADA-USD", "TRX-USD", "AVAX-USD", "SHIB-USD",
    "DOT-USD", "LINK-USD","BCH-USD", "NEAR-USD",  "LTC-USD",
    "XLM-USD", "ETC-USD", "ATOM-USD","XMR-USD",   "HBAR-USD",
    "VET-USD", "MKR-USD", "AAVE-USD","ALGO-USD",  "FIL-USD"
]

def scan_crypto(ticker):
    try:
        t   = yf.Ticker(ticker)
        d1h = t.history(period="60d", interval="1h", prepost=False)
        d1d = t.history(period="1y",  interval="1d", prepost=False)
        if len(d1h) < 30:
            return None

        c = d1h['Close']
        h = d1h['High']
        l = d1h['Low']
        v = d1h['Volume']

        # All indicators independently computed
        rsi = ta.momentum.RSIIndicator(c, 14).rsi().iloc[-1]

        bb  = ta.volatility.BollingerBands(c, 20, 2)
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_mid   = bb.bollinger_mavg().iloc[-1]

        adx = ta.trend.ADXIndicator(h, l, c, 14).adx().iloc[-1]

        atr = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range().iloc[-1]

        vol_sma   = v.rolling(20).mean().iloc[-1]
        vol_ratio = v.iloc[-1] / vol_sma

        roll_mean = c.rolling(20).mean()
        roll_std  = c.rolling(20).std()
        zscore    = ((c - roll_mean) / roll_std).iloc[-1]

        vwap = ((c * v).rolling(24).sum() / v.rolling(24).sum()).iloc[-1]

        macd_obj  = ta.trend.MACD(c)
        macd_h    = macd_obj.macd_diff().iloc[-1]
        macd_prev = macd_obj.macd_diff().iloc[-2]

        price = c.iloc[-1]

        # Daily 200 SMA
        sma200d = None
        if len(d1d) >= 200:
            sma200d = ta.trend.SMAIndicator(d1d['Close'], 200).sma_indicator().iloc[-1]

        # V11 Logic evaluation
        market_ranging  = adx < 25
        market_trending = adx >= 25

        v11_signal = "WAIT"
        v11_reason = ""

        # Strategy A: Mean Reversion
        if market_ranging and rsi < 30 and zscore < -1.5 and price <= bb_lower:
            if sma200d and price < (sma200d * 0.90):
                v11_signal = "BLOCKED (200SMA)"
                v11_reason = "Below 200 SMA by >10%"
            else:
                v11_signal = "LONG SNIPER"
                v11_reason = "All 4 conditions met"

        elif market_ranging and rsi > 70 and zscore > 1.5 and price >= bb_upper:
            v11_signal = "SHORT SNIPER"
            v11_reason = "Overbought in ranging market"

        # Strategy B: Momentum Breakout
        elif market_trending and price > bb_upper and vol_ratio > 1.5 and macd_h > 0 and macd_prev <= 0:
            if sma200d and price < sma200d:
                v11_signal = "BLOCKED (200SMA)"
                v11_reason = "Momentum blocked below 200 SMA"
            else:
                v11_signal = "LONG MOMENTUM"
                v11_reason = "Momentum breakout confirmed"

        elif market_trending and price < bb_lower and vol_ratio > 1.5 and macd_h < 0 and macd_prev >= 0:
            v11_signal = "SHORT MOMENTUM"
            v11_reason = "Momentum breakdown confirmed"

        # Near-miss analysis
        near_long  = rsi < 35 and zscore < -1.0
        near_short = rsi > 65 and zscore > 1.0

        return {
            "ticker":      ticker,
            "price":       round(price, 4),
            "rsi":         round(rsi, 1),
            "adx":         round(adx, 1),
            "zscore":      round(zscore, 2),
            "vol_ratio":   round(vol_ratio, 2),
            "bb_lower":    round(bb_lower, 4),
            "bb_upper":    round(bb_upper, 4),
            "at_lower":    price <= bb_lower,
            "at_upper":    price >= bb_upper,
            "below_vwap":  price < vwap,
            "regime":      "RANGING" if market_ranging else "TRENDING",
            "sma200d":     round(sma200d, 4) if sma200d else "N/A",
            "v11_signal":  v11_signal,
            "near_long":   near_long,
            "near_short":  near_short,
            "v11_reason":  v11_reason,
        }
    except Exception as e:
        print(f"  ERROR {ticker}: {e}")
        return None

if __name__ == "__main__":
    print("="*100)
    print("INDEPENDENT CRYPTO VERIFICATION SCAN — All raw indicator values")
    print("="*100)
    print(f"{'TICKER':<12} {'PRICE':>10} {'RSI':>5} {'ADX':>5} {'Z':>6} {'VOL':>5} {'REGIME':<10} {'BB':>8} {'VWAP':>6} {'V11 SIGNAL':<18} {'NOTE'}")
    print("-"*100)

    signals, near_longs, near_shorts = [], [], []

    for ticker in CRYPTO:
        r = scan_crypto(ticker)
        if not r:
            continue

        bb_pos = "LOWER" if r['at_lower'] else ("UPPER" if r['at_upper'] else "inside")
        vwap_s = "below" if r['below_vwap'] else "above"

        note = ""
        if r['near_long']:  note = "<-- NEAR LONG"
        if r['near_short']: note = "<-- NEAR SHORT"
        if r['v11_signal'] not in ["WAIT", ""]: note = "<<<<< SIGNAL!"

        print(f"{r['ticker']:<12} {r['price']:>10} {r['rsi']:>5} {r['adx']:>5} {r['zscore']:>6} {r['vol_ratio']:>5} {r['regime']:<10} {bb_pos:>8} {vwap_s:>6} {r['v11_signal']:<18} {note}")

        if r['v11_signal'] not in ["WAIT", ""]:
            signals.append(r)
        if r['near_long']:
            near_longs.append(r)
        if r['near_short']:
            near_shorts.append(r)

    print("\n" + "="*100)
    if signals:
        print(f"\nACTIVE SIGNALS ({len(signals)}):")
        for s in signals:
            print(f"  [{s['v11_signal']}] {s['ticker']} — {s['v11_reason']}")
    else:
        print("\nNO ACTIVE V11 SIGNALS IN CRYPTO RIGHT NOW.")

    if near_longs:
        print(f"\nNEAR-LONG (RSI<35 and Z<-1.0 — getting close) ({len(near_longs)}):")
        for s in near_longs:
            print(f"  {s['ticker']} — RSI: {s['rsi']}, Z-Score: {s['zscore']}, ADX: {s['adx']} ({s['regime']})")

    if near_shorts:
        print(f"\nNEAR-SHORT (RSI>65 and Z>1.0 — getting close) ({len(near_shorts)}):")
        for s in near_shorts:
            print(f"  {s['ticker']} — RSI: {s['rsi']}, Z-Score: {s['zscore']}, ADX: {s['adx']} ({s['regime']})")

    print("="*100)
