import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict) -> dict:
    if regime.get('score', 0) < 40:
        return None
        
    try:
        close = df_1h['Close'].iloc[-1]
        
        from ta.momentum import RSIIndicator
        from ta.trend import EMAIndicator, ADXIndicator
        
        rsi_ind = RSIIndicator(close=df_1h['Close'], window=14)
        rsi = rsi_ind.rsi()
        
        ema50_ind = EMAIndicator(close=df_1h['Close'], window=50)
        ema50 = ema50_ind.ema_indicator().iloc[-1]
        
        adx_ind = ADXIndicator(high=df_1h['High'], low=df_1h['Low'], close=df_1h['Close'], window=14)
        adx = adx_ind.adx().iloc[-1]
        
        df_1h['Date'] = df_1h.index.date
        df_1h['TP'] = (df_1h['High'] + df_1h['Low'] + df_1h['Close']) / 3
        df_1h['TPV'] = df_1h['TP'] * df_1h['Volume']
        vwap = df_1h.groupby('Date')['TPV'].cumsum() / df_1h.groupby('Date')['Volume'].cumsum()
        current_vwap = vwap.iloc[-1]
        
        score_contrib = 0.0
        
        rsi_recent = rsi.iloc[-4:-1]
        if (rsi_recent < 30).any() and 30 <= rsi.iloc[-1] <= 42:
            score_contrib += 20.0
        elif rsi.iloc[-1] < 30:
            score_contrib += 10.0
            
        if 0 < (ema50 - close) / close <= 0.03:
            score_contrib += 5.0
            
        if close < current_vwap:
            score_contrib += 5.0
            
        if adx < 28:
            score_contrib += 5.0
            
        if score_contrib > 0:
            from ta.volatility import AverageTrueRange
            atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
            atr = atr_ind.average_true_range().iloc[-1]
            
            stop = df_1h['Low'].iloc[-5:].min() - 0.5 * atr
            target = min(ema50, close + 4.0 * atr) if ema50 > close else close + 4.0 * atr
            
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
                    'strategy': 'MEAN_REVERSION',
                    'factor_scores': {'rsi': score_contrib},
                    'total_score_contribution': score_contrib
                }
    except Exception:
        pass
        
    return None
