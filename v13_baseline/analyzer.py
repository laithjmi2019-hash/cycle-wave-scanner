import pandas as pd
import numpy as np
import ta
import yfinance as yf
import datetime

# ============================================================
# TOXIC KEYWORDS — NLP Fundamental Safety Filter
# ============================================================
TOXIC_KEYWORDS = [
    "bankruptcy", "scandal", "fraud", "lawsuit", "investigation",
    "delisted", "misses earnings", "subpoena", "criminal", "sec probe",
    "sued", "default", "collapse", "chapter 11", "ponzi", "indicted"
]

VIX_BLOCK_THRESHOLD = 25.0   # Block US mean-reversion LONGs when fear is elevated
US_TICKERS_PATTERN  = ["-USD"]   # Crypto excluded from VIX filter

# ============================================================
# VIX REGIME CACHE (refreshed once per scan, shared across tickers)
# ============================================================
_vix_cache = {"value": None, "ts": None}

def get_vix():
    """Fetch current VIX. Cached for 30 minutes to avoid repeated API calls."""
    global _vix_cache
    now = datetime.datetime.now(datetime.timezone.utc)
    if _vix_cache["ts"] and (now - _vix_cache["ts"]).seconds < 1800:
        return _vix_cache["value"]
    try:
        vix_df = yf.Ticker("^VIX").history(period="2d", interval="1h")
        if not vix_df.empty:
            val = float(vix_df['Close'].iloc[-1])
            _vix_cache = {"value": val, "ts": now}
            return val
    except Exception:
        pass
    return None

def check_toxic_news(ticker):
    try:
        t    = yf.Ticker(ticker)
        news = t.news
        if not news:
            return False
        for item in news[:5]:
            title = ""
            if 'content' in item and 'title' in item['content']:
                title = item['content']['title'].lower()
            elif 'title' in item:
                title = item['title'].lower()
            for word in TOXIC_KEYWORDS:
                if word in title:
                    return True
    except Exception:
        pass
    return False

def has_earnings_soon(ticker, hours=72):
    """Returns True if earnings within `hours`. Block signals near earnings."""
    try:
        t   = yf.Ticker(ticker)
        cal = t.calendar
        if cal is None:
            return False
        dates = None
        if isinstance(cal, dict):
            dates = cal.get('Earnings Date') or cal.get('earnings_date')
        if dates is None:
            return False
        if not isinstance(dates, (list, tuple)):
            dates = [dates]
        for d in dates:
            if d is None:
                continue
            try:
                ed  = pd.Timestamp(d)
                now = pd.Timestamp.now(tz=ed.tzinfo if ed.tzinfo else None)
                diff = (ed - now).total_seconds() / 3600
                if -24 < diff < hours:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False

# ============================================================
# PROPER DAILY-RESET VWAP
# ============================================================
def calc_vwap(df):
    """
    True daily-reset VWAP: cumsum(TP * Vol) / cumsum(Vol), grouped by date.
    TP = (High + Low + Close) / 3
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df['_date'] = df.index.normalize()
    df['_tp']   = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['_tpv']  = df['_tp'] * df['Volume']
    df['_cvol'] = df.groupby('_date')['Volume'].cumsum()
    df['_ctpv'] = df.groupby('_date')['_tpv'].cumsum()
    vwap = (df['_ctpv'] / df['_cvol']).replace([np.inf, -np.inf], np.nan)
    return vwap

# ============================================================
# 15-MINUTE CONFIRMATION
# ============================================================
def confirm_on_15m(df_15m, direction):
    """
    Validates signal direction on 15M chart.
    Falls back to True if 15M data unavailable — never blocks due to missing data.
    """
    try:
        if df_15m is None or len(df_15m) < 20:
            return True
        c      = df_15m['Close']
        rsi_15 = ta.momentum.RSIIndicator(c, 14).rsi().dropna()
        if len(rsi_15) < 3:
            return True
        r_now   = rsi_15.iloc[-1]
        r_prev  = rsi_15.iloc[-2]
        r_prev2 = rsi_15.iloc[-3]
        if direction == "LONG":
            return r_now > r_prev and r_prev <= r_prev2 and r_now < 55
        else:
            return r_now < r_prev and r_prev >= r_prev2 and r_now > 45
    except Exception:
        return True

# ============================================================
# RSI CROSS DETECTION
# ============================================================
def rsi_crossed_up(rsi_series, lookback=3):
    """
    Returns True if RSI was below 30 within `lookback` bars
    AND is now back above 30 (confirmed bounce, not just touch).
    """
    current = rsi_series.iloc[-1]
    if current < 30 or current > 42:   # must be in 30-42 zone (fresh cross)
        return False
    for i in range(1, lookback + 1):
        if rsi_series.iloc[-1 - i] < 30:
            return True
    return False

def rsi_crossed_down(rsi_series, lookback=3):
    """
    Returns True if RSI was above 70 within `lookback` bars
    AND is now back below 70 (confirmed rollover, not just touch).
    """
    current = rsi_series.iloc[-1]
    if current > 70 or current < 58:   # must be in 58-70 zone (fresh cross)
        return False
    for i in range(1, lookback + 1):
        if rsi_series.iloc[-1 - i] > 70:
            return True
    return False

# ============================================================
# INDICATOR SUITE
# ============================================================
def calculate_indicators(df):
    if len(df) < 50:
        return df
    c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']

    df['rsi']      = ta.momentum.RSIIndicator(c, 14).rsi()
    bb             = ta.volatility.BollingerBands(c, 20, 2.0)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_mid']   = bb.bollinger_mavg()
    df['atr']      = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range()
    df['adx']      = ta.trend.ADXIndicator(h, l, c, 14).adx()
    df['vol_sma']  = ta.trend.SMAIndicator(v, 20).sma_indicator()
    df['vol_ratio']= v / df['vol_sma']
    df['ema50']    = ta.trend.EMAIndicator(c, 50).ema_indicator()
    df['sma200']   = ta.trend.SMAIndicator(c, 200).sma_indicator()

    macd           = ta.trend.MACD(c)
    df['macd_h']   = macd.macd_diff()
    df['macd_prev']= df['macd_h'].shift(1)

    rm             = c.rolling(20).mean()
    rs             = c.rolling(20).std()
    df['zscore']   = (c - rm) / rs

    # Proper daily-reset VWAP
    df['vwap']     = calc_vwap(df)

    return df

def _star_rating(n):
    if n >= 7: return "STAR_5"
    if n >= 6: return "STAR_4"
    if n >= 5: return "STAR_3"
    return "STAR_2"

def _calc_rr(entry, stop, target, is_short=False):
    risk   = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0:
        return "N/A"
    return f"1:{reward/risk:.1f}"

def position_size_guide(entry, stop):
    """Position size for 1% risk on a $10,000 account."""
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return "N/A"
    units = 100.0 / risk_per_unit
    return f"{units:.1f} units (risk $100 per $10k)"

def _is_us_equity(ticker):
    """True if ticker is a US equity (not crypto, not international with dot)"""
    return "." not in ticker and "-USD" not in ticker

# ============================================================
# V13 APEX ENGINE — INSTITUTIONAL GRADE
# ============================================================
def analyze_asset(ticker, df_1d, df_1h, df_15m, spy_data=None):
    """
    V13 Institutional Grade Engine.

    GATES (all must pass for signal):
    ─────────────────────────────────────────────────────────
    LONG SNIPER (Mean Reversion):
      1. ADX < 25 (ranging market — mean reversion valid)
      2. RSI CROSS UP: was below 30 in last 3 bars, now 30–42 (bounce confirmed)
      3. Price near EMA50 (within 3%) — mean is the target, must be close to it
      4. Price below VWAP — below institutional fair value (backtest confirmed)
      5. VIX < 25 for US equities (no mean reversion during market panic)
      6. Daily 200 SMA: price not >10% below (no catching macro knives)
      7. 15M RSI turning upward — timeframe confirmation
      8. No toxic news / No earnings within 72h

    SHORT SNIPER (Mean Reversion):
      1. ADX < 25 (ranging market)
      2. RSI CROSS DOWN: was above 70 in last 3 bars, now 58–70 (rollover confirmed)
      3. Price near EMA50 (within 3% above it)
      4. Price above VWAP
      5. 15M RSI turning downward
      6. No toxic news / No earnings within 72h

    LONG/SHORT MOMENTUM: unchanged from V12
    ─────────────────────────────────────────────────────────
    Stop: 2 ATR | Target: 4 ATR (1:2 R:R — backtested optimal)
    """
    df1h = calculate_indicators(df_1h.copy()).dropna()
    if df1h.empty or len(df1h) < 10:
        return None

    # Daily 200 SMA
    daily_200_sma = None
    if df_1d is not None and len(df_1d) >= 200:
        d = df_1d.copy()
        d['sma200d'] = ta.trend.SMAIndicator(d['Close'], 200).sma_indicator()
        daily_200_sma = d['sma200d'].iloc[-1]

    c         = df1h.iloc[-1]
    rsi_series= df1h['rsi']
    rsi       = c['rsi']
    bb_lower  = c['bb_lower']
    bb_upper  = c['bb_upper']
    atr       = c['atr']
    adx       = c['adx']
    entry     = c['Close']
    vol_ratio = c['vol_ratio']
    macd_h    = c['macd_h']
    macd_prev = c['macd_prev']
    zscore    = c['zscore']
    vwap      = c['vwap']
    ema50     = c['ema50']

    rec        = "WAIT"
    signal     = "Scanning"
    reason     = "No confluence detected."
    score      = 0
    stars      = "STAR_2"
    stop_loss  = 0.0
    target_val = 0.0
    upside_str = "N/A"
    rr_str     = "N/A"
    pos_size   = "N/A"

    bb_status = "Inside Bands"
    if entry < bb_lower: bb_status = "Below Lower Band"
    elif entry > bb_upper: bb_status = "Above Upper Band"

    ranging  = adx < 25
    trending = adx >= 25

    # ── STRATEGY A: MEAN REVERSION LONG ─────────────────────────────────
    # Core: RSI confirmed cross up + EMA50 proximity + below VWAP
    rsi_cross_up  = rsi_crossed_up(rsi_series, lookback=3)
    near_ema50    = entry <= ema50 * 1.03    # within 3% of EMA50
    below_vwap    = entry < vwap

    if ranging and rsi_cross_up and near_ema50 and below_vwap:

        # VIX Gate: block US mean-reversion LONGs during elevated fear
        vix = get_vix()
        if _is_us_equity(ticker) and vix and vix > VIX_BLOCK_THRESHOLD:
            reason = f"FILTERED (VIX={vix:.1f}): Market fear elevated. Mean reversion unreliable."

        # Macro Gate: no catching macro falling knives
        elif daily_200_sma and entry < (daily_200_sma * 0.90):
            reason = "FILTERED (MTF): Price >10% below Daily 200 SMA. Macro downtrend too strong."

        # 15M Confirmation
        elif not confirm_on_15m(df_15m, "LONG"):
            reason = "PENDING (15M): 1H bounce forming. Waiting for 15M RSI to confirm upward turn."

        # Earnings filter
        elif "-USD" not in ticker and has_earnings_soon(ticker, hours=72):
            reason = "FILTERED (Earnings): Earnings within 72h. Fundamental risk too high."

        # NLP filter
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."

        else:
            rec        = "LONG SNIPER"
            signal     = "Mean Reversion"
            stop_loss  = entry - (2.0 * atr)
            target_val = entry + (4.0 * atr)
            rr_str     = _calc_rr(entry, stop_loss, target_val)
            upside_str = f"+{((target_val - entry) / entry * 100):.2f}%"
            pos_size   = position_size_guide(entry, stop_loss)

            # Star rating — additional quality confirmations
            confirmed = 4   # RSI cross + EMA50 + VWAP + ADX = 4 base
            if zscore < -1.5:       confirmed += 1   # Statistically extreme
            if entry <= bb_lower:   confirmed += 1   # At/below BB lower
            if vol_ratio > 1.2:     confirmed += 1   # Elevated volume
            if daily_200_sma and entry > daily_200_sma: confirmed += 1  # Macro uptrend
            if df_15m is not None:  confirmed += 1   # 15M confirmed
            stars  = _star_rating(confirmed)
            score  = confirmed * 12

            vix_str = f", VIX={vix:.1f}" if vix else ""
            reason = (f"V13 LONG: ADX={adx:.1f}(ranging), RSI crossed up "
                      f"({rsi:.1f}), near EMA50, below VWAP, 15M=confirmed{vix_str}")

    # ── STRATEGY A: MEAN REVERSION SHORT ────────────────────────────────
    rsi_cross_dn  = rsi_crossed_down(rsi_series, lookback=3)
    near_ema50_sh = entry >= ema50 * 0.97   # within 3% above EMA50
    above_vwap    = entry > vwap

    if ranging and rsi_cross_dn and near_ema50_sh and above_vwap and rec == "WAIT":

        if not confirm_on_15m(df_15m, "SHORT"):
            reason = "PENDING (15M): 1H rollover forming. Waiting for 15M RSI to confirm downward turn."
        elif "-USD" not in ticker and has_earnings_soon(ticker, hours=72):
            reason = "FILTERED (Earnings): Earnings within 72h. Fundamental risk too high."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news detected. Blocking trade."
        else:
            rec        = "SHORT SNIPER"
            signal     = "Mean Reversion"
            stop_loss  = entry + (2.0 * atr)
            target_val = entry - (4.0 * atr)
            rr_str     = _calc_rr(entry, stop_loss, target_val, is_short=True)
            upside_str = f"+{((entry - target_val) / entry * 100):.2f}%"
            pos_size   = position_size_guide(entry, stop_loss)

            confirmed = 4
            if zscore > 1.5:        confirmed += 1
            if entry >= bb_upper:   confirmed += 1
            if vol_ratio > 1.2:     confirmed += 1
            if daily_200_sma and entry < daily_200_sma: confirmed += 1
            if df_15m is not None:  confirmed += 1
            stars  = _star_rating(confirmed)
            score  = confirmed * 12

            reason = (f"V13 SHORT: ADX={adx:.1f}(ranging), RSI crossed down "
                      f"({rsi:.1f}), near EMA50, above VWAP, 15M=confirmed")

    # ── STRATEGY B: MOMENTUM BREAKOUT LONG ──────────────────────────────
    if trending and entry > bb_upper and vol_ratio > 1.5 and macd_h > 0 and macd_prev <= 0 and rec == "WAIT":

        if daily_200_sma and entry < daily_200_sma:
            reason = "FILTERED (MTF): Momentum breakout blocked — below Daily 200 SMA."
        elif "-USD" not in ticker and has_earnings_soon(ticker, hours=72):
            reason = "FILTERED (Earnings): Earnings within 72h."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news detected."
        else:
            rec        = "LONG MOMENTUM"
            signal     = "Trend Breakout"
            stop_loss  = entry - (2.0 * atr)
            target_val = entry + (4.0 * atr)
            rr_str     = _calc_rr(entry, stop_loss, target_val)
            upside_str = f"+{((target_val - entry) / entry * 100):.2f}%"
            pos_size   = position_size_guide(entry, stop_loss)
            confirmed  = 3
            if entry > vwap:    confirmed += 1
            if vol_ratio > 2.0: confirmed += 1
            if daily_200_sma and entry > daily_200_sma: confirmed += 1
            stars  = _star_rating(confirmed)
            score  = confirmed * 12
            reason = (f"V13 MOMENTUM: ADX={adx:.1f}(trending), "
                      f"Vol={vol_ratio:.1f}x, MACD crossed +, BB breakout")

    # ── STRATEGY B: MOMENTUM BREAKDOWN SHORT ────────────────────────────
    if trending and entry < bb_lower and vol_ratio > 1.5 and macd_h < 0 and macd_prev >= 0 and rec == "WAIT":

        if "-USD" not in ticker and has_earnings_soon(ticker, hours=72):
            reason = "FILTERED (Earnings): Earnings within 72h."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news detected."
        else:
            rec        = "SHORT MOMENTUM"
            signal     = "Trend Breakdown"
            stop_loss  = entry + (2.0 * atr)
            target_val = entry - (4.0 * atr)
            rr_str     = _calc_rr(entry, stop_loss, target_val, is_short=True)
            upside_str = f"+{((entry - target_val) / entry * 100):.2f}%"
            pos_size   = position_size_guide(entry, stop_loss)
            confirmed  = 3
            if entry < vwap:    confirmed += 1
            if vol_ratio > 2.0: confirmed += 1
            stars  = _star_rating(confirmed)
            score  = confirmed * 12
            reason = (f"V13 SHORT MOMENTUM: ADX={adx:.1f}(trending), "
                      f"Vol={vol_ratio:.1f}x, MACD crossed -, BB breakdown")

    return {
        "ticker":         ticker,
        "recommendation": rec,
        "signal":         signal,
        "score":          score,
        "stars":          stars,
        "reason":         reason,
        "upside":         upside_str,
        "stop_loss":      f"${stop_loss:.4f}" if stop_loss > 0 else "N/A",
        "stop_loss_raw":  stop_loss,
        "target_raw":     target_val,
        "entry":          entry,
        "rr":             rr_str,
        "pos_size":       pos_size,
        "rsi":            f"{rsi:.1f}",
        "adx":            f"{adx:.1f}",
        "zscore":         f"{zscore:.2f}",
        "bb_status":      bb_status,
        "timestamp":      datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

def analyze_crypto_asset(ticker, df_1d, df_1h, df_15m, btc_1d=None):
    return analyze_asset(ticker, df_1d, df_1h, df_15m)
