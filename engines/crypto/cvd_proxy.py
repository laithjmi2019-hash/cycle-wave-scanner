import pandas as pd
import numpy as np

def cvd_proxy(df: pd.DataFrame) -> pd.Series:
    """
    Approximate CVD (Cumulative Volume Delta) from OHLCV data.
    TRUE CVD requires tick data. This is an approximation using:
    Bar delta = Volume * ((Close - Open) / (High - Low + 0.0001))
    """
    if df.empty or 'Volume' not in df.columns:
        return pd.Series(dtype=float)
        
    close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
    open_p = df['Open'].squeeze() if isinstance(df['Open'], pd.DataFrame) else df['Open']
    high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
    low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
    vol = df['Volume'].squeeze() if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
    
    delta = vol * ((close - open_p) / (high - low + 0.0001))
    return delta.cumsum()

def cvd_analysis(df: pd.DataFrame) -> dict:
    res = {
        "cvd_direction": "NEUTRAL",
        "cvd_slope": "FLAT",
        "price_cvd_divergence": False,
        "divergence_direction": "NONE",
        "cvd_score": 0.0
    }
    
    if df.empty or len(df) < 10:
        return res
        
    cvd = cvd_proxy(df)
    
    if cvd.iloc[-1] > cvd.iloc[0]:
        res["cvd_direction"] = "POSITIVE"
    elif cvd.iloc[-1] < cvd.iloc[0]:
        res["cvd_direction"] = "NEGATIVE"
        
    recent_5 = cvd.iloc[-5:]
    prior_5 = cvd.iloc[-10:-5]
    recent_slope = recent_5.iloc[-1] - recent_5.iloc[0]
    prior_slope = prior_5.iloc[-1] - prior_5.iloc[0]
    
    if recent_slope > prior_slope and recent_slope > 0:
        res["cvd_slope"] = "RISING"
    elif recent_slope < prior_slope and recent_slope < 0:
        res["cvd_slope"] = "FALLING"
        
    # Divergence
    recent_price_5 = df['Close'].iloc[-5:]
    prior_price_5 = df['Close'].iloc[-10:-5]
    price_slope = recent_price_5.iloc[-1] - recent_price_5.iloc[0]
    
    if price_slope > 0 and recent_slope < 0:
        res["price_cvd_divergence"] = True
        res["divergence_direction"] = "BEARISH"
    elif price_slope < 0 and recent_slope > 0:
        res["price_cvd_divergence"] = True
        res["divergence_direction"] = "BULLISH"
        
    # Score 0-7
    score = 3.5
    if res["cvd_direction"] == "POSITIVE":
        score += 1.5
    elif res["cvd_direction"] == "NEGATIVE":
        score -= 1.5
        
    if res["cvd_slope"] == "RISING":
        score += 2.0
    elif res["cvd_slope"] == "FALLING":
        score -= 2.0
        
    if res["divergence_direction"] == "BULLISH":
        score += 1.0
    elif res["divergence_direction"] == "BEARISH":
        score -= 1.0
        
    res["cvd_score"] = max(0, min(7, score))
    return res
