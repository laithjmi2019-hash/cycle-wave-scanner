import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def calc_crypto_rs(ticker_df: pd.DataFrame, btc_df: pd.DataFrame, eth_df: pd.DataFrame = None, periods=[5,15,30,60]) -> dict:
    res = {}
    if ticker_df.empty or btc_df.empty:
        return res
        
    for p in periods:
        if len(ticker_df) >= p and len(btc_df) >= p:
            t_ret = ticker_df['Close'].iloc[-1] / ticker_df['Close'].iloc[-p] - 1
            b_ret = btc_df['Close'].iloc[-1] / btc_df['Close'].iloc[-p] - 1
            vs_btc = (1 + t_ret) / (1 + b_ret)
            
            vs_eth = 1.0
            if eth_df is not None and not eth_df.empty and len(eth_df) >= p:
                e_ret = eth_df['Close'].iloc[-1] / eth_df['Close'].iloc[-p] - 1
                vs_eth = (1 + t_ret) / (1 + e_ret)
                
            res[p] = {"vs_btc": float(vs_btc), "vs_eth": float(vs_eth)}
    return res

def rs_score(rs_dict: dict) -> float:
    # 0-16 from config weights
    score = 8.0
    if not rs_dict:
        return score
    for p, vals in rs_dict.items():
        if vals["vs_btc"] > 1.05:
            score += 2.0
        elif vals["vs_btc"] < 0.95:
            score -= 2.0
    return max(0, min(16, score))

def persistence_score(rs_dict: dict) -> float:
    # does the coin CONSISTENTLY outperform across periods?
    if not rs_dict:
        return 0.0
    outperform_count = sum(1 for v in rs_dict.values() if v["vs_btc"] > 1.0)
    return outperform_count / len(rs_dict)

def narrative_strength(ticker: str, narrative_peers_dfs: dict) -> float:
    return 1.0
