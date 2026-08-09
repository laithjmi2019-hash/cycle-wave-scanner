import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict) -> dict:
    if regime.get('score', 0) < 55:
        return None
        
    try:
        close = df_1h['Close'].iloc[-1]
        
        from ta.momentum import RSIIndicator
        from ta.trend import EMAIndicator
        from ta.volatility import AverageTrueRange
        
        rsi_ind = RSIIndicator(close=df_1h['Close'], window=14)
        rsi = rsi_ind.rsi()
        
        ema50_ind = EMAIndicator(close=df_1h['Close'], window=50)
        ema50 = ema50_ind.ema_indicator().iloc[-1]
        
        if rsi.iloc[-5:].max() > 60 and 40 <= rsi.iloc[-1] <= 55:
            if close > ema50:
                atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
                atr = atr_ind.average_true_range().iloc[-1]
                
                stop = df_1h['Low'].iloc[-5:].min() - 0.2 * atr
                target = df_1h['High'].iloc[-15:].max()
                
                risk = close - stop
                reward = target - close
                rr = reward / risk if risk > 0 else 0
                
                if rr >= config.MIN_RR_RATIO:
                    return {
                        'direction': 'LONG',
                        'entry': close,
                        'stop': stop,
                        'target': target,
                        'rr': rr,
                        'strategy': 'PULLBACK_CONTINUATION',
                        'factor_scores': {},
                        'total_score_contribution': 15.0
                    }
    except Exception:
        pass
        
    return None
