import pandas as pd
import numpy as np
import ta

def calculate_indicators(df, full=False):
    """
    Calculates essential indicators for V8 Hybrid Apex Engine.
    Uses 14-RSI, Bollinger Bands, 10-ATR, Volume SMA, and MACD.
    """
    if len(df) < 26:
        return df

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()

    # Bollinger Bands (20, 2)
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2.0)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()
    
    # ATR (10) for scaling stops and targets and deep checks
    df['atr_10'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10).average_true_range()
    
    # Volume SMA for Breakout Logic
    df['vol_sma_20'] = ta.trend.SMAIndicator(df['Volume'], window=20).sma_indicator()
    
    # MACD for Momentum Breakout Confirmation
    macd = ta.trend.MACD(df['Close'])
    df['macd_hist'] = macd.macd_diff()
    df['macd_hist_prev'] = df['macd_hist'].shift(1)

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
    V8.0 Hybrid Apex Engine:
    Strategy A (Sniper): Extreme Panic/Euphoria (RSI < 20 or > 80) outside BB. 1:1 RR.
    Strategy B (Momentum): Breakout of BB with 2x Volume + MACD flipping. 1:1 RR.
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
    vol = c1h['Volume']
    vol_sma = c1h['vol_sma_20']
    macd_h = c1h['macd_hist']
    macd_h_prev = c1h['macd_hist_prev']

    # Default State
    rec = "WAIT FOR EXTREME"
    signal = "Waiting"
    reason = "Scanning for Deep Reversion (Sniper) or Volume Breakout (Momentum)."
    score = 30
    bb_status = "Inside Bands"
    stop_loss = 0.0
    upside_str = "N/A"
    rr_str = "N/A"

    if entry < bb_lower:
        bb_status = "Below Lower Band"
    elif entry > bb_upper:
        bb_status = "Above Upper Band"

    # ====================================================
    # STRATEGY A: THE SNIPER (DEEP MEAN REVERSION)
    # ====================================================
    if rsi < 20 and entry < (bb_lower - (0.5 * atr)):
        rec = "LONG SNIPER"
        signal = "Deep Reversion"
        score = 99
        stop_loss = entry - (2.0 * atr)
        target = entry + (2.0 * atr)
        reason = "STRATEGY A (SNIPER): Extreme panic detected (RSI < 20) severely below Lower BB. 1:1 R:R profile."
        
        _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=False)
        upside_str = f"+{((target - entry) / entry) * 100:.2f}%"

    elif rsi > 80 and entry > (bb_upper + (0.5 * atr)):
        rec = "SHORT SNIPER"
        signal = "Deep Reversion"
        score = 99
        stop_loss = entry + (2.0 * atr)
        target = entry - (2.0 * atr)
        reason = "STRATEGY A (SNIPER): Extreme euphoria detected (RSI > 80) severely above Upper BB. 1:1 R:R profile."
        
        _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=True)
        upside_str = f"+{((entry - target) / entry) * 100:.2f}%"

    # ====================================================
    # STRATEGY B: MOMENTUM BREAKOUT
    # ====================================================
    elif entry > bb_upper and vol > (vol_sma * 2.0) and macd_h > 0 and macd_h_prev < 0:
        rec = "LONG MOMENTUM"
        signal = "Volume Breakout"
        score = 95
        stop_loss = entry - (2.0 * atr)
        target = entry + (2.0 * atr)
        reason = "STRATEGY B (MOMENTUM): Price broke Upper BB with >200% average volume & MACD flipped bullish. 1:1 R:R profile."
        
        _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=False)
        upside_str = f"+{((target - entry) / entry) * 100:.2f}%"
        
    elif entry < bb_lower and vol > (vol_sma * 2.0) and macd_h < 0 and macd_h_prev > 0:
        rec = "SHORT MOMENTUM"
        signal = "Volume Breakdown"
        score = 95
        stop_loss = entry + (2.0 * atr)
        target = entry - (2.0 * atr)
        reason = "STRATEGY B (MOMENTUM): Price broke Lower BB with >200% average volume & MACD flipped bearish. 1:1 R:R profile."
        
        _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=True)
        upside_str = f"+{((entry - target) / entry) * 100:.2f}%"

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
    Applies identical V8.0 Hybrid Engine to Crypto.
    """
    return analyze_asset(ticker, df_1d, df_1h, df_15m)
