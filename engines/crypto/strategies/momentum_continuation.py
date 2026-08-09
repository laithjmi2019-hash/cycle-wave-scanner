import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict, derivatives: dict, cvd: dict, rs: dict) -> dict:
    if not regime or regime.get("score", 0) < 60:
        return None
        
    if df_1h.empty:
        return None
        
    close = df_1h['Close'].iloc[-1]
    
    # Check conditions
    cond = True
    
    # Coin RS vs BTC positive
    if rs:
        rs_last = list(rs.values())[-1]
        if rs_last.get("vs_btc", 0) < 1.0:
            cond = False
            
    # OI rising
    if derivatives and derivatives.get("oi_trend") != "RISING":
        cond = False
        
    # Funding positive but not extreme
    if derivatives:
        f = derivatives.get("funding_current", 0.0)
        if f > 0.0003 or f < 0:
            cond = False
            
    # CVD positive and rising
    if cvd and (cvd.get("cvd_direction") != "POSITIVE" or cvd.get("cvd_slope") != "RISING"):
        cond = False
        
    if not cond:
        return None
        
    stop = close * 0.95
    target = close * 1.15
    
    return {
        "direction": "LONG",
        "entry": close,
        "stop": stop,
        "target": target,
        "rr": (target - close) / (close - stop) if close > stop else 0,
        "strategy": "MOMENTUM_CONTINUATION",
        "factor_scores": {"regime": regime.get("score", 0)}
    }
