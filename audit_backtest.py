"""
V12 SYSTEM AUDIT BACKTEST
Compares current V12 vs proposed institutional improvements.
Tests on 1-year hourly data across 25 major assets.
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
    if len(df) < 200: return None
    return df

def indicators(df):
    c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']
    df['rsi']    = ta.momentum.RSIIndicator(c, 14).rsi()
    bb           = ta.volatility.BollingerBands(c, 20, 2)
    df['bb_l']   = bb.bollinger_lband()
    df['bb_u']   = bb.bollinger_hband()
    df['adx']    = ta.trend.ADXIndicator(h, l, c, 14).adx()
    df['atr']    = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range()
    df['vol_sma']= v.rolling(20).mean()
    df['volr']   = v / df['vol_sma']
    rm           = c.rolling(20).mean()
    rs           = c.rolling(20).std()
    df['z']      = (c - rm) / rs
    # Money Flow Index
    df['mfi']    = ta.volume.MFIIndicator(h, l, c, v, 14).money_flow_index()
    # OBV
    df['obv']    = ta.volume.OnBalanceVolumeIndicator(c, v).on_balance_volume()
    df['obv_sma']= df['obv'].rolling(20).mean()
    # OBV divergence: price makes lower low but OBV doesn't
    df['price_ll']= c < c.shift(5)
    df['obv_hl']  = df['obv'] > df['obv'].shift(5)
    df['bull_div']= df['price_ll'] & df['obv_hl']
    # Williams %R
    df['willr']  = ta.momentum.WilliamsRIndicator(h, l, c, 14).williams_r()
    # Chaikin Money Flow
    df['cmf']    = ta.volume.ChaikinMoneyFlowIndicator(h, l, c, v, 20).chaikin_money_flow()
    # VWAP simple approximation
    df['vwap']   = (c * v).rolling(24).sum() / v.rolling(24).sum()
    return df.dropna()

def backtest(df, signal_fn, stop_atr=2.0, target_atr=4.0):
    signals = signal_fn(df)
    wins = losses = skipped = 0
    for i in signals:
        ei = i + 1
        if ei >= len(df): continue
        entry  = df['Close'].iloc[ei]
        atr    = df['atr'].iloc[ei]
        stop   = entry - stop_atr * atr
        target = entry + target_atr * atr
        outcome = None
        for j in range(ei+1, min(ei+48, len(df))):
            if df['Low'].iloc[j]  <= stop:  outcome='loss'; break
            if df['High'].iloc[j] >= target: outcome='win';  break
        if outcome=='win':   wins+=1
        elif outcome=='loss': losses+=1
        else: skipped+=1
    total = wins+losses
    if total == 0: return None
    wr  = wins/total
    exp = wr*(target_atr/stop_atr) - (1-wr)
    return {'signals':total, 'wins':wins, 'losses':losses,
            'wr':round(wr*100,1), 'exp':round(exp,3)}

# ── STRATEGY DEFINITIONS ─────────────────────────────────────────────────

def s_v11(df):
    """V11: RSI<30 + BB Lower + ADX<25"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_v12(df):
    """V12: RSI<30 + BB + ADX<25 + Z<-1.5"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_v12_mfi(df):
    """V12 + MFI<30 (volume-weighted oversold confirmation)"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)&(df['mfi']<30)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_v12_div(df):
    """V12 + OBV Bullish Divergence (institutional accumulation)"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)&(df['bull_div'])
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_v12_cmf(df):
    """V12 + CMF > -0.1 (money flow not strongly negative = bounce likely)"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)&(df['cmf']>-0.1)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_v12_willr(df):
    """V12 + Williams %R < -80 (triple oversold confirmation)"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)&(df['willr']<-80)
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_v12_vwap(df):
    """V12 + Price below VWAP (below fair value)"""
    m = (df['rsi']<30)&(df['Close']<=df['bb_l'])&(df['adx']<25)&(df['z']<-1.5)&(df['Close']<df['vwap'])
    return [i for i in range(len(df)-1) if m.iloc[i]]

def s_elite(df):
    """ELITE: V12 + MFI<35 + OBV divergence OR CMF > -0.1 + Below VWAP"""
    m = (
        (df['rsi']<30) & (df['Close']<=df['bb_l']) & (df['adx']<25) &
        (df['z']<-1.5) & (df['mfi']<35) &
        (df['Close']<df['vwap']) &
        ((df['bull_div']) | (df['cmf']>-0.1))
    )
    return [i for i in range(len(df)-1) if m.iloc[i]]

STRATEGIES = [
    ("V11 (current baseline)",       s_v11),
    ("V12 (deployed)",               s_v12),
    ("V12 + MFI<30",                 s_v12_mfi),
    ("V12 + OBV Divergence",         s_v12_div),
    ("V12 + CMF>-0.1",               s_v12_cmf),
    ("V12 + Williams %R<-80",        s_v12_willr),
    ("V12 + Below VWAP",             s_v12_vwap),
    ("ELITE (All filters combined)", s_elite),
]

if __name__ == "__main__":
    print("="*72)
    print("V12 SYSTEM AUDIT — Comparative Backtest | 1Y Hourly | 25 Assets")
    print("Stop: 2 ATR | Target: 4 ATR (1:2 R:R)")
    print("="*72)

    agg = {s[0]: {'signals':0,'wins':0,'losses':0} for s in STRATEGIES}

    for ticker in TICKERS:
        df = load(ticker)
        if df is None: print(f"  {ticker}: skip"); continue
        df = indicators(df)
        print(f"  {ticker}: {len(df)} bars", end="")
        for name, fn in STRATEGIES:
            r = backtest(df, fn)
            if r:
                agg[name]['signals'] += r['signals']
                agg[name]['wins']    += r['wins']
                agg[name]['losses']  += r['losses']
        print()

    print()
    print(f"{'STRATEGY':<32} {'SIG':>5} {'WIN%':>6} {'EXPECT':>8} {'QUALITY'}")
    print("-"*72)
    for name, _ in STRATEGIES:
        d = agg[name]
        t = d['wins']+d['losses']
        if t == 0:
            print(f"{name:<32} {'0':>5} {'N/A':>6} {'N/A':>8}")
            continue
        wr  = d['wins']/t
        exp = round(wr*2.0 - (1-wr), 3)  # 1:2 R:R
        stars = "ELITE" if exp>0.6 else ("GOOD" if exp>0.4 else ("OK" if exp>0.2 else "WEAK"))
        print(f"{name:<32} {t:>5} {wr*100:>5.1f}% {exp:>8.3f}  {stars}")
    print("="*72)
    print("Expectancy = (WinRate x 2) - (LossRate x 1)  [for 1:2 R:R]")
    print("Positive = profitable. Higher = better edge per trade.")
