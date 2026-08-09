"""
engines/stocks/strategies/short_mean_reversion.py
Short strategy: Fading an overextended rally in a downtrend.
"""
def evaluate(ticker, df_1d, df_1h, df_15m, regime, indicators):
    """
    Evaluates a short mean reversion setup.
    Only valid if regime is RISK_OFF or PANIC (score <= 45).
    """
    if not regime or regime.get('score', 100) > 45:
        return None
        
    try:
        current_price = float(df_1h['Close'].iloc[-1])
        
        # Check RSI overbought
        from ta.momentum import RSIIndicator
        rsi_ind = RSIIndicator(df_1h['Close'], window=14)
        rsi = rsi_ind.rsi()
        current_rsi = float(rsi.iloc[-1])
        prev_rsi = float(rsi.iloc[-2])
        
        # Look for RSI crossing down from overbought territory (e.g. 70)
        if current_rsi > 65 or (prev_rsi >= 70 and current_rsi < 70):
            pass # Valid setup
        else:
            return None
            
        # Check moving average rejection (e.g., price hitting 50 EMA from below)
        from ta.trend import EMAIndicator
        ema_50 = EMAIndicator(df_1h['Close'], window=50).ema_indicator().iloc[-1]
        
        # If price is far above EMA50 during a downtrend, it's overextended.
        # If it's rejecting near EMA50, it's a MA rejection.
        if current_price < ema_50 * 0.95:
             # Not overextended upwards relative to 50 EMA
             pass
             
        from ta.volatility import AverageTrueRange
        atr = AverageTrueRange(df_1d['High'], df_1d['Low'], df_1d['Close'], 14).average_true_range().iloc[-1]
        
        # Stop loss placed slightly above the recent high
        recent_high = float(df_1h['High'].iloc[-10:].max())
        stop_loss = recent_high + (0.5 * atr)
        
        # Target recent swing low
        recent_low = float(df_1h['Low'].iloc[-30:].min())
        target = min(recent_low, current_price - (2 * atr))
        
        rr = (current_price - target) / (stop_loss - current_price) if (stop_loss - current_price) > 0 else 0
        if rr < 1.2:
            return None
            
        return {
            'strategy': 'SHORT_MEAN_REVERSION',
            'direction': 'SHORT',
            'entry': current_price,
            'stop': stop_loss,
            'target': target,
            'rr': round(rr, 2),
            'total_score_contribution': 60.0
        }
    except Exception:
        return None
