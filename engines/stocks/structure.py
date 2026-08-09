import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def detect_structure(df_1h: pd.DataFrame) -> dict:
    res = {
        'trend': 'RANGING',
        'hh_hl': False,
        'll_lh': False,
        'bos': False,
        'choch': False,
        'compression': False,
        'acceptance': False,
        'score': 0.0
    }
    
    if df_1h is None or len(df_1h) < 20:
        return res
        
    try:
        closes = df_1h['Close'].values
        highs = df_1h['High'].values
        lows = df_1h['Low'].values
        
        recent_h = highs[-10:]
        recent_l = lows[-10:]
        
        hh = recent_h[-1] > recent_h[0]
        hl = recent_l[-1] > recent_l[0]
        lh = recent_h[-1] < recent_h[0]
        ll = recent_l[-1] < recent_l[0]
        
        res['hh_hl'] = bool(hh and hl)
        res['ll_lh'] = bool(ll and lh)
        
        if res['hh_hl']: res['trend'] = 'UPTREND'
        elif res['ll_lh']: res['trend'] = 'DOWNTREND'
        
        try:
            from ta.volatility import BollingerBands
            bb = BollingerBands(close=df_1h['Close'], window=20, window_dev=2)
            bbw = bb.bollinger_wband()
            bbw_recent = bbw.iloc[-20:]
            if bbw.iloc[-1] <= bbw_recent.quantile(0.2):
                res['compression'] = True
        except:
            pass
            
        swing_high = highs[-20:-5].max()
        if closes[-1] > swing_high:
            res['bos'] = True
            if res['trend'] == 'DOWNTREND':
                res['choch'] = True
                
        if closes[-1] > swing_high and closes[-2] > swing_high:
            res['acceptance'] = True
            
        max_score = config.STOCK_SCORE_WEIGHTS.get("price_structure", 14.0)
        s = 0.0
        if res['trend'] == 'UPTREND': s += max_score * 0.4
        if res['bos']: s += max_score * 0.3
        if res['acceptance']: s += max_score * 0.3
        res['score'] = min(max_score, s)
        
    except Exception:
        pass
        
    return res
