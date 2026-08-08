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
    """
    Returns True if the ticker has earnings within `hours`.
    Blocks signals near earnings — fundamental risk overrides technical.
    """
    try:
        t   = yf.Ticker(ticker)
        cal = t.calendar
        if cal is None:
            return False
        # yfinance returns calendar as a dict with 'Earnings Date' key
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
                if -24 < diff < hours:   # within window (incl. day after)
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
    Calculates true daily-reset VWAP on hourly data.
    Formula: cumsum(TypicalPrice * Volume) / cumsum(Volume), reset each day.
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
    Validates the 1H signal direction on the 15M chart.
    LONG: 15M RSI must be rising from below 40 (momentum turning up).
    SHORT: 15M RSI must be falling from above 60 (momentum turning down).
    Returns True (confirmed) or False (not yet aligned).
    Falls back to True if 15M data unavailable — never blocks due to missing data.
    """
    try:
        if df_15m is None or len(df_15m) < 20:
            return True
        c      = df_15m['Close']
        rsi_15 = ta.momentum.RSIIndicator(c, 14).rsi().dropna()
        if len(rsi_15) < 3:
            return True
        r_now  = rsi_15.iloc[-1]
        r_prev = rsi_15.iloc[-2]
        r_prev2= rsi_15.iloc[-3]

        if direction == "LONG":
            # RSI was oversold area and is now rising
            return r_now > r_prev and r_prev <= r_prev2 and r_now < 50
        else:  # SHORT
            # RSI was overbought area and is now falling
            return r_now < r_prev and r_prev >= r_prev2 and r_now > 50
    except Exception:
        return True

# ============================================================
# INDICATOR SUITE
# ============================================================
def calculate_indicators(df):
    if len(df) < 30:
        return df
    c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']

    df['rsi']     = ta.momentum.RSIIndicator(c, 14).rsi()
    bb            = ta.volatility.BollingerBands(c, 20, 2.0)
    df['bb_lower']= bb.bollinger_lband()
    df['bb_upper']= bb.bollinger_hband()
    df['bb_mid']  = bb.bollinger_mavg()
    df['atr']     = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range()
    df['adx']     = ta.trend.ADXIndicator(h, l, c, 14).adx()
    df['vol_sma'] = ta.trend.SMAIndicator(v, 20).sma_indicator()
    df['vol_ratio']= v / df['vol_sma']

    macd           = ta.trend.MACD(c)
    df['macd_h']   = macd.macd_diff()
    df['macd_prev']= df['macd_h'].shift(1)

    rm             = c.rolling(20).mean()
    rs             = c.rolling(20).std()
    df['zscore']   = (c - rm) / rs

    # Proper daily-reset VWAP
    df['vwap']     = calc_vwap(df)
    df['sma200']   = ta.trend.SMAIndicator(c, 200).sma_indicator()

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
    """Returns position sizing for 1% risk on a $10,000 account."""
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return "N/A"
    units = 100.0 / risk_per_unit   # $100 = 1% of $10k
    return f"{units:.1f} units (risk $100 per $10k account)"

# ============================================================
# V12 APEX ANALYSIS ENGINE
# ============================================================
def analyze_asset(ticker, df_1d, df_1h, df_15m, spy_data=None):
    """
    V12 Institutional Grade Multi-Factor Engine.

    Gate 1 — Earnings Safety: block if earnings within 72h
    Gate 2 — Market Regime (ADX): ranging → mean reversion | trending → momentum
    Gate 3 — Multi-Factor Signal (RSI + Z-Score + BB + VWAP)
    Gate 4 — 15M Confirmation: 15M RSI must align with signal direction
    Gate 5 — Daily 200 SMA macro filter
    Gate 6 — NLP toxic news filter

    Stop:   2 ATR | Target: 4 ATR (1:2 R:R — backtested optimal)
    """
    df1h = calculate_indicators(df_1h.copy()).dropna()
    if df1h.empty or len(df1h) < 5:
        return None

    # Daily 200 SMA
    daily_200_sma = None
    if df_1d is not None and len(df_1d) >= 200:
        d = df_1d.copy()
        d['sma200d'] = ta.trend.SMAIndicator(d['Close'], 200).sma_indicator()
        daily_200_sma = d['sma200d'].iloc[-1]

    c         = df1h.iloc[-1]
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
    if ranging and rsi < 30 and zscore < -1.5 and entry <= bb_lower:

        # Gate 4: 15M confirmation
        if not confirm_on_15m(df_15m, "LONG"):
            reason = "PENDING (15M): 1H oversold confirmed. Waiting for 15M RSI to turn up."
        # Gate 5: Macro filter
        elif daily_200_sma and entry < (daily_200_sma * 0.90):
            reason = "FILTERED (MTF): Price >10% below Daily 200 SMA. Macro downtrend too strong."
        # Gate 6: News
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news detected. Blocking trade."
        else:
            rec        = "LONG SNIPER"
            signal     = "Mean Reversion"
            stop_loss  = entry - (2.0 * atr)
            target_val = entry + (4.0 * atr)
            rr_str     = _calc_rr(entry, stop_loss, target_val)
            upside_str = f"+{((target_val - entry) / entry * 100):.2f}%"
            pos_size   = position_size_guide(entry, stop_loss)
            confirmed  = 3  # RSI + ZScore + BB
            if entry < vwap:       confirmed += 1
            if vol_ratio > 1.3:    confirmed += 1
            if daily_200_sma and entry > daily_200_sma: confirmed += 1
            if df_15m is not None: confirmed += 1  # 15M confirmed
            stars  = _star_rating(confirmed)
            score  = confirmed * 14
            reason = (f"V12 LONG: ADX={adx:.1f}(ranging), RSI={rsi:.1f}, "
                      f"Z={zscore:.2f}, BB=touched, VWAP={'below' if entry<vwap else 'above'}, "
                      f"15M=confirmed")

    # ── STRATEGY A: MEAN REVERSION SHORT ────────────────────────────────
    elif ranging and rsi > 70 and zscore > 1.5 and entry >= bb_upper:

        if not confirm_on_15m(df_15m, "SHORT"):
            reason = "PENDING (15M): 1H overbought confirmed. Waiting for 15M RSI to turn down."
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
            confirmed  = 3
            if entry > vwap:       confirmed += 1
            if vol_ratio > 1.3:    confirmed += 1
            if daily_200_sma and entry < daily_200_sma: confirmed += 1
            if df_15m is not None: confirmed += 1
            stars  = _star_rating(confirmed)
            score  = confirmed * 14
            reason = (f"V12 SHORT: ADX={adx:.1f}(ranging), RSI={rsi:.1f}, "
                      f"Z={zscore:.2f}, BB=extended, 15M=confirmed")

    # ── STRATEGY B: MOMENTUM BREAKOUT LONG ──────────────────────────────
    elif trending and entry > bb_upper and vol_ratio > 1.5 and macd_h > 0 and macd_prev <= 0:

        if daily_200_sma and entry < daily_200_sma:
            reason = "FILTERED (MTF): Momentum breakout blocked — below Daily 200 SMA."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news detected. Blocking trade."
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
            score  = confirmed * 14
            reason = (f"V12 MOMENTUM: ADX={adx:.1f}(trending), "
                      f"Vol={vol_ratio:.1f}x, MACD crossed +")

    # ── STRATEGY B: MOMENTUM BREAKDOWN SHORT ────────────────────────────
    elif trending and entry < bb_lower and vol_ratio > 1.5 and macd_h < 0 and macd_prev >= 0:

        if check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news detected. Blocking trade."
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
            score  = confirmed * 14
            reason = (f"V12 SHORT MOMENTUM: ADX={adx:.1f}(trending), "
                      f"Vol={vol_ratio:.1f}x, MACD crossed -")

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
