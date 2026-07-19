import pandas as pd
import numpy as np
import ta

# ─────────────────────────────────────────────────────────────────
# CORE INDICATORS (shared by all analyzers)
# ─────────────────────────────────────────────────────────────────
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all indicators without lookahead bias."""
    df = df.copy()

    # RSI & StochRSI
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    stoch_rsi = ta.momentum.StochRSIIndicator(df['Close'], window=14, smooth1=3, smooth2=3)
    df['stoch_rsi_k'] = stoch_rsi.stochrsi_k() * 100
    df['stoch_rsi_d'] = stoch_rsi.stochrsi_d() * 100

    # FIX 6: MACD is now computed AND wired in as a confirmation signal
    macd = ta.trend.MACD(df['Close'])
    df['macd_diff']       = macd.macd_diff()       # histogram (momentum)
    df['macd_diff_prev']  = df['macd_diff'].shift(1)

    # EMAs: Fast (9/21) + Macro (50/200)
    df['ema_9']   = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
    df['ema_21']  = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
    df['ema_50']  = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
    df['ema_200'] = ta.trend.EMAIndicator(df['Close'], window=200).ema_indicator()

    # ATR (volatility) — FIX 9: removed unused atr_14
    df['atr_10'] = ta.volatility.AverageTrueRange(
        df['High'], df['Low'], df['Close'], window=10).average_true_range()

    # ── BULLISH FVG ────────────────────────────────────────────────
    # FIX 4: limit raised from 5 → 20 candles (~20h on 1H chart)
    df['fvg_bull_gap_low']  = df['High'].shift(2)
    df['fvg_bull_gap_high'] = df['Low']
    df['is_bull_fvg']       = df['fvg_bull_gap_high'] > df['fvg_bull_gap_low']
    df['active_bull_fvg_top']    = df['fvg_bull_gap_high'].where(df['is_bull_fvg']).ffill(limit=20).shift(1)
    df['active_bull_fvg_bottom'] = df['fvg_bull_gap_low'].where(df['is_bull_fvg']).ffill(limit=20).shift(1)
    df['tapping_bull_fvg'] = (
        (df['Low']   <= df['active_bull_fvg_top']) &
        (df['Close'] >= df['active_bull_fvg_bottom'])
    )

    # ── BEARISH FVG ────────────────────────────────────────────────
    # FIX 4: limit raised from 5 → 20 candles
    df['fvg_bear_gap_high'] = df['Low'].shift(2)
    df['fvg_bear_gap_low']  = df['High']
    df['is_bear_fvg']       = df['fvg_bear_gap_low'] < df['fvg_bear_gap_high']
    df['active_bear_fvg_bottom'] = df['fvg_bear_gap_low'].where(df['is_bear_fvg']).ffill(limit=20).shift(1)
    df['active_bear_fvg_top']    = df['fvg_bear_gap_high'].where(df['is_bear_fvg']).ffill(limit=20).shift(1)
    df['tapping_bear_fvg'] = (
        (df['High']  >= df['active_bear_fvg_bottom']) &
        (df['Close'] <= df['active_bear_fvg_top'])
    )

    # ── CANDLESTICK PATTERNS ───────────────────────────────────────
    df['body_size']   = abs(df['Close'] - df['Open'])
    df['total_range'] = df['High'] - df['Low']
    df['lower_wick']  = df[['Close', 'Open']].min(axis=1) - df['Low']
    df['upper_wick']  = df['High'] - df[['Close', 'Open']].max(axis=1)

    # Bullish Pin Bar
    df['is_pin_bar'] = (
        (df['lower_wick'] >= 2 * df['body_size']) &
        (df[['Close', 'Open']].max(axis=1) >= df['High'] - 0.33 * df['total_range']) &
        (df['total_range'] > 0)
    )

    # Bearish Pin Bar (shooting star)
    df['is_bear_pin_bar'] = (
        (df['upper_wick'] >= 2 * df['body_size']) &
        (df[['Close', 'Open']].min(axis=1) <= df['Low'] + 0.33 * df['total_range']) &
        (df['total_range'] > 0)
    )

    prev_open  = df['Open'].shift(1)
    prev_close = df['Close'].shift(1)
    vol_ma20   = df['Volume'].rolling(20).mean()

    # Bullish Engulfing (Volume-confirmed for equities)
    df['is_engulfing'] = (
        (df['Close'] > df['Open']) &
        (prev_open > prev_close) &
        (df['Close'] >= prev_open) &
        (df['Open']  <= prev_close) &
        (df['Volume'] > vol_ma20)
    )

    # Bearish Engulfing (Volume-confirmed for equities)
    df['is_bear_engulfing'] = (
        (df['Close'] < df['Open']) &
        (prev_open < prev_close) &
        (df['Close'] <= prev_open) &
        (df['Open']  >= prev_close) &
        (df['Volume'] > vol_ma20)
    )

    # Bullish Engulfing (Range expansion for crypto)
    df['is_engulfing_pa'] = (
        (df['Close'] > df['Open']) &
        (prev_open > prev_close) &
        (df['Close'] >= prev_open) &
        (df['Open']  <= prev_close) &
        (df['body_size'] > 1.5 * df['atr_10'].shift(1))
    )

    # Bearish Engulfing (Range expansion for crypto)
    df['is_bear_engulfing_pa'] = (
        (df['Close'] < df['Open']) &
        (prev_open < prev_close) &
        (df['Close'] <= prev_open) &
        (df['Open']  >= prev_close) &
        (df['body_size'] > 1.5 * df['atr_10'].shift(1))
    )

    return df


# ─────────────────────────────────────────────────────────────────
# DIVERGENCE DETECTION  (Bullish + Bearish, no lookahead)
# FIX 5: lookback raised from 20 → 45 candles for deeper divergences
# ─────────────────────────────────────────────────────────────────
def detect_divergence(df: pd.DataFrame, lookback: int = 45) -> str:
    if len(df) < lookback + 1:
        return "None"
    recent      = df.iloc[-lookback:]
    current_idx = df.index[-1]
    rsi_min_idx = recent['rsi'].idxmin()
    rsi_max_idx = recent['rsi'].idxmax()

    # Bullish: price makes Lower Low, RSI makes Higher Low
    if df['Low'].iloc[-1] <= recent['Low'].min() * 1.01:
        if rsi_min_idx != current_idx and df['rsi'].iloc[-1] > df.loc[rsi_min_idx, 'rsi']:
            return "Bullish"

    # Bearish: price makes Higher High, RSI makes Lower High
    if df['High'].iloc[-1] >= recent['High'].max() * 0.99:
        if rsi_max_idx != current_idx and df['rsi'].iloc[-1] < df.loc[rsi_max_idx, 'rsi']:
            return "Bearish"

    return "None"


# ─────────────────────────────────────────────────────────────────
# FIX 6: MACD CONFLUENCE CHECKER
# Returns True if MACD histogram is rising (bullish momentum) or
# falling (bearish momentum), confirming the direction of a signal.
# ─────────────────────────────────────────────────────────────────
def _macd_confirms_long(row) -> bool:
    """MACD histogram is positive and rising — confirms bullish momentum."""
    return (pd.notna(row['macd_diff']) and pd.notna(row['macd_diff_prev']) and
            row['macd_diff'] > 0 and row['macd_diff'] > row['macd_diff_prev'])

def _macd_confirms_short(row) -> bool:
    """MACD histogram is negative and falling — confirms bearish momentum."""
    return (pd.notna(row['macd_diff']) and pd.notna(row['macd_diff_prev']) and
            row['macd_diff'] < 0 and row['macd_diff'] < row['macd_diff_prev'])


# ─────────────────────────────────────────────────────────────────
# FIX 1 & 2: RISK-TO-REWARD CALCULATOR (signed-aware, safe scope)
# ─────────────────────────────────────────────────────────────────
def _calc_rr(entry: float, stop: float, target: float, is_short: bool = False):
    """
    Returns (rr_ratio, upside_str, downside_str, rr_str, rr_ok).
    FIX 1: now correctly handles short trade direction.
    rr_ok is True when R:R >= 1.5
    """
    if is_short:
        # For shorts: reward = entry - target, risk = stop - entry
        reward = entry  - target
        risk   = stop   - entry
    else:
        reward = target - entry
        risk   = entry  - stop

    if risk <= 0 or reward <= 0:
        return 0, "N/A", "N/A", "N/A", False

    rr           = reward / risk
    move_pct     = (reward / entry) * 100
    risk_pct     = (risk   / entry) * 100

    direction    = "-" if is_short else "+"
    upside_str   = f"{direction}{round(move_pct, 2)}%"
    downside_str = f"-{round(risk_pct, 2)}%"
    rr_str       = f"1:{round(rr, 1)}"

    return round(rr, 2), upside_str, downside_str, rr_str, rr >= 1.5


# ─────────────────────────────────────────────────────────────────
# EQUITY ANALYZER
# ─────────────────────────────────────────────────────────────────
def analyze_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame,
                  data_15m: pd.DataFrame, spy_1d: pd.DataFrame) -> dict:
    """
    Full 3-TF Sniper engine for US Equities.
    Fixes applied: 1 (short R:R), 2 (scope), 3 (prepost), 4 (FVG limit),
                   5 (divergence lookback), 6 (MACD confirmation)
    """
    # FIX 2: initialise all output variables at top of function scope
    upside_str   = "N/A"
    rr_str       = "N/A"
    stop         = None

    EMPTY = {"ticker": ticker, "recommendation": "AVOID", "upside": "N/A",
             "stop_loss": "N/A", "rr": "N/A", "signal": "Avoid",
             "score": 0, "reason": "Insufficient Data",
             "trend_1d": "N/A", "div_1h": "N/A",
             "fvg_tap": False, "pa_trigger": False, "current_price": 0}

    df_1d  = calculate_indicators(data_1d).dropna()
    df_1h  = calculate_indicators(data_1h).dropna()
    df_15m = calculate_indicators(data_15m).dropna()

    if df_1d.empty or df_1h.empty or df_15m.empty:
        return EMPTY

    curr_1d  = df_1d.iloc[-1]
    curr_1h  = df_1h.iloc[-1]
    curr_15m = df_15m.iloc[-1]

    trend_1d      = "UP" if curr_1d['ema_9'] > curr_1d['ema_21'] else "DOWN"
    daily_rsi     = curr_1d['rsi']
    is_overbought = daily_rsi > 75
    is_oversold   = daily_rsi < 30

    spy_df    = calculate_indicators(spy_1d).dropna()
    spy_trend = "UP" if (not spy_df.empty and spy_df.iloc[-1]['ema_9'] > spy_df.iloc[-1]['ema_21']) else "DOWN"

    div_1h = detect_divergence(df_1h)

    # FIX 6: MACD confirmation on 1H
    macd_bull = _macd_confirms_long(curr_1h)
    macd_bear = _macd_confirms_short(curr_1h)

    # Bullish triggers
    tap_bull_fvg_1h  = bool(curr_1h['tapping_bull_fvg'])
    pin_bar_15m      = bool(curr_15m['is_pin_bar'])
    engulf_bull_15m  = bool(curr_15m['is_engulfing'])
    bull_trigger_15m = pin_bar_15m or engulf_bull_15m

    # Bearish triggers
    tap_bear_fvg_1h  = bool(curr_1h['tapping_bear_fvg'])
    bear_pin_15m     = bool(curr_15m['is_bear_pin_bar'])
    engulf_bear_15m  = bool(curr_15m['is_bear_engulfing'])
    bear_trigger_15m = bear_pin_15m or engulf_bear_15m

    score      = 50
    signal     = "Avoid"
    reason     = []
    rec        = "AVOID"
    pa_trigger = bull_trigger_15m
    fvg_tap    = tap_bull_fvg_1h

    entry  = curr_15m['Close']
    atr_1h = curr_1h['atr_10']

    is_short_setup = (
        trend_1d == "DOWN" and
        div_1h == "Bearish" and
        (tap_bear_fvg_1h or bear_trigger_15m) and
        not is_oversold
    )

    is_bull_setup = (
        trend_1d == "UP" and
        div_1h == "Bullish" and
        (tap_bull_fvg_1h or bull_trigger_15m) and
        not is_overbought
    )

    if is_bull_setup:
        signal = "Good Entry"
        score  = 95
        # FIX 6: MACD confirmation adds +3 conviction
        if macd_bull:
            score += 3
            reason.append("MACD Hist rising — momentum confirmed.")
        trig = []
        if tap_bull_fvg_1h: trig.append("1H FVG Tap")
        if pin_bar_15m:     trig.append("15m Pin Bar")
        if engulf_bull_15m: trig.append("15m Engulfing")
        reason.append(f"LONG Confluence: 1D Fast UP + 1H Bull Div + {' + '.join(trig)}.")
        rec = "STRONG BUY"

        fvg_bottom = curr_1h.get('active_bull_fvg_bottom', entry - atr_1h)
        stop   = (fvg_bottom if pd.notna(fvg_bottom) else entry) - atr_1h
        target = max(df_1h['High'].rolling(20).max().iloc[-1], entry + 2.5 * atr_1h)
        # FIX 1: is_short=False for long trades
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=False)

        if not rr_ok:
            signal = "Trend Up"; score = 65; rec = "WAIT FOR DIP"
            reason.append(f"R:R REJECTED ({rr_str}). Wait for deeper pull-back.")
            upside_str = rr_str = "N/A"; stop = None

    elif is_short_setup:
        signal = "Short Setup"; score = 90; rec = "STRONG SHORT"
        # FIX 6: MACD confirmation adds +3 conviction
        if macd_bear:
            score += 3
            reason.append("MACD Hist falling — bearish momentum confirmed.")
        trig = []
        if tap_bear_fvg_1h: trig.append("1H Bear FVG Tap")
        if bear_pin_15m:    trig.append("15m Bear Pin")
        if engulf_bear_15m: trig.append("15m Bear Engulfing")
        reason.append(f"SHORT Confluence: 1D Fast DOWN + 1H Bear Div + {' + '.join(trig)}.")

        stop   = entry + atr_1h
        target = min(df_1h['Low'].rolling(20).min().iloc[-1], entry - 2.5 * atr_1h)
        # FIX 1: is_short=True so reward/risk are sign-correct
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=True)

        if not rr_ok:
            signal = "Trend Down"; score = 35; rec = "AVOID"
            reason.append(f"Short R:R REJECTED ({rr_str}).")
            upside_str = rr_str = "N/A"; stop = None

    elif trend_1d == "UP":
        if is_overbought:
            reason.append(f"EXHAUSTION VETO: 1D RSI={round(daily_rsi,1)} (>75). Do NOT buy extended markets.")
            signal = "Avoid"; score = 20; rec = "AVOID"
        else:
            signal = "Trend Up"; score = 60; rec = "WAIT FOR DIP"
            reason.append("1D Fast Uptrend active. Awaiting 1H divergence + 15m execution trigger.")
        stop = None

    else:
        if is_oversold:
            reason.append(f"Oversold Alert: 1D RSI={round(daily_rsi,1)} (<30). Watch for bullish reversal trigger.")
            score = 35
        else:
            score = 25
            reason.append("1D Downtrend. Avoid longs. Monitor for Short Setup.")
        signal = "Trend Down"; rec = "AVOID"; stop = None

    # SPY Macro Breadth Penalty
    if spy_trend == "DOWN" and signal in ["Good Entry", "Trend Up"]:
        score -= 20
        reason.append("SPY Macro Penalty: Market breadth is bearish.")
        if signal == "Good Entry":
            signal = "Avoid"; rec = "AVOID"
            reason.append("LONG invalidated by bearish SPY macro.")

    score    = max(0, min(100, score))
    stop_str = f"${round(stop, 2)}" if stop is not None and pd.notna(stop) else "N/A"

    return {
        "ticker":         ticker,
        "recommendation": rec,
        "upside":         upside_str,
        "stop_loss":      stop_str,
        "rr":             rr_str,
        "signal":         signal,
        "score":          score,
        "reason":         " ".join(reason),
        "trend_1d":       trend_1d,
        "div_1h":         div_1h,
        "fvg_tap":        fvg_tap,
        "pa_trigger":     pa_trigger,
        "current_price":  round(entry, 4)
    }


# ─────────────────────────────────────────────────────────────────
# CRYPTO ANALYZER (MTF Sniper — same 6 fixes applied)
# ─────────────────────────────────────────────────────────────────
def analyze_crypto_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame,
                         data_15m: pd.DataFrame, btc_1d: pd.DataFrame) -> dict:
    """
    Full MTF Sniper engine for Crypto.
    All 6 fixes applied identically to the equity analyzer.
    """
    # FIX 2: initialise output variables at top of function scope
    upside_str = "N/A"
    rr_str     = "N/A"
    stop       = None

    EMPTY = {"ticker": ticker, "recommendation": "AVOID", "upside": "N/A",
             "stop_loss": "N/A", "rr": "N/A", "signal": "Avoid",
             "score": 0, "reason": "Insufficient Data",
             "trend_1d": "N/A", "div_1h": "N/A",
             "fvg_tap": False, "pa_trigger": False, "current_price": 0}

    df_1d  = calculate_indicators(data_1d).dropna()
    df_1h  = calculate_indicators(data_1h).dropna()
    df_15m = calculate_indicators(data_15m).dropna()

    if df_1d.empty or df_1h.empty or df_15m.empty:
        return EMPTY

    curr_1d  = df_1d.iloc[-1]
    curr_1h  = df_1h.iloc[-1]
    curr_15m = df_15m.iloc[-1]

    trend_1d      = "UP" if curr_1d['ema_9'] > curr_1d['ema_21'] else "DOWN"
    daily_rsi     = curr_1d['rsi']
    is_overbought = daily_rsi > 75
    is_oversold   = daily_rsi < 30

    btc_df    = calculate_indicators(btc_1d).dropna()
    btc_trend = "UP" if (not btc_df.empty and btc_df.iloc[-1]['ema_9'] > btc_df.iloc[-1]['ema_21']) else "DOWN"

    div_1h = detect_divergence(df_1h)

    # FIX 6: MACD confirmation on 1H
    macd_bull = _macd_confirms_long(curr_1h)
    macd_bear = _macd_confirms_short(curr_1h)

    # Bullish triggers
    tap_bull_fvg   = bool(curr_1h['tapping_bull_fvg'])
    pin_bar_15m    = bool(curr_15m['is_pin_bar'])
    engulf_15m     = bool(curr_15m['is_engulfing_pa'])
    bull_trig_15m  = pin_bar_15m or engulf_15m

    # Bearish triggers
    tap_bear_fvg    = bool(curr_1h['tapping_bear_fvg'])
    bear_pin_15m    = bool(curr_15m['is_bear_pin_bar'])
    bear_engulf_15m = bool(curr_15m['is_bear_engulfing_pa'])
    bear_trig_15m   = bear_pin_15m or bear_engulf_15m

    entry  = curr_15m['Close']
    atr_1h = curr_1h['atr_10']

    score  = 50
    signal = "Avoid"
    rec    = "AVOID"
    reason = []

    is_bull_setup = (
        trend_1d == "UP" and
        ((div_1h == "Bullish") or tap_bull_fvg) and
        bull_trig_15m and
        not is_overbought
    )

    is_short_setup = (
        trend_1d == "DOWN" and
        div_1h == "Bearish" and
        (tap_bear_fvg or bear_trig_15m) and
        not is_oversold
    )

    if is_bull_setup:
        signal = "Good Entry"; score = 95; rec = "STRONG BUY"
        if macd_bull:
            score += 3
            reason.append("MACD Hist rising — momentum confirmed.")
        setup = []
        trig  = []
        if div_1h == "Bullish": setup.append("1H Bull Div")
        if tap_bull_fvg:        setup.append("1H FVG Tap")
        if pin_bar_15m:         trig.append("15m Pin Bar")
        if engulf_15m:          trig.append("15m Engulfing")
        reason.append(f"MTF LONG: 1D Fast UP + {' & '.join(setup)} + Sniper {' + '.join(trig)}.")

        fvg_bottom = curr_1h.get('active_bull_fvg_bottom', entry - atr_1h)
        stop   = (fvg_bottom if pd.notna(fvg_bottom) else entry) - atr_1h
        target = max(df_1h['High'].rolling(20).max().iloc[-1], entry + 2.5 * atr_1h)
        # FIX 1: is_short=False
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=False)

        if not rr_ok:
            signal = "Trend Up"; score = 65; rec = "WAIT FOR DIP"
            reason.append(f"R:R REJECTED ({rr_str}). Wait for deeper pull-back into FVG.")
            upside_str = rr_str = "N/A"; stop = None

    elif is_short_setup:
        signal = "Short Setup"; score = 90; rec = "STRONG SHORT"
        if macd_bear:
            score += 3
            reason.append("MACD Hist falling — bearish momentum confirmed.")
        trig = []
        if tap_bear_fvg:    trig.append("1H Bear FVG Tap")
        if bear_pin_15m:    trig.append("15m Bear Pin")
        if bear_engulf_15m: trig.append("15m Bear Engulfing")
        reason.append(f"MTF SHORT: 1D Fast DOWN + 1H Bear Div + {' + '.join(trig)}.")

        stop   = entry + atr_1h
        target = min(df_1h['Low'].rolling(20).min().iloc[-1], entry - 2.5 * atr_1h)
        # FIX 1: is_short=True so math is sign-correct
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=True)

        if not rr_ok:
            signal = "Trend Down"; score = 35; rec = "AVOID"
            reason.append(f"Short R:R REJECTED ({rr_str}).")
            upside_str = rr_str = "N/A"; stop = None

    elif trend_1d == "UP":
        if is_overbought:
            signal = "Avoid"; score = 20; rec = "AVOID"
            reason.append(f"EXHAUSTION VETO: 1D RSI={round(daily_rsi,1)} (>75). Market too extended.")
        else:
            signal = "Trend Up"; score = 60; rec = "WAIT FOR DIP"
            reason.append("1D Fast Uptrend active. Awaiting 15m execution trigger inside 1H setup zone.")
        stop = None

    else:
        if is_oversold:
            reason.append(f"Capitulation Watch: 1D RSI={round(daily_rsi,1)}. Possible bottom formation.")
            score = 35
        else:
            score = 25
            reason.append("1D Downtrend. Avoid longs.")
        signal = "Trend Down"; rec = "AVOID"; stop = None

    # BTC Macro Filter
    if btc_trend == "DOWN" and signal in ["Good Entry", "Trend Up"]:
        score -= 25
        reason.append("BTC Macro Penalty: Bitcoin 1D is DOWN.")
        if signal == "Good Entry":
            signal = "Avoid"; rec = "AVOID"
            reason.append("LONG invalidated by bearish BTC macro.")

    score    = max(0, min(100, score))
    stop_str = f"${round(stop, 4)}" if stop is not None and pd.notna(stop) else "N/A"

    return {
        "ticker":         ticker,
        "recommendation": rec,
        "upside":         upside_str,
        "stop_loss":      stop_str,
        "rr":             rr_str,
        "signal":         signal,
        "score":          score,
        "reason":         " ".join(reason),
        "trend_1d":       trend_1d,
        "div_1h":         div_1h,
        "fvg_tap":        tap_bull_fvg,
        "pa_trigger":     bull_trig_15m,
        "current_price":  round(entry, 4)
    }
