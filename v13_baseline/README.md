# V13 Baseline Checkpoint

Preserved on: 2026-08-09
Win Rate: ~40.4% (backtested, 25 assets, 1Y hourly)
Expectancy: +0.213R/trade
R:R: 1:2.0

## Key V13 Characteristics
- 226 assets (US/EU/China/UAE/Crypto)
- 8-gate sequential engine (binary pass/fail)
- ADX regime detection (< 25 ranging, >= 25 trending)
- RSI Cross: was below 30, now 30-42
- EMA50 proximity (+/-3%)
- VWAP mandatory gate (daily reset)
- VIX < 25 block for US mean-reversion longs
- Daily 200 SMA macro filter (10% buffer)
- 15M RSI confirmation
- Earnings 72h block + NLP news filter
- 2 ATR stop / 4 ATR target
- Star rating system
- Signal outcome tracker (GitHub API)

## Run Baseline
    python v13_baseline/run_v13.py

## Compare vs New System
    python research/compare_engines.py
