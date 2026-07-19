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
    
    # Fast Trend (EMA 9 and 21) + Macro (EMA 50 and 200)
    df['ema_9'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
    df['ema_50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
    df['ema_200'] = ta.trend.EMAIndicator(df['Close'], window=200).ema_indicator()
    
    # ATR for Range Expansion
    df['atr_10'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10).average_true_range()
    
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
    
    # Institutional Engulfing (Original with Volume)
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
    
    # Institutional Engulfing (Price Action / Range Expansion for Crypto MTF)
    df['is_engulfing_pa'] = (
        (df['Close'] > df['Open']) & 
        (prev_open > prev_close) & 
        (df['Close'] >= prev_open) & 
        (df['Open'] <= prev_close) & 
        (df['body_size'] > 1.5 * df['atr_10'].shift(1))
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

def analyze_crypto_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame, data_15m: pd.DataFrame, btc_1d: pd.DataFrame) -> dict:
    df_1d = calculate_indicators(data_1d).dropna()
    df_1h = calculate_indicators(data_1h).dropna()
    df_15m = calculate_indicators(data_15m).dropna()
    
    if df_1d.empty or df_1h.empty or df_15m.empty:
        return {"ticker": ticker, "signal": "Avoid", "score": 0, "reason": "Insufficient Data"}
        
    curr_1d = df_1d.iloc[-1]
    curr_1h = df_1h.iloc[-1]
    curr_15m = df_15m.iloc[-1]
    
    div_1h = detect_divergence(df_1h)
    
    # Fast 1D Trend for Crypto (EMA 9 > 21)
    trend_1d = "UP" if curr_1d['ema_9'] > curr_1d['ema_21'] else "DOWN"
    
    btc_df = calculate_indicators(btc_1d).dropna()
    if not btc_df.empty:
        btc_curr = btc_df.iloc[-1]
        btc_trend = "UP" if btc_curr['ema_9'] > btc_curr['ema_21'] else "DOWN"
    else:
        btc_trend = "UP"
        
    # Liquidity Tap from 1H
    tapping_fvg_1h = bool(curr_1h['tapping_bull_fvg'])
    
    # Trigger from 15m (Sniper Execution)
    pin_bar_15m = bool(curr_15m['is_pin_bar'])
    engulfing_15m = bool(curr_15m['is_engulfing_pa'])
    trigger_15m = pin_bar_15m or engulfing_15m
    
    score = 50
    signal = "Avoid"
    reason = []
    
    # MTF Confluence Matrix
    is_setup_ready = (div_1h == "Bullish") or tapping_fvg_1h
    
    if trend_1d == "UP" and is_setup_ready and trigger_15m:
        signal = "Good Entry"
        score = 95
        trigger_str = []
        if pin_bar_15m: trigger_str.append("15m Pin Bar")
        if engulfing_15m: trigger_str.append("15m MTF Engulfing")
        setup_str = []
        if div_1h == "Bullish": setup_str.append("1H Bullish Div")
        if tapping_fvg_1h: setup_str.append("1H FVG Tap")
        
        reason.append(f"MTF Confluence: 1D Fast Uptrend + {' & '.join(setup_str)} + Sniper {' + '.join(trigger_str)}.")
    elif trend_1d == "UP":
        signal = "Trend Up"
        score = 70
        reason.append("1D Fast Uptrend, but awaiting 1H setup or 15m execution trigger.")
    else:
        signal = "Trend Down"
        score = 30
        reason.append("1D Fast Downtrend. Avoid.")
        
    # Bitcoin Macro Filter
    if btc_trend == "DOWN" and signal in ["Good Entry", "Trend Up"]:
        score -= 25
        reason.append("Bitcoin Macro Penalty (BTC 1D is DOWN).")
        if signal == "Good Entry":
            signal = "Avoid" # Demote due to bad macro
            reason.append("Setup invalidated by BTC Downtrend.")
            
    score = max(0, min(100, score))
    
    return {
        "ticker": ticker,
        "signal": signal,
        "score": score,
        "reason": " ".join(reason),
        "trend_1d": trend_1d,
        "div_1h": div_1h,
        "fvg_tap": tapping_fvg_1h,
        "pa_trigger": trigger_15m,
        "current_price": round(curr_15m['Close'], 4)
    }
