import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def calc_rvol(df_1h: pd.DataFrame) -> float:
    if df_1h is None or df_1h.empty or 'Volume' not in df_1h.columns:
        return 1.0
        
    try:
        current_idx = df_1h.index[-1]
        current_vol = df_1h['Volume'].iloc[-1]
        if not isinstance(current_idx, pd.Timestamp):
            return 1.0
            
        hour = current_idx.hour
        minute = current_idx.minute
        
        recent_df = df_1h.iloc[:-1].last('14D')
        if recent_df.empty: return 1.0
        
        same_time = recent_df[(recent_df.index.hour == hour) & (recent_df.index.minute == minute)]
        if len(same_time) == 0:
            return 1.0
            
        avg_vol = same_time['Volume'].mean()
        if avg_vol == 0: return 1.0
        return float(current_vol / avg_vol)
    except:
        return 1.0

def rvol_score(rvol: float) -> float:
    max_score = config.STOCK_SCORE_WEIGHTS.get("participation", 14.0)
    if rvol >= 2.0: return max_score
    if rvol >= 1.5: return max_score * 0.8
    if rvol >= 1.2: return max_score * 0.5
    if rvol >= 1.0: return max_score * 0.2
    return 0.0

def volume_on_move(df_1h: pd.DataFrame, direction: str) -> str:
    if len(df_1h) < 3 or 'Volume' not in df_1h.columns:
        return 'NEUTRAL'
        
    try:
        vols = df_1h['Volume'].tail(3).values
        closes = df_1h['Close'].tail(3).values
        opens = df_1h['Open'].tail(3).values
        
        is_bullish = closes[-1] > opens[-1]
        if direction == 'LONG':
            if is_bullish and vols[-1] > vols[-2]: return 'EXPANDING'
            if not is_bullish and vols[-1] < vols[-2]: return 'DECLINING'
        return 'NEUTRAL'
    except:
        return 'NEUTRAL'
