import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def calc_relative_strength(ticker_df_1h: pd.DataFrame, benchmark_df_1h: pd.DataFrame, periods=[5,15,30,60]) -> dict:
    rs_dict = {}
    if ticker_df_1h is None or ticker_df_1h.empty or benchmark_df_1h is None or benchmark_df_1h.empty:
        return {p: 1.0 for p in periods}
        
    try:
        t_close = ticker_df_1h['Close']
        b_close = benchmark_df_1h['Close']
        
        common_idx = t_close.index.intersection(b_close.index)
        t_close = t_close.loc[common_idx]
        b_close = b_close.loc[common_idx]
        
        for p in periods:
            if len(t_close) > p:
                t_ret = t_close.iloc[-1] / t_close.iloc[-(p+1)]
                b_ret = b_close.iloc[-1] / b_close.iloc[-(p+1)]
                rs_dict[p] = float(t_ret / b_ret) if b_ret != 0 else 1.0
            else:
                rs_dict[p] = 1.0
    except Exception as e:
        rs_dict = {p: 1.0 for p in periods}
        
    return rs_dict

def calc_rs_score(rs_dict: dict) -> float:
    weight_map = {5: 0.1, 15: 0.2, 30: 0.3, 60: 0.4}
    max_score = config.STOCK_SCORE_WEIGHTS.get("relative_strength", 18.0)
    
    val = sum(rs_dict.get(p, 1.0) * w for p, w in weight_map.items())
        
    if val > 1.05: return max_score
    elif val > 1.0: return max_score * 0.75
    elif val > 0.95: return max_score * 0.4
    return 0.0

def get_sector_etf(ticker: str) -> str:
    return config.TICKER_SECTOR.get(ticker, "SPY")

def rs_trend(rs_values: dict) -> str:
    short_term = rs_values.get(5, 1.0)
    long_term = rs_values.get(30, 1.0)
    if short_term > long_term and short_term > 1.0:
        return 'IMPROVING'
    elif short_term < long_term and short_term < 1.0:
        return 'DETERIORATING'
    return 'STABLE'
