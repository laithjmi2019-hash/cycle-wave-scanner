import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict) -> dict:
    # 1. Regime Filter: Intraday setups need at least a Neutral market
    if regime.get('score', 0) < 40:
        return None
        
    try:
        if len(df_15m) < 50:
            return None
            
        from ta.momentum import RSIIndicator
        from ta.trend import EMAIndicator, SMAIndicator
        from ta.volatility import AverageTrueRange
        
        # --- 1D/1H Macro Context ---
        # The daily trend must be UP (Price > 50 EMA on Daily)
        ema50_1d = EMAIndicator(close=df_1d['Close'], window=50).ema_indicator().iloc[-1]
        close_1d = df_1d['Close'].iloc[-1]
        if close_1d < ema50_1d:
            return None
            
        # --- 15m Intraday Dynamics ---
        close_15m = df_15m['Close']
        high_15m = df_15m['High']
        low_15m = df_15m['Low']
        vol_15m = df_15m['Volume']
        
        c = close_15m.iloc[-1]
        l = low_15m.iloc[-1]
        
        # 1. Calculate Intraday VWAP
        df_15m['Date'] = df_15m.index.date
        df_15m['TP'] = (high_15m + low_15m + close_15m) / 3
        df_15m['TPV'] = df_15m['TP'] * vol_15m
        vwap = df_15m.groupby('Date')['TPV'].cumsum() / df_15m.groupby('Date')['Volume'].cumsum()
        curr_vwap = vwap.iloc[-1]
        
        # 2. RSI on 15m
        rsi_15m = RSIIndicator(close=close_15m, window=14).rsi().iloc[-1]
        
        # 3. Relative Volume (RVOL) on 15m (We want high volume today)
        vol_sma20 = SMAIndicator(vol_15m, window=20).sma_indicator().iloc[-1]
        rvol = vol_15m.iloc[-1] / vol_sma20 if vol_sma20 > 0 else 0
        
        # --- INTRADAY VWAP PULLBACK LOGIC ---
        # 1. Stock is oversold on the 15m chart (RSI < 30)
        # 2. Stock taps the VWAP or drops slightly below it (L <= VWAP) but C is still nearby.
        # 3. Stock has overall strong volume today (RVOL > 1.2)
        
        if rsi_15m < 30 and l <= curr_vwap and c >= (curr_vwap * 0.995):
            if rvol > 1.2:
                # Daily ATR for sizing
                atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
                atr_1d = atr_ind.average_true_range().iloc[-1]
                
                # Risk/Reward: 1 to 2
                stop = c - (0.5 * atr_1d) # Tight 15m stop
                target = c + (1.0 * atr_1d)
                
                risk = c - stop
                reward = target - c
                rr = reward / risk if risk > 0 else 0
                
                if rr >= 1.5:
                    return {
                        'direction': 'LONG',
                        'entry': c,
                        'stop': stop,
                        'target': target,
                        'rr': rr,
                        'strategy': 'INTRADAY_VWAP_PULLBACK',
                        'factor_scores': {'rsi': 20.0},
                        'total_score_contribution': 20.0,
                        'rsi': round(float(rsi_15m), 1),
                        'adx': 0.0
                    }
    except Exception:
        pass
        
    return None
