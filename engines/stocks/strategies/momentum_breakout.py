import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict) -> dict:
    if regime.get('score', 0) < 60:
        return None
        
    try:
        close = df_1h['Close'].iloc[-1]
        
        from ta.trend import ADXIndicator, MACD
        from ta.volatility import BollingerBands, AverageTrueRange
        
        adx_ind = ADXIndicator(high=df_1h['High'], low=df_1h['Low'], close=df_1h['Close'], window=14)
        adx = adx_ind.adx().iloc[-1]
        adx_prev = adx_ind.adx().iloc[-2]
        
        bb = BollingerBands(close=df_1h['Close'], window=20, window_dev=2)
        upper_bb = bb.bollinger_hband().iloc[-1]
        
        pdh = df_1d['High'].iloc[-2] if len(df_1d) >= 2 else close
        
        macd_ind = MACD(close=df_1h['Close'])
        macd_hist = macd_ind.macd_diff()
        
        if adx >= 22 and adx > adx_prev:
            if close > upper_bb and close > pdh:
                if macd_hist.iloc[-1] > 0:
                    atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
                    atr = atr_ind.average_true_range().iloc[-1]
                    
                    stop = pdh - 0.5 * atr if pdh < close else close - atr
                    target = close + config.TARGET_ATR_MULT * atr
                    
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
                            'strategy': 'MOMENTUM_BREAKOUT',
                            'factor_scores': {},
                            'total_score_contribution': 20.0
                        }
    except Exception:
        pass
        
    return None
