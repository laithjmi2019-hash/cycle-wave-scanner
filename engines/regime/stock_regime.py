import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

class StockRegimeEngine:
    def __init__(self):
        self._cache = None
        self._cache_time = None
        
    def compute(self) -> dict:
        now = datetime.now()
        if self._cache and self._cache_time and (now - self._cache_time) < timedelta(minutes=30):
            return self._cache
            
        tickers = ['SPY', 'QQQ', 'IWM', '^VIX', '^DXY', '^TNX']
        sector_etfs = ['XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLC', 'XLI', 'XLP']
        
        data = yf.download(tickers + sector_etfs, period="5d", interval="1d", group_by="ticker", progress=False)
        
        breakdown = {
            "index_structure": 0.0,
            "vix_regime": 0.0,
            "dxy_trend": 0.0,
            "breadth": 0.0,
            "yield_environment": 0.0
        }
        
        vix = 20.0
        try:
            vix_df = data['^VIX']
            vix = vix_df['Close'].iloc[-1]
            if pd.isna(vix): vix = vix_df['Close'].dropna().iloc[-1]
        except:
            pass
            
        if vix < 15: breakdown['vix_regime'] = 25.0
        elif vix < 20: breakdown['vix_regime'] = 20.0
        elif vix < 25: breakdown['vix_regime'] = 15.0
        elif vix < 30: breakdown['vix_regime'] = 8.0
        else: breakdown['vix_regime'] = 0.0
        
        dxy = 100.0
        try:
            dxy_df = data['^DXY']
            dxy = dxy_df['Close'].iloc[-1]
            if len(dxy_df) > 1:
                if dxy < dxy_df['Close'].iloc[-2]: breakdown['dxy_trend'] = 15.0
                else: breakdown['dxy_trend'] = 5.0
            else:
                breakdown['dxy_trend'] = 10.0
        except:
            breakdown['dxy_trend'] = 10.0

        idx_pts = 0.0
        for idx in ['SPY', 'QQQ', 'IWM']:
            try:
                df_idx = data[idx].dropna()
                if len(df_idx) >= 2:
                    if df_idx['Close'].iloc[-1] > df_idx['Close'].iloc[-2]:
                        idx_pts += 10.0
            except:
                pass
        breakdown['index_structure'] = min(30.0, idx_pts)
        
        pos_sectors = 0
        total_sectors = 0
        for sec in sector_etfs:
            try:
                df_sec = data[sec].dropna()
                if len(df_sec) >= 2:
                    total_sectors += 1
                    if df_sec['Close'].iloc[-1] > df_sec['Close'].iloc[-2]:
                        pos_sectors += 1
            except:
                pass
        if total_sectors > 0:
            breakdown['breadth'] = (pos_sectors / total_sectors) * 20.0
            
        try:
            tnx_df = data['^TNX'].dropna()
            if len(tnx_df) >= 2:
                if tnx_df['Close'].iloc[-1] < tnx_df['Close'].iloc[-2]:
                    breakdown['yield_environment'] = 10.0
                else:
                    breakdown['yield_environment'] = 5.0
            else:
                breakdown['yield_environment'] = 5.0
        except:
            breakdown['yield_environment'] = 5.0
            
        total_score = sum(breakdown.values())
        
        if vix >= config.VIX_PANIC_BLOCK:
            regime = "PANIC"
            total_score = min(total_score, 19.0)
        else:
            regime = config.regime_class(total_score)
            
        result = {
            "score": total_score,
            "regime_class": regime,
            "breakdown": breakdown,
            "vix": float(vix),
            "dxy": float(dxy)
        }
        self._cache = result
        self._cache_time = now
        return result
