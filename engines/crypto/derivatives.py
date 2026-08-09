import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from data import binance_api

class DerivativesAnalyzer:
    def analyze(self, binance_symbol: str) -> dict:
        res = {
            "oi_current": 0.0,
            "oi_change_1h": 0.0,
            "oi_change_4h": 0.0,
            "oi_trend": "STABLE",
            "funding_current": 0.0,
            "funding_trend": "STABLE",
            "funding_interpretation": {},
            "oi_price_signal": {},
            "lsr_current": None,
            "lsr_trend": None,
            "derivatives_score": 0.0,
            "summary": ""
        }
        
        try:
            # OI
            oi_hist = binance_api.get_oi_history(binance_symbol, period="1h", limit=5)
            if oi_hist and len(oi_hist) > 1:
                res["oi_current"] = float(oi_hist[-1]['sumOpenInterestValue'])
                oi_1h_ago = float(oi_hist[-2]['sumOpenInterestValue']) if len(oi_hist) >= 2 else res["oi_current"]
                oi_4h_ago = float(oi_hist[0]['sumOpenInterestValue']) if len(oi_hist) >= 5 else res["oi_current"]
                
                res["oi_change_1h"] = ((res["oi_current"] - oi_1h_ago) / (oi_1h_ago + 1e-9)) * 100
                res["oi_change_4h"] = ((res["oi_current"] - oi_4h_ago) / (oi_4h_ago + 1e-9)) * 100
                
                if res["oi_change_4h"] > 2.0:
                    res["oi_trend"] = "RISING"
                elif res["oi_change_4h"] < -2.0:
                    res["oi_trend"] = "FALLING"
                    
            # Funding
            funding_data = binance_api.get_mark_price_and_funding(binance_symbol)
            if funding_data:
                res["funding_current"] = float(funding_data.get('lastFundingRate', 0.0))
                res["funding_interpretation"] = binance_api.interpret_funding(res["funding_current"])
                
            # Long/Short Ratio
            lsr_hist = binance_api.get_long_short_ratio(binance_symbol, period="1h", limit=5)
            if lsr_hist and len(lsr_hist) > 0:
                res["lsr_current"] = float(lsr_hist[-1]['longShortRatio'])
                if len(lsr_hist) >= 2:
                    lsr_old = float(lsr_hist[0]['longShortRatio'])
                    if res["lsr_current"] > lsr_old + 0.1:
                        res["lsr_trend"] = "RISING"
                    elif res["lsr_current"] < lsr_old - 0.1:
                        res["lsr_trend"] = "FALLING"
                    else:
                        res["lsr_trend"] = "STABLE"

            # Score calculation (Max 16)
            score = 8.0 # Base neutral
            
            # Adjust from funding
            if res["funding_interpretation"]:
                score += res["funding_interpretation"].get("score_adjustment", 0) * 0.5
                
            # Adjust from OI
            if res["oi_trend"] == "RISING":
                score += 3
            elif res["oi_trend"] == "FALLING":
                score -= 2
                
            res["derivatives_score"] = max(0, min(16, score))
            res["summary"] = f"Score: {res['derivatives_score']:.1f}/16. Funding: {res['funding_current']*100:.4f}%, OI Trend: {res['oi_trend']}"
            
        except Exception as e:
            res["summary"] = "Binance API data missing or failed"
            
        return res
