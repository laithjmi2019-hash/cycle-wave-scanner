import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict) -> dict:
    if regime.get('score', 0) < 60:
        return None
        
    try:
        close = df_1h['Close'].iloc[-1]
        prev_close = df_1h['Close'].iloc[-2]
        
        from ta.volatility import BollingerBands, KeltnerChannel, AverageTrueRange
        from ta.trend import SMAIndicator
        
        # Squeeze Check
        bb = BollingerBands(close=df_1h['Close'], window=20, window_dev=2.0)
        kc = KeltnerChannel(high=df_1h['High'], low=df_1h['Low'], close=df_1h['Close'], window=20, window_atr=1.5)
        
        bb_upper = bb.bollinger_hband()
        bb_lower = bb.bollinger_lband()
        kc_upper = kc.keltner_channel_hband()
        kc_lower = kc.keltner_channel_lband()
        
        squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
        squeeze_curr = squeeze.iloc[-1]
        squeeze_prev = squeeze.iloc[-2]
        
        # VWAP calculation
        df_1h['Date'] = df_1h.index.date
        df_1h['TP'] = (df_1h['High'] + df_1h['Low'] + df_1h['Close']) / 3
        df_1h['TPV'] = df_1h['TP'] * df_1h['Volume']
        vwap = df_1h.groupby('Date')['TPV'].cumsum() / df_1h.groupby('Date')['Volume'].cumsum()
        
        vwap_curr = vwap.iloc[-1]
        vwap_prev = vwap.iloc[-2]
        
        # RVOL
        vol_sma20 = SMAIndicator(df_1h['Volume'], window=20).sma_indicator().iloc[-1]
        rvol = df_1h['Volume'].iloc[-1] / vol_sma20 if vol_sma20 > 0 else 0
        
        atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
        atr = atr_ind.average_true_range().iloc[-1]
        
        # COMBO 7: VWAP Breakout Surge (Risk 1 to make 3)
        if squeeze_prev == True and squeeze_curr == False:
            if rvol > 2.0 and close > vwap_curr and prev_close < vwap_prev:
                
                stop = close - (1.0 * atr)
                target = close + (3.0 * atr)
                
                risk = close - stop
                reward = target - close
                rr = reward / risk if risk > 0 else 0
                
                if rr >= config.MIN_RR_RATIO:
                    from ta.momentum import RSIIndicator
                    from ta.trend import ADXIndicator
                    rsi = RSIIndicator(close=df_1h['Close'], window=14).rsi().iloc[-1]
                    adx = ADXIndicator(high=df_1h['High'], low=df_1h['Low'], close=df_1h['Close'], window=14).adx().iloc[-1]
                    return {
                        'direction': 'LONG',
                        'entry': close,
                        'stop': stop,
                        'target': target,
                        'rr': rr,
                        'strategy': 'VWAP_BREAKOUT_SURGE',
                        'factor_scores': {},
                        'total_score_contribution': 20.0,
                        'rsi': round(float(rsi), 1),
                        'adx': round(float(adx), 1)
                    }
    except Exception:
        pass
        
    return None
