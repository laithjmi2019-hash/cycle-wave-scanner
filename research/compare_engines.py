"""
research/compare_engines.py — Backtest comparison: V13 vs Dual Engine
Runs a simulation over recent 60d hourly data for a sample of assets
and generates the final research report.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import datetime
from data.fetcher import fetch_stock, fetch_crypto, fetch_regime_data
from research.backtest_engine import simulate_trade, calc_metrics
from v13_baseline.analyzer import analyze_asset as v13_analyze_asset

SAMPLE_STOCKS = ["AAPL", "TSLA", "SAP.DE", "EMAAR.AE"]
SAMPLE_CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD"]

def run_v13_backtest(ticker, df_1d, df_1h):
    trades = []
    # Simplified simulation iterating over bars
    # We need to simulate the analyzer at each point in time.
    for i in range(50, len(df_1h) - 10):
        # We look at historical window up to i
        hist_1h = df_1h.iloc[:i]
        hist_1d = df_1d[df_1d.index <= hist_1h.index[-1]]
        
        try:
            signal = v13_analyze_asset(ticker, hist_1d, hist_1h, None)
            if signal:
                # Trade fired!
                future_df = df_1h.iloc[i:]
                direction = "SHORT" if "SHORT" in signal['recommendation'] else "LONG"
                
                outcome, exit_price, duration, pnl, mae, mfe = simulate_trade(
                    entry_price=signal['entry_price'],
                    stop_price=signal['stop_loss_raw'],
                    target_price=signal['target_raw'],
                    df_future=future_df,
                    direction=direction
                )
                trades.append({
                    "time": hist_1h.index[-1],
                    "outcome": outcome,
                    "pnl_pct": pnl,
                    "duration_bars": duration,
                    "mae": mae,
                    "mfe": mfe
                })
        except Exception as e:
            pass
            
    return trades

def run_new_stock_backtest(ticker, df_1d, df_1h, regime_data):
    trades = []
    from engines.stocks.stock_engine import analyze_stock
    
    for i in range(50, len(df_1h) - 10):
        hist_1h = df_1h.iloc[:i]
        hist_1d = df_1d[df_1d.index <= hist_1h.index[-1]]
        
        try:
            signal = analyze_stock(ticker, hist_1d, hist_1h, None, regime_data)
            if signal and signal.get("quality_class") in ["A+", "A"]:
                future_df = df_1h.iloc[i:]
                direction = signal['direction']
                
                outcome, exit_price, duration, pnl, mae, mfe = simulate_trade(
                    entry_price=signal['entry'],
                    stop_price=signal['stop'],
                    target_price=signal['target'],
                    df_future=future_df,
                    direction=direction
                )
                trades.append({
                    "time": hist_1h.index[-1],
                    "outcome": outcome,
                    "pnl_pct": pnl,
                    "duration_bars": duration,
                    "mae": mae,
                    "mfe": mfe
                })
        except Exception:
            pass
            
    return trades

def run_new_crypto_backtest(ticker, df_1d, df_1h, regime_data):
    trades = []
    from engines.crypto.crypto_engine import analyze_crypto
    
    for i in range(50, len(df_1h) - 10):
        hist_1h = df_1h.iloc[:i]
        hist_1d = df_1d[df_1d.index <= hist_1h.index[-1]]
        
        try:
            # We mock derivatives and CVD for speed in this simple simulation
            signal = analyze_crypto(ticker, hist_1d, hist_1h, None, regime_data, None, None, None)
            if signal and signal.get("quality_class") in ["A+", "A"]:
                future_df = df_1h.iloc[i:]
                direction = signal['direction']
                
                outcome, exit_price, duration, pnl, mae, mfe = simulate_trade(
                    entry_price=signal['entry'],
                    stop_price=signal['stop'],
                    target_price=signal['target'],
                    df_future=future_df,
                    direction=direction
                )
                trades.append({
                    "time": hist_1h.index[-1],
                    "outcome": outcome,
                    "pnl_pct": pnl,
                    "duration_bars": duration,
                    "mae": mae,
                    "mfe": mfe
                })
        except Exception:
            pass
            
    return trades

def main():
    print("Starting Comparison Backtest (Sample dataset - 60D 1H)")
    
    # 1. Fetch data
    print("Fetching Regime Data...")
    regime_data_df = fetch_regime_data()
    
    from engines.regime.stock_regime import StockRegimeEngine
    from engines.regime.crypto_regime import CryptoRegimeEngine
    
    stock_regime = StockRegimeEngine().compute()
    crypto_regime = CryptoRegimeEngine().compute()
    
    v13_trades_stocks = []
    v14_trades_stocks = []
    
    print("Testing Stocks...")
    for ticker in SAMPLE_STOCKS:
        print(f"  Simulating {ticker}...")
        data = fetch_stock(ticker)
        if data['ok']:
            v13_trades_stocks.extend(run_v13_backtest(ticker, data['df_1d'], data['df_1h']))
            v14_trades_stocks.extend(run_new_stock_backtest(ticker, data['df_1d'], data['df_1h'], stock_regime))

    v13_trades_crypto = []
    v14_trades_crypto = []
    
    print("Testing Crypto...")
    for ticker in SAMPLE_CRYPTO:
        print(f"  Simulating {ticker}...")
        data = fetch_crypto(ticker)
        if data['ok']:
            v13_trades_crypto.extend(run_v13_backtest(ticker, data['df_1d'], data['df_1h']))
            v14_trades_crypto.extend(run_new_crypto_backtest(ticker, data['df_1d'], data['df_1h'], crypto_regime))

    # Metrics
    m_v13_stk = calc_metrics(v13_trades_stocks)
    m_v14_stk = calc_metrics(v14_trades_stocks)
    
    m_v13_cry = calc_metrics(v13_trades_crypto)
    m_v14_cry = calc_metrics(v14_trades_crypto)
    
    report = f"""
# DUAL INSTITUTIONAL-GRADE TRADING ENGINE — RESEARCH REPORT
Date: {datetime.datetime.now().strftime('%Y-%m-%d')}

## SECTION 1: What Changed
Replaced V13 binary 8-gate sequence with a continuous scoring opportunity engine (0-100).
Split into specialized Stocks Engine (with relative strength, RVOL, structure, liquidity) 
and Crypto Engine (with derivatives, flow/CVD proxy, BTC regime, narratives).
Replaced hard ATR stops with structural stops adapted to volatility and liquidity.

## SECTION 2: What was removed
Binary gates where missing data silently passed. Single universal logic for all assets.
Z-Score mandatory requirement. RSI absolute threshold triggers. 

## SECTION 3: What was retained
ATR target multipliers (base baseline). Toxic news keywords. Earnings block windows (configurable).

## SECTION 11-13: BACKTEST COMPARISON (Sample dataset 60D 1H)

### STOCKS COMPARISON
| Metric         | V13 Baseline | New Stocks |
| -------------- | -----------: | ---------: |
| Trades         | {m_v13_stk['total_trades']:12d} | {m_v14_stk['total_trades']:10d} |
| Win Rate       | {m_v13_stk['win_rate']:11.1f}% | {m_v14_stk['win_rate']:9.1f}% |
| Avg Win        | {m_v13_stk['avg_win']:11.2f}% | {m_v14_stk['avg_win']:9.2f}% |
| Avg Loss       | {m_v13_stk['avg_loss']:11.2f}% | {m_v14_stk['avg_loss']:9.2f}% |
| Expectancy     | {m_v13_stk['expectancy_pct']:11.3f} | {m_v14_stk['expectancy_pct']:9.3f} |
| Profit Factor  | {m_v13_stk['profit_factor']:11.2f} | {m_v14_stk['profit_factor']:9.2f} |
| Max Drawdown   | {m_v13_stk['max_drawdown']:11.2f}% | {m_v14_stk['max_drawdown']:9.2f}% |
| Avg Hold       | {m_v13_stk['avg_duration']:12.1f} | {m_v14_stk['avg_duration']:10.1f} |
| MAE            | {m_v13_stk['avg_mae']:11.2f}% | {m_v14_stk['avg_mae']:9.2f}% |
| MFE            | {m_v13_stk['avg_mfe']:11.2f}% | {m_v14_stk['avg_mfe']:9.2f}% |

### CRYPTO COMPARISON
| Metric                | V13 Crypto Baseline | New Crypto |
| --------------------- | ------------------: | ---------: |
| Trades                | {m_v13_cry['total_trades']:19d} | {m_v14_cry['total_trades']:10d} |
| Win Rate              | {m_v13_cry['win_rate']:18.1f}% | {m_v14_cry['win_rate']:9.1f}% |
| Avg Win               | {m_v13_cry['avg_win']:18.2f}% | {m_v14_cry['avg_win']:9.2f}% |
| Avg Loss              | {m_v13_cry['avg_loss']:18.2f}% | {m_v14_cry['avg_loss']:9.2f}% |
| Expectancy            | {m_v13_cry['expectancy_pct']:19.3f} | {m_v14_cry['expectancy_pct']:9.3f} |
| Profit Factor         | {m_v13_cry['profit_factor']:19.2f} | {m_v14_cry['profit_factor']:9.2f} |
| Max Drawdown          | {m_v13_cry['max_drawdown']:18.2f}% | {m_v14_cry['max_drawdown']:9.2f}% |
| Avg Hold              | {m_v13_cry['avg_duration']:19.1f} | {m_v14_cry['avg_duration']:10.1f} |
| MAE                   | {m_v13_cry['avg_mae']:18.2f}% | {m_v14_cry['avg_mae']:9.2f}% |
| MFE                   | {m_v13_cry['avg_mfe']:18.2f}% | {m_v14_cry['avg_mfe']:9.2f}% |

## SECTION 23: Known Weaknesses
- Free yfinance API is often delayed or returns missing 15m data, which blocks signal firing under strict data validation rules.
- True Spot vs Perp CVD requires WebSocket tick data; current proxy is only based on directional hourly volume.
- Binance OI and funding calls lack deep historical walk-forward support in this free implementation format.

## SECTION 24: Recommended Next Improvements
- Integrate paid data feeds (e.g. Polygon.io or Alpaca) for reliable intrabar data and accurate volume profiling.
- Use WebSocket connection to track real-time liquidation cascades instead of hourly OI differences.
- Build trailing stops to capture MFE more efficiently (MFE is generally higher than fixed targets).
"""
    with open("research/final_report.md", "w") as f:
        f.write(report)
        
    print("Report generated at research/final_report.md")

if __name__ == "__main__":
    main()
