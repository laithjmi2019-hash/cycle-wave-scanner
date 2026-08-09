"""
engines/crypto/strategies/long_squeeze.py
Short strategy: Crowded longs getting squeezed.
"""
def evaluate(ticker, df_1d, df_1h, df_15m, regime, indicators, derivatives, cvd):
    """
    Evaluates a long squeeze setup.
    Valid in NEUTRAL or RISK_OFF regimes.
    """
    if not regime or regime.get('score', 100) > 60:
        return None
        
    try:
        current_price = float(df_1h['Close'].iloc[-1])
        
        if not derivatives:
            return None
            
        # We need highly positive funding (longs paying shorts heavily)
        funding = float(derivatives.get('funding_current', 0))
        if funding < 0.02: # Needs to be reasonably high to squeeze
            return None
            
        ls_ratio = derivatives.get('lsr_current')
        if ls_ratio and float(ls_ratio) < 1.0: # Need longs to be dominant or crowded
            pass
            
        # Price rejecting structural resistance
        recent_high = float(df_1h['High'].iloc[-15:].max())
        if current_price < recent_high * 0.95:
             # Too far from high, wait for rally to short
             return None
             
        # CVD stalling or diverging
        if cvd and cvd.get('price_cvd_divergence') and cvd.get('divergence_direction') == 'BEARISH':
            pass # Perfect, spot is selling while perps are buying
            
        from ta.volatility import AverageTrueRange
        atr = AverageTrueRange(df_1d['High'], df_1d['Low'], df_1d['Close'], 14).average_true_range().iloc[-1]
        
        stop_loss = recent_high + (0.5 * atr)
        target = current_price - (3 * atr)
        
        rr = (current_price - target) / (stop_loss - current_price) if (stop_loss - current_price) > 0 else 0
        if rr < 1.2:
            return None
            
        return {
            'strategy': 'LONG_SQUEEZE',
            'direction': 'SHORT',
            'entry': current_price,
            'stop': stop_loss,
            'target': target,
            'rr': round(rr, 2),
            'total_score_contribution': 65.0
        }
    except Exception:
        return None
