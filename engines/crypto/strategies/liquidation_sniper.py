"""
engines/crypto/strategies/liquidation_sniper.py
Strategy: Sniping extreme liquidation cascades in real-time.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from data.binance_websocket import get_recent_liquidations

def evaluate(ticker, df_1d, df_1h, df_15m, regime, indicators, derivatives, cvd):
    """
    Evaluates if there is a massive liquidation event that warrants a counter-trade.
    """
    try:
        # Format ticker for Binance WS (e.g. BTC-USD -> BTCUSDT)
        ws_symbol = ticker.replace('-', '') + "T" 
        
        long_liq, short_liq = get_recent_liquidations(ws_symbol, seconds=300)
        
        current_price = float(df_15m['Close'].iloc[-1])
        
        from ta.volatility import AverageTrueRange
        atr = AverageTrueRange(df_1d['High'], df_1d['Low'], df_1d['Close'], 14).average_true_range().iloc[-1]
        
        # Scenario A: Massive Long Liquidation Cascade (Buy the blood)
        if long_liq > 2_000_000: # Over $2M in longs liquidated in last 5 mins
            stop_loss = current_price - (0.5 * atr)
            target = current_price + (2 * atr) # Reversion target
            
            rr = (target - current_price) / (current_price - stop_loss)
            
            return {
                'strategy': 'LIQUIDATION_SNIPER_LONG',
                'direction': 'LONG',
                'entry': current_price,
                'stop': stop_loss,
                'target': target,
                'rr': round(rr, 2),
                'total_score_contribution': 95.0 # Highest conviction
            }
            
        # Scenario B: Massive Short Liquidation Cascade (Short the top)
        if short_liq > 2_000_000:
            stop_loss = current_price + (0.5 * atr)
            target = current_price - (2 * atr)
            
            rr = (current_price - target) / (stop_loss - current_price)
            
            return {
                'strategy': 'LIQUIDATION_SNIPER_SHORT',
                'direction': 'SHORT',
                'entry': current_price,
                'stop': stop_loss,
                'target': target,
                'rr': round(rr, 2),
                'total_score_contribution': 95.0
            }
            
        return None
    except Exception:
        return None
