import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from engines.crypto.strategies import momentum_continuation, liquidity_sweep_reversal, short_squeeze, mean_reversion, short_trend_continuation, long_squeeze, liquidation_sniper

def analyze_crypto(ticker: str, df_1d, df_1h, df_15m, regime_data, derivatives_data, cvd_data, rs_data) -> dict:
    strategies = [
        momentum_continuation.evaluate,
        liquidity_sweep_reversal.evaluate,
        short_squeeze.evaluate,
        mean_reversion.evaluate,
        short_trend_continuation.evaluate,
        long_squeeze.evaluate,
        liquidation_sniper.evaluate
    ]
    
    best_signal = None
    best_score = -1
    
    for strat in strategies:
        try:
            res = strat(ticker, df_1d, df_1h, df_15m, regime_data, {}, derivatives_data, cvd_data, rs_data) if 'rs' in strat.__code__.co_varnames else strat(ticker, df_1d, df_1h, df_15m, regime_data, {}, derivatives_data, cvd_data)
            if res:
                score = res.get('total_score_contribution', 70.0)
                if score > best_score:
                    best_score = score
                    best_signal = res
        except Exception:
            pass
            
    if best_signal:
        quality = "C"
        if best_score >= config.SCORE_THRESHOLDS.get("A+", 82):
            quality = "A+"
        elif best_score >= config.SCORE_THRESHOLDS.get("A", 68):
            quality = "A"
        elif best_score >= config.SCORE_THRESHOLDS.get("B+", 54):
            quality = "B+"
        elif best_score >= config.SCORE_THRESHOLDS.get("B", 40):
            quality = "B"
            
        best_signal.update({
            "ticker": ticker,
            "asset_class": "CRYPTO",
            "pos_size": config.BASE_RISK_PCT * config.QUALITY_RISK_MULT.get(quality, 0),
            "total_score": best_score,
            "quality_class": quality,
            "breakdown": {},
            "oi_summary": derivatives_data.get("summary", "") if derivatives_data else "N/A",
            "funding_summary": derivatives_data.get("funding_current", "") if derivatives_data else "N/A",
            "cvd_summary": cvd_data.get("cvd_direction", "") if cvd_data else "N/A",
            "narrative": "Altcoin Season" if rs_data and rs_data.get('rs_score', 0) > 0 else "BTC Dominance",
            "btc_regime": regime_data.get('regime_class', 'N/A'),
            "rs_vs_btc": rs_data.get('trend', 'N/A') if rs_data else "N/A",
            "reason_top3": [
                f"Strategy: {best_signal.get('strategy', '')}",
                f"Regime: {regime_data.get('regime_class', 'N/A')}",
                f"RR: {best_signal.get('rr', 0):.2f}"
            ],
            "timestamp": time.time()
        })
        
    return best_signal
