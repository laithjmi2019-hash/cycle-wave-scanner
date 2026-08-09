"""
research/backtest_engine.py — Intrabar-aware backtesting engine.
Simulates trading using the new dual engine on historical data.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

def simulate_trade(entry_price, stop_price, target_price, df_future, direction="LONG"):
    """
    Simulates a trade going forward using the given DataFrame.
    Returns: outcome, exit_price, duration_bars, pnl_pct, mae, mfe
    """
    mae = 0.0
    mfe = 0.0
    
    highest = entry_price
    lowest = entry_price
    initial_stop = stop_price
    current_stop = stop_price
    
    for i, (idx, row) in enumerate(df_future.iterrows()):
        high, low = row['High'], row['Low']
        
        if direction == "LONG":
            highest = max(highest, high)
            current_mae = (low - entry_price) / entry_price * 100
            current_mfe = (high - entry_price) / entry_price * 100
            mae = min(mae, current_mae)
            mfe = max(mfe, current_mfe)
            
            risk_1r = entry_price - initial_stop
            # Move to BE at 1R
            if highest >= entry_price + risk_1r and current_stop < entry_price:
                current_stop = entry_price
            # Trail by 1.5R
            if highest >= entry_price + (1.5 * risk_1r):
                current_stop = max(current_stop, highest - (1.5 * risk_1r))
            
            stop_hit = low <= current_stop
            target_hit = high >= target_price
            
            if stop_hit and target_hit:
                return "AMBIGUOUS", entry_price, i+1, 0.0, mae, mfe
            elif stop_hit:
                pnl = (current_stop - entry_price) / entry_price * 100
                return "STOPPED OUT", current_stop, i+1, pnl, mae, mfe
            elif target_hit:
                pnl = (target_price - entry_price) / entry_price * 100
                return "TARGET HIT", target_price, i+1, pnl, mae, mfe
                
        else: # SHORT
            lowest = min(lowest, low)
            current_mae = (entry_price - high) / entry_price * 100
            current_mfe = (entry_price - low) / entry_price * 100
            mae = min(mae, current_mae)
            mfe = max(mfe, current_mfe)
            
            risk_1r = initial_stop - entry_price
            # Move to BE at 1R
            if lowest <= entry_price - risk_1r and current_stop > entry_price:
                current_stop = entry_price
            # Trail by 1.5R
            if lowest <= entry_price - (1.5 * risk_1r):
                current_stop = min(current_stop, lowest + (1.5 * risk_1r))
            
            stop_hit = high >= current_stop
            target_hit = low <= target_price
            
            if stop_hit and target_hit:
                return "AMBIGUOUS", entry_price, i+1, 0.0, mae, mfe
            elif stop_hit:
                pnl = (entry_price - current_stop) / entry_price * 100
                return "STOPPED OUT", current_stop, i+1, pnl, mae, mfe
            elif target_hit:
                pnl = (entry_price - target_price) / entry_price * 100
                return "TARGET HIT", target_price, i+1, pnl, mae, mfe
                
    # If we reach end of data without hitting stop/target
    last_close = df_future['Close'].iloc[-1]
    if direction == "LONG":
        pnl = (last_close - entry_price) / entry_price * 100
    else:
        pnl = (entry_price - last_close) / entry_price * 100
        
    return "TIME STOP", last_close, len(df_future), pnl, mae, mfe

def calc_metrics(trades):
    """Calculate all required backtest metrics from a list of trades."""
    if not trades or not [t for t in trades if t['outcome'] != 'AMBIGUOUS']:
        return {
            "total_trades": len(trades) if trades else 0,
            "valid_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy_pct": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "avg_duration": 0.0,
            "avg_mae": 0.0,
            "avg_mfe": 0.0
        }
        
    valid_trades = [t for t in trades if t['outcome'] != 'AMBIGUOUS']
         
    wins = [t for t in valid_trades if t['pnl_pct'] > 0]
    losses = [t for t in valid_trades if t['pnl_pct'] <= 0]
    
    win_rate = len(wins) / len(valid_trades)
    avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0
    
    gross_profit = sum(t['pnl_pct'] for t in wins)
    gross_loss = abs(sum(t['pnl_pct'] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
    
    avg_duration = np.mean([t['duration_bars'] for t in valid_trades])
    mae_avg = np.mean([t['mae'] for t in valid_trades])
    mfe_avg = np.mean([t['mfe'] for t in valid_trades])
    
    # Calculate Max Drawdown based on cumulative returns sequence
    cum_returns = []
    current_ret = 1.0
    for t in valid_trades:
        current_ret *= (1 + t['pnl_pct'] / 100)
        cum_returns.append(current_ret)
        
    if cum_returns:
        peaks = pd.Series(cum_returns).cummax()
        drawdowns = (pd.Series(cum_returns) - peaks) / peaks
        max_dd = drawdowns.min() * 100
    else:
        max_dd = 0.0

    return {
        "total_trades": len(trades),
        "valid_trades": len(valid_trades),
        "win_rate": win_rate * 100,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy_pct": expectancy,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "avg_duration": avg_duration,
        "avg_mae": mae_avg,
        "avg_mfe": mfe_avg
    }
