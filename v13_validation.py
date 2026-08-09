"""
V13 VALIDATION BACKTEST
Tests V12 (current) vs all V13 changes to confirm win rate improvement.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import warnings
warnings.filterwarnings("ignore")

TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","JPM","XOM","GOOGL","AMD",
    "BA","NFLX","INTC","BAC","COST","DIS","SBUX","WMT","CVX","V",
    "ASML.AS","MC.PA","SAP.DE","TTE.PA","SGO.PA"
]

def load(ticker):
    t = yf.Ticker(ticker)
    df = t.history(period="1y", interval="1h", prepost=False)
    return df if len(df) >= 200 else None

def indicators(df):
    c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']
    df['rsi']     = ta.momentum.RSIIndicator(c, 14).rsi()
    df['rsi_prev']= df['rsi'].shift(1)
    df['rsi_prev2']= df['rsi'].shift(2)
    df['rsi_prev3']= df['rsi'].shift(3)
    bb = ta.volatility.BollingerBands(c, 20, 2)
    df['bb_l']    = bb.bollinger_lband()
    df['bb_u']    = bb.bollinger_hband()
    df['adx']     = ta.trend.ADXIndicator(h, l, c, 14).adx()
    df['atr']     = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range()
    df['vol_sma'] = v.rolling(20).mean()
    df['volr']    = v / df['vol_sma']
    rm = c.rolling(20).mean(); rs = c.rolling(20).std()
    df['z']       = (c - rm) / rs
    df['ema50']   = ta.trend.EMAIndicator(c, 50).ema_indicator()
    df['mfi']     = ta.volume.MFIIndicator(h, l, c, v, 14).money_flow_index()
    df['sma200']  = ta.trend.SMAIndicator(c, 200).sma_indicator()
    df['vwap']    = (c * v).rolling(24).sum() / v.rolling(24).sum()
    return df.dropna()

def backtest(df, fn, stop_m=2.0, tgt_m=4.0):
    sigs = fn(df)
    w = l = 0
    for i in sigs:
        ei = i + 1
        if ei >= len(df): continue
        entry = df['Close'].iloc[ei]
        atr   = df['atr'].iloc[ei]
        stop  = entry - stop_m * atr
        target= entry + tgt_m * atr
        for j in range(ei+1, min(ei+48, len(df))):
            if df['Low'].iloc[j]  <= stop:  l+=1; break
            if df['High'].iloc[j] >= target: w+=1; break
    t = w+l
    if t==0: return None
    wr  = w/t
    exp = round(wr*(tgt_m/stop_m)-(1-wr),3)
    return {'s':t,'w':w,'l':l,'wr':round(wr*100,1),'exp':exp}

# ── STRATEGIES ───────────────────────────────────────────────────────────

def v12_current(df):
    """V12: RSI<30 + BB touch + ADX<25 + Z<-1.5 (TOUCH method)"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def v13_rsi_cross(df):
    """V13-A: RSI CROSS — RSI just crossed back above 30 from below (bounce confirmed)"""
    rsi_was_below = (df['rsi_prev']<30)|(df['rsi_prev2']<30)|(df['rsi_prev3']<30)
    m = (df['rsi']>=30)&(df['rsi']<40)&rsi_was_below&(df['adx']<25)&(df['z']<-1.0)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def v13_vol_exhaust(df):
    """V13-B: RSI cross + Volume DRYING UP at lows (sellers exhausted)"""
    rsi_was_below = (df['rsi_prev']<30)|(df['rsi_prev2']<30)|(df['rsi_prev3']<30)
    m = (df['rsi']>=30)&(df['rsi']<40)&rsi_was_below&(df['adx']<25)&(df['volr']<0.85)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def v13_ema50(df):
    """V13-C: RSI cross + price near 50 EMA (mean reversion target = EMA)"""
    rsi_was_below = (df['rsi_prev']<30)|(df['rsi_prev2']<30)|(df['rsi_prev3']<30)
    near_ema = df['Close'] <= (df['ema50'] * 1.02)  # within 2% of 50 EMA
    m = (df['rsi']>=30)&(df['rsi']<40)&rsi_was_below&(df['adx']<25)&near_ema
    return [i for i in range(len(df)-1) if m.iloc[i]]

def v13_macro(df):
    """V13-D: RSI cross + price ABOVE 200 SMA (buy dips in uptrend only)"""
    rsi_was_below = (df['rsi_prev']<30)|(df['rsi_prev2']<30)|(df['rsi_prev3']<30)
    macro_up = df['Close'] > df['sma200']
    m = (df['rsi']>=30)&(df['rsi']<40)&rsi_was_below&(df['adx']<25)&macro_up
    return [i for i in range(len(df)-1) if m.iloc[i]]

def v13_vwap(df):
    """V13-E: RSI cross + price below VWAP (below fair institutional value)"""
    rsi_was_below = (df['rsi_prev']<30)|(df['rsi_prev2']<30)|(df['rsi_prev3']<30)
    below_vwap = df['Close'] < df['vwap']
    m = (df['rsi']>=30)&(df['rsi']<40)&rsi_was_below&(df['adx']<25)&below_vwap
    return [i for i in range(len(df)-1) if m.iloc[i]]

def v13_elite(df):
    """V13 ELITE: RSI cross + macro uptrend + vol exhaust + near 50 EMA"""
    rsi_was_below = (df['rsi_prev']<30)|(df['rsi_prev2']<30)|(df['rsi_prev3']<30)
    near_ema  = df['Close'] <= (df['ema50'] * 1.03)
    macro_up  = df['Close'] > (df['sma200'] * 0.95)   # within 5% of 200 SMA
    vol_dry   = df['volr'] < 0.90
    m = (df['rsi']>=30)&(df['rsi']<40)&rsi_was_below&(df['adx']<25)&near_ema&macro_up&vol_dry
    return [i for i in range(len(df)-1) if m.iloc[i]]

STRATEGIES = [
    ("V12 Current (RSI touch)",        v12_current),
    ("V13-A: RSI Cross only",          v13_rsi_cross),
    ("V13-B: RSI Cross + Vol Exhaust", v13_vol_exhaust),
    ("V13-C: RSI Cross + EMA50",       v13_ema50),
    ("V13-D: RSI Cross + 200 SMA",     v13_macro),
    ("V13-E: RSI Cross + VWAP",        v13_vwap),
    ("V13 ELITE (All combined)",       v13_elite),
]

if __name__ == "__main__":
    print("="*72)
    print("V13 VALIDATION BACKTEST | 1Y Hourly | 25 Assets | Stop 2ATR / Target 4ATR")
    print("="*72)

    agg = {s[0]: {'s':0,'w':0,'l':0} for s in STRATEGIES}

    for ticker in TICKERS:
        df = load(ticker)
        if df is None: continue
        df = indicators(df)
        for name, fn in STRATEGIES:
            r = backtest(df, fn)
            if r:
                agg[name]['s'] += r['s']
                agg[name]['w'] += r['w']
                agg[name]['l'] += r['l']

    print(f"\n{'STRATEGY':<35} {'SIG':>5} {'WIN%':>6} {'EXPECT':>8} {'vs V12':>8}")
    print("-"*72)

    v12_exp = None
    for name, _ in STRATEGIES:
        d = agg[name]
        t = d['w']+d['l']
        if t==0: print(f"{name:<35} {'0':>5}"); continue
        wr  = d['w']/t
        exp = round(wr*2.0-(1-wr), 3)
        if v12_exp is None: v12_exp = exp
        delta = f"+{exp-v12_exp:.3f}" if exp>v12_exp else f"{exp-v12_exp:.3f}"
        bar = "#"*int(exp*20) if exp>0 else ""
        print(f"{name:<35} {t:>5} {wr*100:>5.1f}% {exp:>8.3f} {delta:>8}  {bar}")

    print("="*72)
    print("Expectancy = (WR x 2.0) - (LR x 1.0). Higher is better.")
