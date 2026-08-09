import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict, derivatives: dict, cvd: dict) -> dict:
    if df_1h.empty:
        return None
        
    cond = True
    
    if not derivatives:
        return None
        
    # Funding negative
    if derivatives.get("funding_current", 0) >= 0:
        cond = False
        
    # L/S ratio
    lsr = derivatives.get("lsr_current")
    if lsr is None or lsr >= 0.45:
        cond = False
        
    if derivatives.get("oi_trend") == "FALLING":
        cond = False
        
    if not cond:
        return None
        
    close = df_1h['Close'].iloc[-1]
    stop = close * 0.95
    target = close * 1.10
    
    return {
        "direction": "LONG",
        "entry": close,
        "stop": stop,
        "target": target,
        "rr": (target - close) / (close - stop) if close > stop else 0,
        "strategy": "SHORT_SQUEEZE",
        "factor_scores": {}
    }
