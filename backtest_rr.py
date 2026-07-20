"""
DEEP HOLD-PERIOD + RISK-REWARD BACKTEST
Tests S3 and S4 (top performers) across different hold durations
and with proper R:R and stop-loss discipline.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import warnings
warnings.filterwarnings("ignore")

SAMPLE_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "JPM", "V",
    "XOM", "CVX", "BA", "NFLX", "AMD", "INTC", "GOOGL", "BAC",
    "COST", "WMT", "DIS", "SBUX"
]

def fetch_and_prepare(ticker):
    t = yf.Ticker(ticker)
    df = t.history(period="1y", interval="1h", prepost=False)
    if len(df) < 200:
        return None
    c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']
    df['rsi']    = ta.momentum.RSIIndicator(c, 14).rsi()
    bb = ta.volatility.BollingerBands(c, 20, 2)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    df['atr']    = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range()
    df['adx']    = ta.trend.ADXIndicator(h, l, c, 14).adx()
    df['vol_sma']= v.rolling(20).mean()
    df['vol_ratio'] = v / df['vol_sma']
    rolling_mean = c.rolling(20).mean()
    rolling_std  = c.rolling(20).std()
    df['zscore'] = (c - rolling_mean) / rolling_std
    df['vwap']   = (c * v).rolling(24).sum() / v.rolling(24).sum()
    df['sma200h']= c.rolling(200).mean()
    return df.dropna()

def backtest_rr(df, signal_fn, atr_stop_mult=2.0, atr_target_mult=3.0):
    """
    Realistic R:R backtest with ATR-based stop loss and target.
    Returns win rate, R:R achieved, expectancy.
    """
    signals = signal_fn(df)
    wins, losses, skipped = 0, 0, 0

    for idx in signals:
        entry_idx = idx + 1
        if entry_idx >= len(df) - 1:
            continue

        entry  = df['Close'].iloc[entry_idx]
        atr    = df['atr'].iloc[entry_idx]
        stop   = entry - (atr_stop_mult * atr)
        target = entry + (atr_target_mult * atr)

        outcome = None
        for j in range(entry_idx + 1, min(entry_idx + 48, len(df))):
            low_j  = df['Low'].iloc[j]
            high_j = df['High'].iloc[j]
            if low_j <= stop:
                outcome = 'loss'
                break
            if high_j >= target:
                outcome = 'win'
                break

        if outcome == 'win':
            wins += 1
        elif outcome == 'loss':
            losses += 1
        else:
            skipped += 1  # trade still open at 48 bars

    total = wins + losses
    if total == 0:
        return None
    wr = wins / total
    # Expectancy = (WR * reward) - (LR * risk) per unit risk
    # With R:R of target_mult / stop_mult
    rr_ratio = atr_target_mult / atr_stop_mult
    expectancy = (wr * rr_ratio) - ((1 - wr) * 1.0)
    return {
        "wins": wins, "losses": losses, "skipped": skipped,
        "win_rate": round(wr * 100, 1),
        "rr_set": f"1:{rr_ratio}",
        "expectancy": round(expectancy, 3),
        "edge": "POSITIVE" if expectancy > 0 else "NEGATIVE"
    }

# Top strategies from first backtest
def s3_rsi_bb_adx(df):
    mask = (df['rsi'] < 30) & (df['Close'] <= df['bb_lower']) & (df['adx'] < 25)
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def s4_zscore_adx_vol(df):
    mask = (df['zscore'] < -2.0) & (df['adx'] < 25) & (df['vol_ratio'] > 1.5)
    return [i for i in range(len(df)-1) if mask.iloc[i]]

# NEW ELITE STRATEGIES TO TEST
def sA_triple_confirm(df):
    """RSI<30 + Z<-1.5 + ADX<25 + Below VWAP + Vol>1.3x — TRIPLE CONFIRMATION"""
    mask = (
        (df['rsi'] < 30) &
        (df['zscore'] < -1.5) &
        (df['adx'] < 25) &
        (df['Close'] < df['vwap']) &
        (df['vol_ratio'] > 1.3)
    )
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def sB_trend_aligned_dip(df):
    """Price above 200H SMA (uptrend) + RSI<35 + Z<-1.5 — Buy the dip in uptrend"""
    mask = (
        (df['Close'] > df['sma200h']) &
        (df['rsi'] < 35) &
        (df['zscore'] < -1.5) &
        (df['adx'] < 30)
    )
    return [i for i in range(len(df)-1) if mask.iloc[i]]

def sC_volatility_squeeze_breakout(df):
    """
    BB Width compressed (squeeze) + Volume explosion + MACD cross.
    Volatility squeeze then explosion = institutional accumulation release.
    """
    macd = ta.trend.MACD(df['Close'])
    df['macd_h'] = macd.macd_diff()
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / ((df['bb_upper'] + df['bb_lower']) / 2)
    df['bb_width_sma'] = df['bb_width'].rolling(20).mean()

    mask = (
        (df['bb_width'] < df['bb_width_sma'] * 0.7) &  # BB squeezed 30% below avg
        (df['vol_ratio'] > 2.0) &                       # Volume explosion
        (df['macd_h'] > 0)                              # Positive MACD
    )
    return [i for i in range(len(df)-1) if mask.iloc[i]]

STRATEGIES = [
    ("S3: RSI+BB+ADX<25 (Current Best)",  s3_rsi_bb_adx),
    ("S4: Z-Score+ADX+Volume",            s4_zscore_adx_vol),
    ("SA: Triple Confirm",                sA_triple_confirm),
    ("SB: Trend-Aligned Dip (BEST)",     sB_trend_aligned_dip),
    ("SC: Volatility Squeeze Breakout",   sC_volatility_squeeze_breakout),
]

RR_CONFIGS = [
    (1.5, 2.0, "Stop 1.5 ATR / Target 2 ATR (1:1.33)"),
    (2.0, 3.0, "Stop 2 ATR / Target 3 ATR (1:1.5) "),
    (2.0, 4.0, "Stop 2 ATR / Target 4 ATR (1:2)   "),
]

if __name__ == "__main__":
    print("="*75)
    print("DEEP R:R BACKTEST — ATR-Based Stop/Target | 48-Bar Max Hold")
    print("="*75)

    for stop_m, tgt_m, rr_label in RR_CONFIGS:
        print(f"\n  Risk Config: {rr_label}")
        print(f"  {'STRATEGY':<40} {'SIGNALS':>7} {'WIN%':>6} {'EXPECT':>8} {'EDGE':>10}")
        print("  " + "-"*68)

        all_res = {}
        for name, fn in STRATEGIES:
            total_w, total_l, total_sk = 0, 0, 0
            for ticker in SAMPLE_TICKERS:
                df = fetch_and_prepare(ticker)
                if df is None: continue
                r = backtest_rr(df, fn, stop_m, tgt_m)
                if r:
                    total_w  += r['wins']
                    total_l  += r['losses']
                    total_sk += r['skipped']

            total = total_w + total_l
            if total == 0:
                print(f"  {name:<40} {'0':>7} {'N/A':>6} {'N/A':>8} {'N/A':>10}")
                continue
            wr = total_w / total
            rr_ratio = tgt_m / stop_m
            exp = round((wr * rr_ratio) - ((1 - wr) * 1.0), 3)
            edge = "[+] POSITIVE" if exp > 0 else "[-] NEGATIVE"
            print(f"  {name:<40} {total:>7} {wr*100:>5.1f}% {exp:>8.3f} {edge:>10}")

    print("\n" + "="*75)
    print("Expectancy > 0 = profitable strategy over large sample sizes.")
    print("Expectancy formula: (WinRate × Reward) - (LossRate × Risk)")
    print("="*75)
