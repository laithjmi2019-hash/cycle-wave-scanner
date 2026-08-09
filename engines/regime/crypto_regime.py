import sys
import os
import time
import datetime
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator

# Import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from data import binance_api

class CryptoRegimeEngine:
    def __init__(self):
        self.cache = None
        self.cache_time = 0

    def compute(self) -> dict:
        now = time.time()
        if self.cache and (now - self.cache_time) < 900:  # 15 minutes
            return self.cache

        try:
            # Fetch YF data
            btc_1h = yf.download("BTC-USD", period="60d", interval="1h", progress=False)
            eth_1h = yf.download("ETH-USD", period="30d", interval="1h", progress=False)
            spy_1h = yf.download("SPY", period="30d", interval="1h", progress=False)
            
            if btc_1h.empty:
                return self._fallback()

            # BTC Structure Score (0-30)
            btc_close = btc_1h['Close'].iloc[-1].item() if isinstance(btc_1h['Close'].iloc[-1], pd.Series) else btc_1h['Close'].iloc[-1]
            btc_1h['VWAP'] = (btc_1h['Volume'] * (btc_1h['High'] + btc_1h['Low'] + btc_1h['Close']) / 3).cumsum() / btc_1h['Volume'].cumsum()
            vwap = btc_1h['VWAP'].iloc[-1].item() if isinstance(btc_1h['VWAP'].iloc[-1], pd.Series) else btc_1h['VWAP'].iloc[-1]
            
            adx_ind = ADXIndicator(high=btc_1h['High'].squeeze(), low=btc_1h['Low'].squeeze(), close=btc_1h['Close'].squeeze(), window=14)
            adx = adx_ind.adx().iloc[-1]
            
            btc_structure_score = 15
            if btc_close > vwap:
                btc_structure_score += 5
            if btc_close > btc_1h['Close'].iloc[-24].item() if isinstance(btc_1h['Close'].iloc[-24], pd.Series) else btc_1h['Close'].iloc[-24]:
                btc_structure_score += 5
            if adx > 25:
                btc_structure_score += 5

            # BTC Dominance Score (0-20)
            if not eth_1h.empty:
                eth_close = eth_1h['Close'].iloc[-1].item() if isinstance(eth_1h['Close'].iloc[-1], pd.Series) else eth_1h['Close'].iloc[-1]
                btc_mc = btc_close * 21_000_000
                eth_mc = eth_close * 120_000_000
                dom_current = btc_mc / (btc_mc + eth_mc)
                
                eth_close_old = eth_1h['Close'].iloc[-24].item() if isinstance(eth_1h['Close'].iloc[-24], pd.Series) else eth_1h['Close'].iloc[-24]
                btc_close_old = btc_1h['Close'].iloc[-24].item() if isinstance(btc_1h['Close'].iloc[-24], pd.Series) else btc_1h['Close'].iloc[-24]
                btc_mc_old = btc_close_old * 21_000_000
                eth_mc_old = eth_close_old * 120_000_000
                dom_old = btc_mc_old / (btc_mc_old + eth_mc_old)
                
                if dom_current < dom_old:
                    btc_dominance_score = 15 # altcoin season
                else:
                    btc_dominance_score = 10 # rising dominance
            else:
                btc_dominance_score = 10

            # Funding Score (0-20)
            funding_data = binance_api.get_mark_price_and_funding("BTCUSDT")
            funding_score = 10
            funding_current = 0.0
            if funding_data:
                funding_current = float(funding_data.get('lastFundingRate', 0.0))
                funding_interp = binance_api.interpret_funding(funding_current)
                # Adjust based on interpretation
                bias = funding_interp.get("bias", "")
                if bias == "LONG_CROWDED":
                    funding_score = 5
                elif bias == "LONG_LEAN":
                    funding_score = 12
                elif bias == "NEUTRAL":
                    funding_score = 15
                elif bias == "SHORT_LEAN":
                    funding_score = 18
                elif bias == "SHORT_CROWDED":
                    funding_score = 20

            # OI Score (0-15)
            oi_hist = binance_api.get_oi_history("BTCUSDT", period="1h", limit=24)
            oi_score = 7
            oi_trend = "STABLE"
            if oi_hist and len(oi_hist) > 1:
                oi_first = float(oi_hist[0]['sumOpenInterestValue'])
                oi_last = float(oi_hist[-1]['sumOpenInterestValue'])
                if oi_last > oi_first and btc_close > btc_close_old:
                    oi_score = 15
                    oi_trend = "RISING"
                elif oi_last < oi_first:
                    oi_trend = "FALLING"
                    
            # Macro Correlation Score (0-15)
            macro_corr_score = 7
            if not spy_1h.empty:
                spy_close = spy_1h['Close'].iloc[-1].item() if isinstance(spy_1h['Close'].iloc[-1], pd.Series) else spy_1h['Close'].iloc[-1]
                spy_old = spy_1h['Close'].iloc[-24].item() if isinstance(spy_1h['Close'].iloc[-24], pd.Series) else spy_1h['Close'].iloc[-24]
                spy_up = spy_close > spy_old
                btc_up = btc_close > btc_close_old
                
                if btc_up and not spy_up:
                    macro_corr_score = 15 # Alpha signal
                elif btc_up and spy_up:
                    macro_corr_score = 10 # Aligned
                elif not btc_up and not spy_up:
                    macro_corr_score = 5 # Risk-off
                else:
                    macro_corr_score = 8
                    
            total_score = btc_structure_score + btc_dominance_score + funding_score + oi_score + macro_corr_score
            regime_class = config.regime_class(total_score)
            
            res = {
                "score": total_score,
                "regime_class": regime_class,
                "breakdown": {
                    "btc_structure": btc_structure_score,
                    "btc_dominance": btc_dominance_score,
                    "funding": funding_score,
                    "oi": oi_score,
                    "macro_corr": macro_corr_score
                },
                "btc_price": btc_close,
                "btc_trend": "UP" if btc_close > btc_close_old else "DOWN",
                "funding_current": funding_current,
                "oi_trend": oi_trend
            }
            self.cache = res
            self.cache_time = now
            return res

        except Exception as e:
            return self._fallback()

    def _fallback(self):
        return {
            "score": 50,
            "regime_class": "NEUTRAL",
            "breakdown": {},
            "btc_price": 0.0,
            "btc_trend": "UNKNOWN",
            "funding_current": 0.0,
            "oi_trend": "UNKNOWN"
        }
