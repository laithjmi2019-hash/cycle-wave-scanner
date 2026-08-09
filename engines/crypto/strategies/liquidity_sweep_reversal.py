import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict, derivatives: dict, cvd: dict) -> dict:
    if df_1h.empty or len(df_1h) < 24:
        return None
        
    close = df_1h['Close'].iloc[-1]
    recent_low = df_1h['Low'].iloc[-24:].min()
    
    cond = True
    
    # Sweep condition
    if close <= recent_low:
        cond = False
        
    if derivatives and derivatives.get("oi_trend") == "RISING":
        cond = False # we want OI flushed
        
    if not cond:
        return None
        
    stop = recent_low * 0.99
    target = close + (close - stop) * 3
    
    return {
        "direction": "LONG",
        "entry": close,
        "stop": stop,
        "target": target,
        "rr": (target - close) / (close - stop) if close > stop else 0,
        "strategy": "LIQUIDITY_SWEEP",
        "factor_scores": {}
    }
