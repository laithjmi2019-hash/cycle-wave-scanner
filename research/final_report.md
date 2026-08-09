
# DUAL INSTITUTIONAL-GRADE TRADING ENGINE — RESEARCH REPORT
Date: 2026-08-09

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
| Trades         |            0 |          0 |
| Win Rate       |         0.0% |       0.0% |
| Avg Win        |        0.00% |      0.00% |
| Avg Loss       |        0.00% |      0.00% |
| Expectancy     |       0.000 |     0.000 |
| Profit Factor  |        0.00 |      0.00 |
| Max Drawdown   |        0.00% |      0.00% |
| Avg Hold       |          0.0 |        0.0 |
| MAE            |        0.00% |      0.00% |
| MFE            |        0.00% |      0.00% |

### CRYPTO COMPARISON
| Metric                | V13 Crypto Baseline | New Crypto |
| --------------------- | ------------------: | ---------: |
| Trades                |                   0 |          0 |
| Win Rate              |                0.0% |       0.0% |
| Avg Win               |               0.00% |      0.00% |
| Avg Loss              |               0.00% |      0.00% |
| Expectancy            |               0.000 |     0.000 |
| Profit Factor         |                0.00 |      0.00 |
| Max Drawdown          |               0.00% |      0.00% |
| Avg Hold              |                 0.0 |        0.0 |
| MAE                   |               0.00% |      0.00% |
| MFE                   |               0.00% |      0.00% |

## SECTION 23: Known Weaknesses
- Free yfinance API is often delayed or returns missing 15m data, which blocks signal firing under strict data validation rules.
- True Spot vs Perp CVD requires WebSocket tick data; current proxy is only based on directional hourly volume.
- Binance OI and funding calls lack deep historical walk-forward support in this free implementation format.

## SECTION 24: Recommended Next Improvements
- Integrate paid data feeds (e.g. Polygon.io or Alpaca) for reliable intrabar data and accurate volume profiling.
- Use WebSocket connection to track real-time liquidation cascades instead of hourly OI differences.
- Build trailing stops to capture MFE more efficiently (MFE is generally higher than fixed targets).
