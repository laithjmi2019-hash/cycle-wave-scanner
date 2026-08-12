import sys
import os
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

from engines.data_quality import validate_ohlcv
from engines.stocks.relative_strength import calc_rs_score
from engines.stocks.rvol import calc_rvol, rvol_score
from engines.stocks.structure import detect_structure
from engines.stocks.liquidity import get_key_levels, liquidity_score
from engines.stocks.catalyst import get_catalyst_score, has_earnings_soon

from engines.stocks.strategies.mean_reversion import evaluate as eval_mr
from engines.stocks.strategies.momentum_breakout import evaluate as eval_mb
from engines.stocks.strategies.pullback_continuation import evaluate as eval_pc
from engines.stocks.strategies.short_breakdown import evaluate as eval_short_bd
from engines.stocks.strategies.short_mean_reversion import evaluate as eval_short_mr

def analyze_stock(ticker: str, df_1d: pd.DataFrame, df_1h: pd.DataFrame, df_15m: pd.DataFrame, regime_data: dict) -> dict:
    try:
        is_valid, issues = validate_ohlcv(df_1h, ticker, 'US')
        if not is_valid:
            return None
            
        hard_veto = None
        if has_earnings_soon(ticker, config.EARNINGS_BLOCK_HOURS):
            hard_veto = 'Earnings soon'
            
        cat_data = get_catalyst_score(ticker)
        if cat_data.get('risk_score', 0) > 0:
            hard_veto = 'Toxic news detected'
            
        indicators = {}
        
        sig_mr = eval_mr(ticker, df_1d, df_1h, df_15m, regime_data, indicators)
        sig_mb = eval_mb(ticker, df_1d, df_1h, df_15m, regime_data, indicators)
        sig_pc = eval_pc(ticker, df_1d, df_1h, df_15m, regime_data, indicators)
        sig_sbd = eval_short_bd(ticker, df_1d, df_1h, df_15m, regime_data, indicators)
        sig_smr = eval_short_mr(ticker, df_1d, df_1h, df_15m, regime_data, indicators)
        
        valid_sigs = [s for s in [sig_mr, sig_mb, sig_pc, sig_sbd, sig_smr] if s is not None]
        if not valid_sigs:
            return None
            
        best_sig = sorted(valid_sigs, key=lambda x: x.get('total_score_contribution', 0), reverse=True)[0]
        
        rs_score = calc_rs_score({5: 1.05})
        
        rvol_val = calc_rvol(df_1h)
        rv_score = rvol_score(rvol_val)
        
        struct_data = detect_structure(df_1h)
        st_score = struct_data.get('score', 0)
        
        levels = get_key_levels(df_1d, df_1h)
        
        from ta.volatility import AverageTrueRange
        atr_ind = AverageTrueRange(high=df_1d['High'], low=df_1d['Low'], close=df_1d['Close'], window=14)
        atr = atr_ind.average_true_range().iloc[-1]
        lq_score = liquidity_score(best_sig['entry'], levels, atr)
        
        cat_score = cat_data.get('score', 0)
        
        reg_score = regime_data.get('score', 0) * (config.STOCK_SCORE_WEIGHTS['market_regime'] / 100.0)
        
        total_score = reg_score + rs_score + rv_score + st_score + lq_score + cat_score
        total_score = min(100.0, total_score)
        
        quality_class = 'C'
        for cls, thresh in config.SCORE_THRESHOLDS.items():
            if total_score >= thresh:
                quality_class = cls
                break
                
        risk_mult = config.QUALITY_RISK_MULT.get(quality_class, 0.0)
        pos_size = 0.0
        risk_per_unit = abs(best_sig['entry'] - best_sig['stop'])
        if risk_mult > 0 and risk_per_unit > 0:
            risk_amt = config.ACCOUNT_SIZE_USD * config.BASE_RISK_PCT * risk_mult
            pos_size = risk_amt / risk_per_unit
            
        return {
            'ticker': ticker,
            'asset_class': 'STOCKS',
            'market': 'US',
            'strategy': best_sig['strategy'],
            'direction': best_sig['direction'],
            'entry': best_sig['entry'],
            'stop': best_sig['stop'],
            'target': best_sig['target'],
            'rr': best_sig['rr'],
            'pos_size': pos_size,
            'total_score': round(total_score, 1),
            'quality_class': quality_class,
            'rsi': best_sig.get('rsi', 'N/A'),
            'adx': best_sig.get('adx', 'N/A'),
            'rvol': round(rvol_val, 1) if rvol_val else 'N/A',
            'structure': struct_data.get('trend', 'N/A'),
            'rs_vs_spy': 'N/A',
            'regime_class': regime_data.get('regime_class', ''),
            'sector': config.TICKER_SECTOR.get(ticker, ''),
            'breakdown': {
                'Regime':    {'score': round(reg_score, 1), 'max': config.STOCK_SCORE_WEIGHTS['market_regime']},
                'Rel Str':   {'score': round(rs_score, 1),  'max': config.STOCK_SCORE_WEIGHTS['relative_strength']},
                'RVOL':      {'score': round(rv_score, 1),  'max': config.STOCK_SCORE_WEIGHTS['participation']},
                'Structure': {'score': round(st_score, 1),  'max': config.STOCK_SCORE_WEIGHTS['price_structure']},
                'Liquidity': {'score': round(lq_score, 1),  'max': config.STOCK_SCORE_WEIGHTS['liquidity']},
                'Catalyst':  {'score': round(cat_score, 1), 'max': config.STOCK_SCORE_WEIGHTS['catalyst']},
            },
            'reason_top3': [
                f"Strategy: {best_sig['strategy']}",
                f"Regime: {regime_data.get('regime_class')}",
                f"RR: {best_sig['rr']:.2f}"
            ],
            'hard_veto': hard_veto,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception:
        return None
