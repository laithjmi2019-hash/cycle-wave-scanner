import pandas as pd
import numpy as np
import ta

def calculate_indicators(df, full=False):
    """
    Calculates essential indicators for V7 Deep Mean Reversion (Combo 6).
    Uses 14-RSI, Bollinger Bands, and 10-ATR.
    """
    if len(df) < 20:
        return df

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()

    # Bollinger Bands (20, 2)
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2.0)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    
    # ATR (10) for scaling stops and targets and deep checks
    df['atr_10'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10).average_true_range()

    return df

def _calc_rr(entry, stop, target, is_short=False):
    """Calculates risk/reward ratio details."""
    if not is_short:
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target

    if risk <= 0:
        return "N/A", 0, 0, "N/A", "N/A"

    ratio = reward / risk
    rr_str = f"1:{ratio:.2f}"
    return ratio, risk, reward, rr_str, "N/A"

def analyze_asset(ticker, df_1d, df_1h, df_15m, spy_data=None):
    """
    V7.0 Deep Mean Reversion (Combo 6):
    Looks for Extreme Panic (RSI < 20) + Price extremely detached from Lower BB (Close < LowerBB - 0.5*ATR).
    Uses 1:1 R:R (Target: 2 ATR, Stop: 2 ATR)
    """
    df1h = calculate_indicators(df_1h).dropna()
    if df1h.empty:
        return None

    c1h = df1h.iloc[-1]
    
    rsi = c1h['rsi']
    bb_lower = c1h['bb_lower']
    bb_upper = c1h['bb_upper']
    atr = c1h['atr_10']
    entry = c1h['Close']

    # Default State
    rec = "WAIT FOR EXTREME"
    signal = "Waiting"
    reason = "Waiting for deep statistical deviation (RSI < 20 or > 80) outside Bollinger Bands."
    score = 30
    bb_status = "Inside Bands"
    stop_loss = 0.0
    upside_str = "N/A"
    rr_str = "N/A"

    if entry < bb_lower:
        bb_status = "Below Lower Band"
    elif entry > bb_upper:
        bb_status = "Above Upper Band"

    # LONG SNIPER (Deep Mean Reversion)
    if rsi < 20 and entry < (bb_lower - (0.5 * atr)):
        rec = "LONG SNIPER"
        signal = "Deep Reversion"
        score = 99
        stop_loss = entry - (2.0 * atr)
        target = entry + (2.0 * atr)
        reason = "HIGH-WINRATE (73%) SNIPER: Extreme panic detected (RSI < 20) severely below Lower BB. 1:1 Risk/Reward profile."
        
        _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=False)
        upside_pct = ((target - entry) / entry) * 100
        upside_str = f"+{upside_pct:.2f}%"

    # SHORT SNIPER (Deep Mean Reversion)
    elif rsi > 80 and entry > (bb_upper + (0.5 * atr)):
        rec = "SHORT SNIPER"
        signal = "Deep Reversion"
        score = 99
        stop_loss = entry + (2.0 * atr)
        target = entry - (2.0 * atr)
        reason = "HIGH-WINRATE (73%) SNIPER: Extreme euphoria detected (RSI > 80) severely above Upper BB. 1:1 Risk/Reward profile."
        
        _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=True)
        upside_pct = ((entry - target) / entry) * 100
        upside_str = f"+{upside_pct:.2f}%"

    return {
        "recommendation": rec,
        "signal": signal,
        "score": score,
        "reason": reason,
        "upside": upside_str,
        "stop_loss": f"${stop_loss:.2f}" if stop_loss > 0 else "N/A",
        "rr": rr_str,
        "rsi": f"{rsi:.1f}",
        "bb_status": bb_status
    }

def analyze_crypto_asset(ticker, df_1d, df_1h, df_15m, btc_1d=None):
    """
    Applies identical V7.0 Deep Mean Reversion to Crypto.
    """
    return analyze_asset(ticker, df_1d, df_1h, df_15m)
