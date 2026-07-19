import pandas as pd
import ta

# ─────────────────────────────────────────────────────────────────
# CORE INDICATORS (shared by all analyzers)
# ─────────────────────────────────────────────────────────────────
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all indicators without lookahead bias."""
    df = df.copy()

    # RSI (primary momentum oscillator)
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()

    # StochRSI — now wired into exhaustion detection
    stoch_rsi = ta.momentum.StochRSIIndicator(df['Close'], window=14, smooth1=3, smooth2=3)
    df['stoch_rsi_k'] = stoch_rsi.stochrsi_k() * 100
    df['stoch_rsi_d'] = stoch_rsi.stochrsi_d() * 100

    # MACD histogram — confirmation signal
    macd = ta.trend.MACD(df['Close'])
    df['macd_diff']      = macd.macd_diff()
    df['macd_diff_prev'] = df['macd_diff'].shift(1)

    # EMAs: Fast (9/21) + Macro (50/200)
    df['ema_9']   = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
    df['ema_21']  = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
    df['ema_50']  = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
    df['ema_200'] = ta.trend.EMAIndicator(df['Close'], window=200).ema_indicator()

    # ATR — volatility / stop / target sizing
    df['atr_10'] = ta.volatility.AverageTrueRange(
        df['High'], df['Low'], df['Close'], window=10).average_true_range()

    # Volume MA — institutional engulfing confirmation
    df['vol_ma20'] = df['Volume'].rolling(20).mean()

    # ── BULLISH FVG (3-candle imbalance: Low[t] > High[t-2]) ──────
    df['fvg_bull_gap_low']  = df['High'].shift(2)
    df['fvg_bull_gap_high'] = df['Low']
    df['is_bull_fvg']       = df['fvg_bull_gap_high'] > df['fvg_bull_gap_low']
    df['active_bull_fvg_top']    = df['fvg_bull_gap_high'].where(df['is_bull_fvg']).ffill(limit=20).shift(1)
    df['active_bull_fvg_bottom'] = df['fvg_bull_gap_low'].where(df['is_bull_fvg']).ffill(limit=20).shift(1)
    df['tapping_bull_fvg'] = (
        (df['Low']   <= df['active_bull_fvg_top']) &
        (df['Close'] >= df['active_bull_fvg_bottom'])
    )

    # ── BEARISH FVG (3-candle imbalance: High[t] < Low[t-2]) ──────
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

    # Bullish Pin Bar (hammer)
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

    # Bullish Engulfing — volume-confirmed (equities)
    df['is_engulfing'] = (
        (df['Close'] > df['Open']) &
        (prev_open > prev_close) &
        (df['Close'] >= prev_open) &
        (df['Open']  <= prev_close) &
        (df['Volume'] > df['vol_ma20'])
    )

    # Bearish Engulfing — volume-confirmed (equities)
    df['is_bear_engulfing'] = (
        (df['Close'] < df['Open']) &
        (prev_open < prev_close) &
        (df['Close'] <= prev_open) &
        (df['Open']  >= prev_close) &
        (df['Volume'] > df['vol_ma20'])
    )

    # Bullish Engulfing — ATR range expansion (crypto, no volume reliance)
    df['is_engulfing_pa'] = (
        (df['Close'] > df['Open']) &
        (prev_open > prev_close) &
        (df['Close'] >= prev_open) &
        (df['Open']  <= prev_close) &
        (df['body_size'] > 1.5 * df['atr_10'].shift(1))
    )

    # Bearish Engulfing — ATR range expansion (crypto)
    df['is_bear_engulfing_pa'] = (
        (df['Close'] < df['Open']) &
        (prev_open < prev_close) &
        (df['Close'] <= prev_open) &
        (df['Open']  >= prev_close) &
        (df['body_size'] > 1.5 * df['atr_10'].shift(1))
    )

    return df


# ─────────────────────────────────────────────────────────────────
# DIVERGENCE DETECTION (no lookahead, lookback=45 candles)
# ─────────────────────────────────────────────────────────────────
def detect_divergence(df: pd.DataFrame, lookback: int = 45) -> str:
    if len(df) < lookback + 1:
        return "None"
    recent      = df.iloc[-lookback:]
    current_idx = df.index[-1]
    rsi_min_idx = recent['rsi'].idxmin()
    rsi_max_idx = recent['rsi'].idxmax()

    # Bullish: price Lower Low, RSI Higher Low
    if df['Low'].iloc[-1] <= recent['Low'].min() * 1.01:
        if rsi_min_idx != current_idx and df['rsi'].iloc[-1] > df.loc[rsi_min_idx, 'rsi']:
            return "Bullish"

    # Bearish: price Higher High, RSI Lower High
    if df['High'].iloc[-1] >= recent['High'].max() * 0.99:
        if rsi_max_idx != current_idx and df['rsi'].iloc[-1] < df.loc[rsi_max_idx, 'rsi']:
            return "Bearish"

    return "None"


# ─────────────────────────────────────────────────────────────────
# MACD CONFLUENCE HELPERS
# ─────────────────────────────────────────────────────────────────
def _macd_confirms_long(row) -> bool:
    return (pd.notna(row['macd_diff']) and pd.notna(row['macd_diff_prev']) and
            row['macd_diff'] > 0 and row['macd_diff'] > row['macd_diff_prev'])

def _macd_confirms_short(row) -> bool:
    return (pd.notna(row['macd_diff']) and pd.notna(row['macd_diff_prev']) and
            row['macd_diff'] < 0 and row['macd_diff'] < row['macd_diff_prev'])

# StochRSI — secondary exhaustion checks (wired in, not dead code)
def _stoch_overbought(row) -> bool:
    return pd.notna(row['stoch_rsi_k']) and row['stoch_rsi_k'] > 80

def _stoch_oversold(row) -> bool:
    return pd.notna(row['stoch_rsi_k']) and row['stoch_rsi_k'] < 20


# ─────────────────────────────────────────────────────────────────
# RISK-TO-REWARD CALCULATOR (signed-aware)
# ─────────────────────────────────────────────────────────────────
def _calc_rr(entry: float, stop: float, target: float, is_short: bool = False):
    if is_short:
        reward = entry - target
        risk   = stop  - entry
    else:
        reward = target - entry
        risk   = entry  - stop

    if risk <= 0 or reward <= 0:
        return 0, "N/A", "N/A", "N/A", False

    rr        = reward / risk
    move_pct  = (reward / entry) * 100
    risk_pct  = (risk   / entry) * 100
    direction = "-" if is_short else "+"

    return (
        round(rr, 2),
        f"{direction}{round(move_pct, 2)}%",
        f"-{round(risk_pct, 2)}%",
        f"1:{round(rr, 1)}",
        rr >= 1.5
    )


# ─────────────────────────────────────────────────────────────────
# EQUITY ANALYZER — Full 3-TF MTF Sniper
# ─────────────────────────────────────────────────────────────────
def analyze_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame,
                  data_15m: pd.DataFrame, spy_1d: pd.DataFrame) -> dict:
    # Safe defaults — no scope bugs
    upside_str = "N/A"
    rr_str     = "N/A"
    stop       = None

    EMPTY = {"ticker": ticker, "recommendation": "AVOID", "upside": "N/A",
             "stop_loss": "N/A", "rr": "N/A", "signal": "Avoid", "score": 0,
             "reason": "Insufficient Data", "trend_1d": "N/A", "div_1h": "N/A",
             "rsi_1d": "N/A", "stoch_1h": "N/A", "macd_conf": "N/A",
             "fvg_tap": False, "pa_trigger": False, "current_price": 0}

    df_1d  = calculate_indicators(data_1d).dropna()
    df_1h  = calculate_indicators(data_1h).dropna()
    df_15m = calculate_indicators(data_15m).dropna()

    if df_1d.empty or df_1h.empty or df_15m.empty:
        return EMPTY

    curr_1d  = df_1d.iloc[-1]
    curr_1h  = df_1h.iloc[-1]
    curr_15m = df_15m.iloc[-1]

    # ── TREND & MOMENTUM ──────────────────────────────────────────
    trend_1d      = "UP" if curr_1d['ema_9'] > curr_1d['ema_21'] else "DOWN"
    daily_rsi     = curr_1d['rsi']
    # StochRSI on 1H for secondary exhaustion — now properly wired
    stoch_ob_1h   = _stoch_overbought(curr_1h)
    stoch_os_1h   = _stoch_oversold(curr_1h)
    # Combined exhaustion: Daily RSI OR 1H StochRSI both overbought
    is_overbought = (daily_rsi > 75) or (daily_rsi > 68 and stoch_ob_1h)
    is_oversold   = (daily_rsi < 30) or (daily_rsi < 35 and stoch_os_1h)

    spy_df    = calculate_indicators(spy_1d).dropna()
    spy_trend = "UP" if (not spy_df.empty and spy_df.iloc[-1]['ema_9'] > spy_df.iloc[-1]['ema_21']) else "DOWN"

    div_1h    = detect_divergence(df_1h)
    macd_bull = _macd_confirms_long(curr_1h)
    macd_bear = _macd_confirms_short(curr_1h)

    # ── LIQUIDITY TRIGGERS ────────────────────────────────────────
    tap_bull_fvg_1h  = bool(curr_1h['tapping_bull_fvg'])
    pin_bar_15m      = bool(curr_15m['is_pin_bar'])
    engulf_bull_15m  = bool(curr_15m['is_engulfing'])
    bull_trigger_15m = pin_bar_15m or engulf_bull_15m

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
    entry      = curr_15m['Close']
    atr_1h     = curr_1h['atr_10']

    is_short_setup = (
        trend_1d == "DOWN" and div_1h == "Bearish" and
        (tap_bear_fvg_1h or bear_trigger_15m) and not is_oversold
    )
    is_bull_setup = (
        trend_1d == "UP" and div_1h == "Bullish" and
        (tap_bull_fvg_1h or bull_trigger_15m) and not is_overbought
    )

    if is_bull_setup:
        signal = "Good Entry"; score = 95; rec = "STRONG BUY"
        if macd_bull:
            score += 3
            reason.append("MACD Hist rising — momentum confirmed.")
        trig = []
        if tap_bull_fvg_1h: trig.append("1H FVG Tap")
        if pin_bar_15m:     trig.append("15m Pin Bar")
        if engulf_bull_15m: trig.append("15m Engulfing")
        reason.append(f"LONG Confluence: 1D Fast UP + 1H Bull Div + {' + '.join(trig)}.")

        fvg_bottom = curr_1h.get('active_bull_fvg_bottom', entry - atr_1h)
        stop   = (fvg_bottom if pd.notna(fvg_bottom) else entry) - atr_1h
        target = max(df_1h['High'].rolling(20).max().iloc[-1], entry + 2.5 * atr_1h)
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=False)

        if not rr_ok:
            signal = "Trend Up"; score = 65; rec = "WAIT FOR DIP"
            reason.append(f"R:R REJECTED ({rr_str}). Wait for deeper pull-back.")
            upside_str = rr_str = "N/A"; stop = None

    elif is_short_setup:
        signal = "Short Setup"; score = 90; rec = "STRONG SHORT"
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
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=True)

        if not rr_ok:
            signal = "Trend Down"; score = 35; rec = "AVOID"
            reason.append(f"Short R:R REJECTED ({rr_str}).")
            upside_str = rr_str = "N/A"; stop = None

    elif trend_1d == "UP":
        if is_overbought:
            reason.append(f"EXHAUSTION VETO: 1D RSI={round(daily_rsi,1)}, 1H StochRSI={'OB' if stoch_ob_1h else 'OK'}. Do NOT buy extended markets.")
            signal = "Avoid"; score = 20; rec = "AVOID"
        else:
            signal = "Trend Up"; score = 60; rec = "WAIT FOR DIP"
            reason.append("1D Fast Uptrend active. Awaiting 1H divergence + 15m execution trigger.")
        stop = None
    else:
        if is_oversold:
            reason.append(f"Oversold Alert: RSI={round(daily_rsi,1)}, StochRSI={'OS' if stoch_os_1h else 'OK'}. Watch for bullish reversal trigger.")
            score = 35
        else:
            score = 25
            reason.append("1D Downtrend. Avoid longs. Monitor for Short Setup.")
        signal = "Trend Down"; rec = "AVOID"; stop = None

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
        "rsi_1d":         round(daily_rsi, 1),
        "stoch_1h":       round(curr_1h['stoch_rsi_k'], 1),
        "macd_conf":      "Yes" if macd_bull or macd_bear else "No",
        "fvg_tap":        fvg_tap,
        "pa_trigger":     pa_trigger,
        "current_price":  round(entry, 4)
    }


# ─────────────────────────────────────────────────────────────────
# CRYPTO ANALYZER — Full MTF Sniper (same upgrades)
# ─────────────────────────────────────────────────────────────────
def analyze_crypto_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame,
                         data_15m: pd.DataFrame, btc_1d: pd.DataFrame) -> dict:
    upside_str = "N/A"
    rr_str     = "N/A"
    stop       = None

    EMPTY = {"ticker": ticker, "recommendation": "AVOID", "upside": "N/A",
             "stop_loss": "N/A", "rr": "N/A", "signal": "Avoid", "score": 0,
             "reason": "Insufficient Data", "trend_1d": "N/A", "div_1h": "N/A",
             "rsi_1d": "N/A", "stoch_1h": "N/A", "macd_conf": "N/A",
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
    stoch_ob_1h   = _stoch_overbought(curr_1h)
    stoch_os_1h   = _stoch_oversold(curr_1h)
    is_overbought = (daily_rsi > 75) or (daily_rsi > 68 and stoch_ob_1h)
    is_oversold   = (daily_rsi < 30) or (daily_rsi < 35 and stoch_os_1h)

    btc_df    = calculate_indicators(btc_1d).dropna()
    btc_trend = "UP" if (not btc_df.empty and btc_df.iloc[-1]['ema_9'] > btc_df.iloc[-1]['ema_21']) else "DOWN"

    div_1h    = detect_divergence(df_1h)
    macd_bull = _macd_confirms_long(curr_1h)
    macd_bear = _macd_confirms_short(curr_1h)

    tap_bull_fvg    = bool(curr_1h['tapping_bull_fvg'])
    pin_bar_15m     = bool(curr_15m['is_pin_bar'])
    engulf_15m      = bool(curr_15m['is_engulfing_pa'])
    bull_trig_15m   = pin_bar_15m or engulf_15m

    tap_bear_fvg    = bool(curr_1h['tapping_bear_fvg'])
    bear_pin_15m    = bool(curr_15m['is_bear_pin_bar'])
    bear_engulf_15m = bool(curr_15m['is_bear_engulfing_pa'])
    bear_trig_15m   = bear_pin_15m or bear_engulf_15m

    entry  = curr_15m['Close']
    atr_1h = curr_1h['atr_10']
    score  = 50; signal = "Avoid"; rec = "AVOID"; reason = []

    is_bull_setup = (
        trend_1d == "UP" and
        ((div_1h == "Bullish") or tap_bull_fvg) and
        bull_trig_15m and not is_overbought
    )
    is_short_setup = (
        trend_1d == "DOWN" and div_1h == "Bearish" and
        (tap_bear_fvg or bear_trig_15m) and not is_oversold
    )

    if is_bull_setup:
        signal = "Good Entry"; score = 95; rec = "STRONG BUY"
        if macd_bull:
            score += 3
            reason.append("MACD Hist rising — momentum confirmed.")
        setup = []; trig = []
        if div_1h == "Bullish": setup.append("1H Bull Div")
        if tap_bull_fvg:        setup.append("1H FVG Tap")
        if pin_bar_15m:         trig.append("15m Pin Bar")
        if engulf_15m:          trig.append("15m Engulfing")
        reason.append(f"MTF LONG: 1D Fast UP + {' & '.join(setup)} + Sniper {' + '.join(trig)}.")

        fvg_bottom = curr_1h.get('active_bull_fvg_bottom', entry - atr_1h)
        stop   = (fvg_bottom if pd.notna(fvg_bottom) else entry) - atr_1h
        target = max(df_1h['High'].rolling(20).max().iloc[-1], entry + 2.5 * atr_1h)
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
        rr, upside_str, _, rr_str, rr_ok = _calc_rr(entry, stop, target, is_short=True)

        if not rr_ok:
            signal = "Trend Down"; score = 35; rec = "AVOID"
            reason.append(f"Short R:R REJECTED ({rr_str}).")
            upside_str = rr_str = "N/A"; stop = None

    elif trend_1d == "UP":
        if is_overbought:
            signal = "Avoid"; score = 20; rec = "AVOID"
            reason.append(f"EXHAUSTION VETO: 1D RSI={round(daily_rsi,1)}, 1H StochRSI={'OB' if stoch_ob_1h else 'OK'}.")
        else:
            signal = "Trend Up"; score = 60; rec = "WAIT FOR DIP"
            reason.append("1D Fast Uptrend active. Awaiting 15m execution trigger inside 1H setup zone.")
        stop = None
    else:
        if is_oversold:
            reason.append(f"Capitulation Watch: RSI={round(daily_rsi,1)}. Possible bottom formation.")
            score = 35
        else:
            score = 25
            reason.append("1D Downtrend. Avoid longs.")
        signal = "Trend Down"; rec = "AVOID"; stop = None

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
        "rsi_1d":         round(daily_rsi, 1),
        "stoch_1h":       round(curr_1h['stoch_rsi_k'], 1),
        "macd_conf":      "Yes" if macd_bull or macd_bear else "No",
        "fvg_tap":        tap_bull_fvg,
        "pa_trigger":     bull_trig_15m,
        "current_price":  round(entry, 4)
    }
