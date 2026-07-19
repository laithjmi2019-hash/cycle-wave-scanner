import pandas as pd
import numpy as np
import ta

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate indicators, FVGs, and Candlestick patterns without lookahead bias."""
    df = df.copy()
    
    # RSI and StochRSI
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    stoch_rsi = ta.momentum.StochRSIIndicator(df['Close'], window=14, smooth1=3, smooth2=3)
    df['stoch_rsi_k'] = stoch_rsi.stochrsi_k() * 100
    df['stoch_rsi_d'] = stoch_rsi.stochrsi_d() * 100
    
    # Trend (EMA 50 and 200)
    df['ema_50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
    df['ema_200'] = ta.trend.EMAIndicator(df['Close'], window=200).ema_indicator()
    
    # 1. Fair Value Gap (FVG)
    # Bullish FVG formed at t: Low of t > High of t-2
    df['fvg_bull_gap_low'] = df['High'].shift(2)
    df['fvg_bull_gap_high'] = df['Low']
    df['is_bull_fvg'] = df['fvg_bull_gap_high'] > df['fvg_bull_gap_low']
    
    # Active FVG (forward fill the gaps for 5 periods) shifted by 1 so we check against PAST FVGs
    df['active_bull_fvg_top'] = df['fvg_bull_gap_high'].where(df['is_bull_fvg']).ffill(limit=5).shift(1)
    df['active_bull_fvg_bottom'] = df['fvg_bull_gap_low'].where(df['is_bull_fvg']).ffill(limit=5).shift(1)
    
    # Tapping FVG: current Low dipped into FVG, but Close didn't break entirely below it
    df['tapping_bull_fvg'] = (df['Low'] <= df['active_bull_fvg_top']) & (df['Close'] >= df['active_bull_fvg_bottom'])
    
    # 2. Candlestick Reversal Triggers
    df['body_size'] = abs(df['Close'] - df['Open'])
    df['total_range'] = df['High'] - df['Low']
    df['lower_wick'] = df[['Close', 'Open']].min(axis=1) - df['Low']
    
    # Pin Bar (Rejection / Sweep)
    df['is_pin_bar'] = (
        (df['lower_wick'] >= 2 * df['body_size']) &
        (df[['Close', 'Open']].max(axis=1) >= df['High'] - 0.33 * df['total_range']) &
        (df['total_range'] > 0)
    )
    
    # Institutional Engulfing
    prev_open = df['Open'].shift(1)
    prev_close = df['Close'].shift(1)
    vol_ma20 = df['Volume'].rolling(20).mean()
    
    df['is_engulfing'] = (
        (df['Close'] > df['Open']) & 
        (prev_open > prev_close) & 
        (df['Close'] >= prev_open) & 
        (df['Open'] <= prev_close) & 
        (df['Volume'] > vol_ma20)
    )
    
    return df

def detect_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
    """Detect bullish or bearish divergence strictly using historical data."""
    if len(df) < lookback + 1:
        return "None"
        
    recent = df.iloc[-lookback:]
    current_idx = df.index[-1]
    
    rsi_min_idx = recent['rsi'].idxmin()
    rsi_max_idx = recent['rsi'].idxmax()
    
    # Check Bullish Divergence
    if df['Low'].iloc[-1] <= recent['Low'].min() * 1.01:
        if rsi_min_idx != current_idx and df['rsi'].iloc[-1] > df.loc[rsi_min_idx, 'rsi']:
            return "Bullish"
            
    # Check Bearish Divergence
    if df['High'].iloc[-1] >= recent['High'].max() * 0.99:
        if rsi_max_idx != current_idx and df['rsi'].iloc[-1] < df.loc[rsi_max_idx, 'rsi']:
            return "Bearish"
            
    return "None"

def analyze_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame, spy_1d: pd.DataFrame) -> dict:
    df_1d = calculate_indicators(data_1d).dropna()
    df_1h = calculate_indicators(data_1h).dropna()
    
    if df_1d.empty or df_1h.empty:
        return {"ticker": ticker, "signal": "Avoid", "score": 0, "reason": "Insufficient Data"}
        
    curr_1d = df_1d.iloc[-1]
    curr_1h = df_1h.iloc[-1]
    
    div_1h = detect_divergence(df_1h)
    trend_1d = "UP" if curr_1d['ema_50'] > curr_1d['ema_200'] else "DOWN"
    
    spy_df = calculate_indicators(spy_1d).dropna()
    if not spy_df.empty:
        spy_curr = spy_df.iloc[-1]
        spy_trend = "UP" if spy_curr['ema_50'] > spy_curr['ema_200'] else "DOWN"
    else:
        spy_trend = "UP"
        
    # Liquidity / Price Action Triggers
    tapping_fvg = bool(curr_1h['tapping_bull_fvg'])
    pin_bar = bool(curr_1h['is_pin_bar'])
    engulfing = bool(curr_1h['is_engulfing'])
    pa_trigger = pin_bar or engulfing
    
    score = 50
    signal = "Avoid"
    reason = []
    
    # 3. Confluence Matrix (Institutional Good Entry)
    is_confluence_entry = (trend_1d == "UP") and (div_1h == "Bullish") and (tapping_fvg or pa_trigger)
    
    if is_confluence_entry:
        signal = "Good Entry"
        score = 95
        trigger_str = []
        if tapping_fvg: trigger_str.append("Tapping 1H FVG")
        if pin_bar: trigger_str.append("Pin Bar Rejection")
        if engulfing: trigger_str.append("Inst. Engulfing")
        reason.append(f"1D Trend UP + Bullish Divergence + {' + '.join(trigger_str)}")
    elif trend_1d == "UP":
        signal = "Trend Up"
        score = 70
        reason.append("Established Uptrend, but lacking full liquidity/divergence confluence.")
    else:
        signal = "Trend Down"
        score = 30
        reason.append("Established Downtrend. Avoid entries.")
        
    # Market Breadth Filter
    if spy_trend == "DOWN" and signal in ["Good Entry", "Trend Up"]:
        score -= 20
        reason.append("Market Breadth Penalty (SPY is DOWN).")
        if signal == "Good Entry":
            signal = "Avoid" # Demote signal due to bad market conditions
            reason.append("Downgraded from Good Entry due to Bearish SPY.")
            
    score = max(0, min(100, score))
    
    return {
        "ticker": ticker,
        "signal": signal,
        "score": score,
        "reason": " ".join(reason),
        "trend_1d": trend_1d,
        "div_1h": div_1h,
        "fvg_tap": tapping_fvg,
        "pa_trigger": pa_trigger,
        "current_price": round(curr_1h['Close'], 2)
    }
