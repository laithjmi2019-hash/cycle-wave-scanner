import pandas as pd
import numpy as np
import ta
import yfinance as yf

# TOXIC KEYWORDS for fundamental filtering
TOXIC_KEYWORDS = [
    "bankruptcy", "scandal", "fraud", "lawsuit", "investigation", 
    "delisted", "misses earnings", "subpoena", "criminal", "sec probe", "sued"
]

def check_toxic_news(ticker):
    """
    Pulls the latest news from Yahoo Finance.
    Returns True if any toxic keywords are found in the titles, otherwise False.
    """
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return False
            
        for item in news[:5]: # check latest 5 headlines
            title = ""
            # Handle new yfinance dict structure
            if 'content' in item and 'title' in item['content']:
                title = item['content']['title'].lower()
            elif 'title' in item:
                title = item['title'].lower()
                
            for word in TOXIC_KEYWORDS:
                if word in title:
                    return True # Toxic!
    except Exception:
        pass
    
    return False

def calculate_indicators(df, full=False):
    """
    Calculates essential indicators for V10 Apex Engine.
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
    
    # ATR (10)
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
    V10.0 Apex Engine:
    Includes Multi-Timeframe Alignment (Daily 200 SMA) and NLP News Filtering.
    """
    df1h = calculate_indicators(df_1h).dropna()
    if df1h.empty:
        return None

    # Calculate MTF Daily 200 SMA
    daily_200_sma = None
    if df_1d is not None and len(df_1d) >= 200:
        df_1d['sma_200'] = ta.trend.SMAIndicator(df_1d['Close'], window=200).sma_indicator()
        daily_200_sma = df_1d['sma_200'].iloc[-1]

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
    if rsi < 30 and entry <= bb_lower:
        if daily_200_sma and entry < daily_200_sma:
            reason = "FILTERED (MTF): Price is below Daily 200 SMA. Refusing to catch falling knife."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected (bankruptcy, fraud, etc). Blocking trade."
        else:
            rec = "LONG SNIPER"
            signal = "Deep Reversion"
            score = 99
            stop_loss = entry - (2.0 * atr)
            target = entry + (2.0 * atr)
            reason = "STRATEGY A (SNIPER): High panic (RSI < 30) in a macro uptrend (Price > 200 SMA)."
            _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=False)
            upside_str = f"+{((target - entry) / entry) * 100:.2f}%"

    elif rsi > 70 and entry >= bb_upper:
        # For SHORT: we SHORT when the stock is overbought.
        # We BLOCK the short only if the macro trend is strongly bearish (price far below 200 SMA)
        # We ALLOW shorts when price is above or near 200 SMA (overbought in any trend = good short)
        if daily_200_sma and entry < (daily_200_sma * 0.85):
            reason = "FILTERED (MTF): Price is massively below 200 SMA - already in freefall, too risky to short."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec = "SHORT SNIPER"
            signal = "Deep Reversion"
            score = 99
            stop_loss = entry + (2.0 * atr)
            target = entry - (2.0 * atr)
            reason = "STRATEGY A (SNIPER): High euphoria (RSI > 70) - overbought reversal setup."
            _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=True)
            upside_str = f"+{((entry - target) / entry) * 100:.2f}%"

    # ====================================================
    # STRATEGY B: MOMENTUM BREAKOUT
    # ====================================================
    elif entry > bb_upper and vol > (vol_sma * 1.5) and macd_h > 0 and macd_h_prev <= 0:
        if daily_200_sma and entry < daily_200_sma:
            reason = "FILTERED (MTF): Price is below Daily 200 SMA. Ignoring dead-cat bounce."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec = "LONG MOMENTUM"
            signal = "Volume Breakout"
            score = 95
            stop_loss = entry - (2.0 * atr)
            target = entry + (2.0 * atr)
            reason = "STRATEGY B (MOMENTUM): Volume breakout in a macro uptrend."
            _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=False)
            upside_str = f"+{((target - entry) / entry) * 100:.2f}%"
        
    elif entry < bb_lower and vol > (vol_sma * 1.5) and macd_h < 0 and macd_h_prev >= 0:
        if check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec = "SHORT MOMENTUM"
            signal = "Volume Breakdown"
            score = 95
            stop_loss = entry + (2.0 * atr)
            target = entry - (2.0 * atr)
            reason = "STRATEGY B (MOMENTUM): Volume breakdown confirmed with high volume."
            _, _, _, rr_str, _ = _calc_rr(entry, stop_loss, target, is_short=True)
            upside_str = f"+{((entry - target) / entry) * 100:.2f}%"

    return {
        "ticker": ticker,
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
    Applies identical V10.0 Apex Engine to Crypto.
    """
    return analyze_asset(ticker, df_1d, df_1h, df_15m)
