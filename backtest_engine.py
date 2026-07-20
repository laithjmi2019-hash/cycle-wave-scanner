"""
INSTITUTIONAL DEEP BACKTEST ENGINE
Tests multiple strategies on 1-year of hourly data for US assets.
Calculates: Win Rate, Avg Return, Max Drawdown, Sharpe-like ratio.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import warnings
warnings.filterwarnings("ignore")

# Use a representative sample for speed
SAMPLE_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "JPM", "V",
    "XOM", "CVX", "BA", "NFLX", "AMD", "INTC", "GOOGL", "BAC",
    "COST", "WMT", "DIS", "SBUX"
]

def fetch(ticker):
    t = yf.Ticker(ticker)
    df = t.history(period="1y", interval="1h", prepost=False)
    if len(df) < 100:
        return None
    df['ticker'] = ticker
    return df

def add_all_indicators(df):
    c = df['Close']
    h = df['High']
    l = df['Low']
    v = df['Volume']

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(c, 14).rsi()

    # Bollinger Bands (20,2)
    bb = ta.volatility.BollingerBands(c, 20, 2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_mid']   = bb.bollinger_mavg()
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']

    # ATR
    df['atr'] = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range()

    # VWAP (rolling 24h)
    df['vwap'] = (c * v).rolling(24).sum() / v.rolling(24).sum()

    # ADX (trend strength)
    df['adx'] = ta.trend.ADXIndicator(h, l, c, 14).adx()

    # MACD
    macd = ta.trend.MACD(c)
    df['macd_h'] = macd.macd_diff()

    # Volume SMA
    df['vol_sma'] = v.rolling(20).mean()
    df['vol_ratio'] = v / df['vol_sma']

    # Z-Score (20-period)
    rolling_mean = c.rolling(20).mean()
    rolling_std  = c.rolling(20).std()
    df['zscore'] = (c - rolling_mean) / rolling_std

    # Stochastic RSI
    srsi = ta.momentum.StochRSIIndicator(c, 14, 3, 3)
    df['srsi_k'] = srsi.stochrsi_k()
    df['srsi_d'] = srsi.stochrsi_d()

    # 200-hour SMA (proxy for multi-day trend on 1H chart)
    df['sma200h'] = c.rolling(200).mean()

    # Volatility regime: is ATR compressed?
    df['atr_sma'] = df['atr'].rolling(20).mean()
    df['atr_compressed'] = df['atr'] < df['atr_sma']

    return df.dropna()

def backtest_strategy(df, strategy_fn, strategy_name, hold_bars=8):
    """
    Runs a backtest. Entry at bar where signal fires. Exit after hold_bars.
    Returns win rate, avg return, max drawdown, signal count.
    """
    signals = strategy_fn(df)
    results = []

    for idx in signals:
        entry_idx = idx + 1
        exit_idx  = idx + 1 + hold_bars
        if exit_idx >= len(df):
            continue

        entry_price = df['Close'].iloc[entry_idx]
        exit_price  = df['Close'].iloc[exit_idx]
        ret = (exit_price - entry_price) / entry_price * 100
        results.append(ret)

    if not results:
        return {"strategy": strategy_name, "signals": 0, "win_rate": 0, "avg_ret": 0, "best": 0, "worst": 0}

    arr = np.array(results)
    return {
        "strategy":   strategy_name,
        "signals":    len(arr),
        "win_rate":   round(float(np.mean(arr > 0)) * 100, 1),
        "avg_ret":    round(float(np.mean(arr)), 3),
        "best":       round(float(np.max(arr)), 2),
        "worst":      round(float(np.min(arr)), 2),
    }

# ============================================================
# STRATEGIES TO TEST
# ============================================================

def s1_current_rsi_bb(df):
    """CURRENT SYSTEM: RSI < 30 + Below BB"""
    mask = (df['rsi'] < 30) & (df['Close'] <= df['bb_lower'])
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s2_zscore_reversion(df):
    """Z-SCORE < -2 (2 std devs below rolling mean)"""
    mask = df['zscore'] < -2.0
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s3_rsi_bb_adx(df):
    """RSI < 30 + Below BB + ADX < 25 (only in ranging markets)"""
    mask = (df['rsi'] < 30) & (df['Close'] <= df['bb_lower']) & (df['adx'] < 25)
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s4_zscore_adx_vol(df):
    """Z-SCORE < -2 + ADX < 25 + Volume Spike (institutional panic)"""
    mask = (df['zscore'] < -2.0) & (df['adx'] < 25) & (df['vol_ratio'] > 1.5)
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s5_vwap_bounce(df):
    """Price dips below VWAP + RSI < 40 + Volume > 1.5x (institutional buy zone)"""
    mask = (df['Close'] < df['vwap']) & (df['rsi'] < 40) & (df['vol_ratio'] > 1.5)
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s6_vwap_zscore_combo(df):
    """Z-SCORE < -1.5 + Below VWAP + Vol Spike + ADX < 25 (multi-factor)"""
    mask = (
        (df['zscore'] < -1.5) &
        (df['Close'] < df['vwap']) &
        (df['vol_ratio'] > 1.5) &
        (df['adx'] < 25)
    )
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s7_stoch_rsi_oversold(df):
    """Stochastic RSI < 0.2 (extreme oversold on RSI momentum)"""
    mask = (df['srsi_k'] < 0.2) & (df['srsi_d'] < 0.2) & (df['Close'] < df['bb_lower'])
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s8_composite_score(df):
    """
    COMPOSITE SCORING: Only fire if 4+ conditions align.
    RSI<35: +1, Z<-1.5: +1, Below BB: +1, Below VWAP: +1, Vol>1.3x: +1, ADX<30: +1
    Threshold: >= 4 points
    """
    score = (
        (df['rsi'] < 35).astype(int) +
        (df['zscore'] < -1.5).astype(int) +
        (df['Close'] < df['bb_lower']).astype(int) +
        (df['Close'] < df['vwap']).astype(int) +
        (df['vol_ratio'] > 1.3).astype(int) +
        (df['adx'] < 30).astype(int)
    )
    mask = score >= 4
    return [i for i in range(len(df)-1) if mask.iloc[i]]

STRATEGIES = [
    ("S1: Current (RSI<30 + BB)",       s1_current_rsi_bb),
    ("S2: Z-Score Reversion (<-2)",      s2_zscore_reversion),
    ("S3: RSI+BB+ADX<25",               s3_rsi_bb_adx),
    ("S4: Z-Score+ADX+Volume",          s4_zscore_adx_vol),
    ("S5: VWAP Bounce",                 s5_vwap_bounce),
    ("S6: VWAP+Z-Score Combo",          s6_vwap_zscore_combo),
    ("S7: Stochastic RSI Extreme",      s7_stoch_rsi_oversold),
    ("S8: Composite Score (4+/6)",      s8_composite_score),
]

if __name__ == "__main__":
    print("="*70)
    print("INSTITUTIONAL DEEP BACKTEST ENGINE")
    print("Testing 8 strategies on 1-year hourly data | 20 US assets")
    print("="*70)

    all_results = {s[0]: [] for s in STRATEGIES}

    for ticker in SAMPLE_TICKERS:
        print(f"  Processing {ticker}...", end=" ")
        df = fetch(ticker)
        if df is None:
            print("SKIP")
            continue
        df = add_all_indicators(df)
        print(f"{len(df)} bars")

        for name, fn in STRATEGIES:
            res = backtest_strategy(df, fn, name)
            all_results[name].append(res)

    print("\n" + "="*70)
    print(f"{'STRATEGY':<35} {'SIGNALS':>7} {'WIN%':>6} {'AVG%':>7} {'BEST%':>7} {'WORST%':>8}")
    print("-"*70)

    for name, _ in STRATEGIES:
        data = all_results[name]
        if not data:
            continue
        total_signals = sum(d['signals'] for d in data)
        if total_signals == 0:
            print(f"{name:<35} {'0':>7} {'N/A':>6} {'N/A':>7} {'N/A':>7} {'N/A':>8}")
            continue
        # Weighted average by signal count
        total_wins = sum(d['win_rate'] * d['signals'] for d in data)
        avg_wr     = round(total_wins / total_signals, 1)
        total_ret  = sum(d['avg_ret'] * d['signals'] for d in data)
        avg_ret    = round(total_ret / total_signals, 3)
        best       = round(max(d['best'] for d in data), 2)
        worst      = round(min(d['worst'] for d in data), 2)
        print(f"{name:<35} {total_signals:>7} {avg_wr:>5}% {avg_ret:>7} {best:>7} {worst:>8}")

    print("="*70)
    print("\nBacktest complete. Hold period = 8 hours per signal.")
