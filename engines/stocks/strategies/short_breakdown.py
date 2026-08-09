"""
engines/stocks/strategies/short_breakdown.py
Short strategy: Support breakdown in a bearish regime.
"""
def evaluate(ticker, df_1d, df_1h, df_15m, regime, indicators):
    """
    Evaluates a short breakdown setup.
    Only valid if regime is RISK_OFF or PANIC (score < 40).
    """
    if not regime or regime.get('score', 100) >= 40:
        return None
        
    try:
        current_price = float(df_1h['Close'].iloc[-1])
        prev_price    = float(df_1h['Close'].iloc[-2])
        
        # Check volume expansion
        vol_current = float(df_1h['Volume'].iloc[-1])
        vol_ma      = float(df_1h['Volume'].rolling(20).mean().iloc[-1])
        rvol = vol_current / vol_ma if vol_ma > 0 else 0
        
        if rvol < 1.2:
            return None
            
        # Check if price is breaking below recent support (last 20 bars low)
        recent_low = float(df_1h['Low'].iloc[-20:-2].min())
        if current_price > recent_low or prev_price < recent_low:
            return None  # Needs to be a fresh breakdown
            
        # ADX trend confirmation
        from ta.trend import ADXIndicator
        adx_ind = ADXIndicator(df_1h['High'], df_1h['Low'], df_1h['Close'], 14)
        adx = adx_ind.adx().iloc[-1]
        minus_di = adx_ind.adx_neg().iloc[-1]
        plus_di = adx_ind.adx_pos().iloc[-1]
        
        if adx < 20 or minus_di < plus_di:
            return None
            
        from ta.volatility import AverageTrueRange
        atr = AverageTrueRange(df_1d['High'], df_1d['Low'], df_1d['Close'], 14).average_true_range().iloc[-1]
        
        stop_loss = recent_low + (0.5 * atr) # Structural stop above broken support
        target = current_price - (3.0 * atr) # Aggressive target for breakdown
        
        rr = (stop_loss - current_price) / (current_price - target) if (current_price - target) > 0 else 0
        if rr < 1.5:
            rr = (current_price - target) / (stop_loss - current_price) if (stop_loss - current_price) > 0 else 0
            
        return {
            'strategy': 'SHORT_BREAKDOWN',
            'direction': 'SHORT',
            'entry': current_price,
            'stop': stop_loss,
            'target': target,
            'rr': round(rr, 2),
            'total_score_contribution': 65.0
        }
    except Exception:
        return None
