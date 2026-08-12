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
        from ta.volatility import BollingerBands, AverageTrueRange
        
        # Calculate VWAP
        df_1h['Date'] = df_1h.index.date
        df_1h['TP'] = (df_1h['High'] + df_1h['Low'] + df_1h['Close']) / 3
        df_1h['TPV'] = df_1h['TP'] * df_1h['Volume']
        vwap = df_1h.groupby('Date')['TPV'].cumsum() / df_1h.groupby('Date')['Volume'].cumsum()
        current_vwap = vwap.iloc[-1]
        
        rsi_ind = RSIIndicator(close=df_1h['Close'], window=14)
        rsi = rsi_ind.rsi().iloc[-1]
        
        bb = BollingerBands(close=df_1h['Close'], window=20, window_dev=2.0)
        bb_lower = bb.bollinger_lband().iloc[-1]
        
        atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
        atr = atr_ind.average_true_range().iloc[-1]
        
        strategy_name = ""
        stop = 0.0
        target = 0.0
        
        # COMBO 8: Ultra-Inverted Scalp (Risk 4 to make 1)
        if rsi < 25 and close < bb_lower and close < current_vwap:
            strategy_name = "ULTRA_INVERTED_SCALP"
            stop = close - (4.0 * atr)
            target = close + (1.0 * atr)
            
        # COMBO 6: Deep Mean Reversion Sniper (Risk 1 to make 1)
        elif rsi < 20 and close < (bb_lower - 0.5 * atr):
            strategy_name = "DEEP_MEAN_REVERSION"
            stop = close - (2.0 * atr)
            target = close + (2.0 * atr)
            
        if strategy_name:
            risk = close - stop
            reward = target - close
            rr = reward / risk if risk > 0 else 0
            
            return {
                'direction': 'LONG',
                'entry': close,
                'stop': stop,
                'target': target,
                'rr': rr,
                'strategy': strategy_name,
                'factor_scores': {'rsi': 20.0},
                'total_score_contribution': 20.0,
                'rsi': round(float(rsi), 1),
                'adx': 0.0
            }
    except Exception:
        pass
        
    return None
