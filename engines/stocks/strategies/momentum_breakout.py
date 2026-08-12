import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config

def evaluate(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime: dict, indicators: dict) -> dict:
    # 1. Regime Filter: Intraday breakouts need at least a Neutral/Risk-On market
    if regime.get('score', 0) < 40:
        return None
        
    try:
        # We need at least enough 15m bars for VWAP and Volatility bands
        if len(df_15m) < 50:
            return None
            
        from ta.volatility import BollingerBands, KeltnerChannel, AverageTrueRange
        from ta.trend import SMAIndicator, EMAIndicator
        
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
        prev_c = close_15m.iloc[-2]
        
        # 1. Calculate Intraday VWAP
        df_15m['Date'] = df_15m.index.date
        df_15m['TP'] = (high_15m + low_15m + close_15m) / 3
        df_15m['TPV'] = df_15m['TP'] * vol_15m
        vwap = df_15m.groupby('Date')['TPV'].cumsum() / df_15m.groupby('Date')['Volume'].cumsum()
        curr_vwap = vwap.iloc[-1]
        
        # 2. Relative Volume (RVOL) on 15m
        vol_sma20 = SMAIndicator(vol_15m, window=20).sma_indicator().iloc[-1]
        rvol = vol_15m.iloc[-1] / vol_sma20 if vol_sma20 > 0 else 0
        
        # 3. Volatility Squeeze on 15m
        bb = BollingerBands(close=close_15m, window=20, window_dev=2.0)
        kc = KeltnerChannel(high=high_15m, low=low_15m, close=close_15m, window=20, window_atr=1.5)
        
        bb_upper = bb.bollinger_hband()
        bb_lower = bb.bollinger_lband()
        kc_upper = kc.keltner_channel_hband()
        kc_lower = kc.keltner_channel_lband()
        
        squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
        sq_curr = squeeze.iloc[-1]
        sq_prev = squeeze.iloc[-2]
        
        # --- INTRADAY BREAKOUT LOGIC ---
        # 1. Squeeze is firing (was True, is now False)
        # 2. Price is ripping above the upper Bollinger Band
        # 3. Volume is surging (RVOL > 1.5)
        # 4. Stock is trading above VWAP (Intraday Bullish Control)
        
        if sq_prev == True and sq_curr == False:
            if c > bb_upper.iloc[-1] and c > curr_vwap and rvol > 1.5:
                
                # Daily ATR for sizing
                atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
                atr_1d = atr_ind.average_true_range().iloc[-1]
                
                # Risk/Reward: 1 to 2
                stop = c - (0.5 * atr_1d) # Tight 15m stop
                target = c + (1.0 * atr_1d)
                
                risk = c - stop
                reward = target - c
                rr = reward / risk if risk > 0 else 0
                
                if rr >= 1.5: # At least 1.5 R:R
                    return {
                        'direction': 'LONG',
                        'entry': c,
                        'stop': stop,
                        'target': target,
                        'rr': rr,
                        'strategy': 'INTRADAY_MOMENTUM_BREAKOUT',
                        'factor_scores': {'rvol': 20.0},
                        'total_score_contribution': 20.0,
                        'rsi': 0.0,
                        'adx': 0.0
                    }
    except Exception:
        pass
        
    return None
