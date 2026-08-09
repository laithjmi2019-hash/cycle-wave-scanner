"""
engines/crypto/strategies/short_trend_continuation.py
Short strategy: Fading broken support with negative CVD and OI.
"""
def evaluate(ticker, df_1d, df_1h, df_15m, regime, indicators, derivatives, cvd):
    """
    Evaluates a short trend continuation setup.
    Only valid if regime is RISK_OFF or PANIC (score <= 50).
    """
    if not regime or regime.get('score', 100) > 50:
        return None
        
    try:
        current_price = float(df_1h['Close'].iloc[-1])
        
        # Check derivatives
        if derivatives:
            # We want OI to be rising (shorts piling in) or stable
            if derivatives.get('oi_trend') == 'FALLING':
                return None
            
            # We want funding to be neutral to positive (so shorts don't pay too much)
            if float(derivatives.get('funding_current', 0)) < 0:
                return None
                
        # Check CVD
        if cvd:
            if cvd.get('cvd_direction') == 'POSITIVE':
                return None # Spot buyers are supporting the price
                
        # Structure check: Price below VWAP or 50 EMA
        from ta.trend import EMAIndicator
        ema_50 = EMAIndicator(df_1h['Close'], window=50).ema_indicator().iloc[-1]
        
        if current_price > ema_50:
            return None # Not in a downtrend yet
            
        from ta.volatility import AverageTrueRange
        atr = AverageTrueRange(df_1d['High'], df_1d['Low'], df_1d['Close'], 14).average_true_range().iloc[-1]
        
        recent_high = float(df_1h['High'].iloc[-15:].max())
        stop_loss = max(recent_high + (0.3 * atr), ema_50 + (0.5 * atr))
        target = current_price - (3 * atr)
        
        rr = (current_price - target) / (stop_loss - current_price) if (stop_loss - current_price) > 0 else 0
        if rr < 1.5:
            return None
            
        return {
            'strategy': 'SHORT_TREND_CONTINUATION',
            'direction': 'SHORT',
            'entry': current_price,
            'stop': stop_loss,
            'target': target,
            'rr': round(rr, 2),
            'total_score_contribution': 70.0
        }
    except Exception:
        return None
