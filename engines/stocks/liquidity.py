import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def get_key_levels(df_1d: pd.DataFrame, df_1h: pd.DataFrame) -> dict:
    levels = {
        'pdh': 0.0,
        'pdl': 0.0,
        'or_high': 0.0,
        'or_low': 0.0,
        'swing_highs': [],
        'swing_lows': []
    }
    
    if df_1d is not None and len(df_1d) >= 2:
        try:
            levels['pdh'] = float(df_1d['High'].iloc[-2])
            levels['pdl'] = float(df_1d['Low'].iloc[-2])
        except: pass
        
    if df_1h is not None and len(df_1h) >= 30:
        try:
            highs = df_1h['High'].values
            lows = df_1h['Low'].values
            levels['swing_highs'] = sorted(list(set([float(highs[-i]) for i in range(1, 30, 5)])), reverse=True)[:3]
            levels['swing_lows'] = sorted(list(set([float(lows[-i]) for i in range(1, 30, 5)])))[:3]
        except: pass
        
    return levels

def liquidity_score(current_price: float, levels: dict, atr: float) -> float:
    score = 0.0
    max_score = config.STOCK_SCORE_WEIGHTS.get("liquidity", 12.0)
    
    if atr <= 0: return 0.0
    
    all_levels = [levels['pdh'], levels['pdl']] + levels['swing_highs'] + levels['swing_lows']
    all_levels = [l for l in all_levels if l > 0]
    
    near_level = any(abs(current_price - l) < atr * 0.5 for l in all_levels)
    if near_level: score += max_score * 0.5
    
    resistances = [l for l in all_levels if l > current_price]
    if not resistances or min(resistances) - current_price > atr * 2.0:
        score += max_score * 0.5
        
    return min(max_score, score)
