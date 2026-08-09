import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict, derivatives: dict, cvd: dict) -> dict:
    if regime and regime.get("regime_class") not in ["NEUTRAL", "MODERATE_RISK_ON"]:
        return None
        
    if df_1h.empty:
        return None
        
    cond = True
    
    if derivatives and derivatives.get("funding_current", 0) > 0.01:
        cond = False
        
    if not cond:
        return None
        
    close = df_1h['Close'].iloc[-1]
    stop = close * 0.90
    target = close * 1.15
    
    return {
        "direction": "LONG",
        "entry": close,
        "stop": stop,
        "target": target,
        "rr": (target - close) / (close - stop) if close > stop else 0,
        "strategy": "MEAN_REVERSION",
        "factor_scores": {}
    }
