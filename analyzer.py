import pandas as pd
import numpy as np
import ta
import yfinance as yf

# ============================================================
# TOXIC KEYWORDS for NLP Fundamental Filter
# ============================================================
TOXIC_KEYWORDS = [
    "bankruptcy", "scandal", "fraud", "lawsuit", "investigation",
    "delisted", "misses earnings", "subpoena", "criminal", "sec probe",
    "sued", "default", "collapse", "chapter 11", "ponzi", "indicted"
]

def check_toxic_news(ticker):
    """
    Pulls latest 5 news headlines from Yahoo Finance.
    Returns True (block trade) if any toxic keywords found.
    """
    try:
        t = yf.Ticker(ticker)
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

def calculate_indicators(df):
    """
    V11 Indicator Suite:
    RSI-14, Bollinger Bands(20,2), ATR-10, Volume SMA-20,
    MACD, ADX-14, Z-Score(20), VWAP(24h rolling), 200-bar SMA.
    """
    if len(df) < 30:
        return df

    c = df['Close']
    h = df['High']
    l = df['Low']
    v = df['Volume']

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(c, window=14).rsi()

    # Bollinger Bands (20, 2)
    bb = ta.volatility.BollingerBands(close=c, window=20, window_dev=2.0)
    df['bb_lower']  = bb.bollinger_lband()
    df['bb_upper']  = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()

    # ATR (10) — used for stops and targets
    df['atr'] = ta.volatility.AverageTrueRange(h, l, c, window=10).average_true_range()

    # ADX (14) — Market Regime: < 25 = ranging, > 25 = trending
    df['adx'] = ta.trend.ADXIndicator(h, l, c, window=14).adx()

    # Volume SMA and ratio
    df['vol_sma']   = ta.trend.SMAIndicator(v, window=20).sma_indicator()
    df['vol_ratio'] = v / df['vol_sma']

    # MACD Histogram
    macd = ta.trend.MACD(c)
    df['macd_h']      = macd.macd_diff()
    df['macd_h_prev'] = df['macd_h'].shift(1)

    # Z-Score (20-period) — statistical deviation from mean
    roll_mean     = c.rolling(20).mean()
    roll_std      = c.rolling(20).std()
    df['zscore']  = (c - roll_mean) / roll_std

    # VWAP (rolling 24-bar proxy)
    df['vwap'] = (c * v).rolling(24).sum() / v.rolling(24).sum()

    # 200-bar SMA (macro trend on hourly = ~8.3 trading days)
    df['sma200'] = ta.trend.SMAIndicator(c, window=200).sma_indicator()

    return df

def _calc_rr(entry, stop, target, is_short=False):
    """Calculates risk/reward ratio."""
    if not is_short:
        risk   = entry - stop
        reward = target - entry
    else:
        risk   = stop - entry
        reward = entry - target
    if risk <= 0:
        return "N/A", 0, 0, "N/A"
    ratio  = reward / risk
    rr_str = f"1:{ratio:.1f}"
    return ratio, risk, reward, rr_str

def _star_rating(conditions_met):
    """Converts number of confirmed conditions into a star string."""
    if conditions_met >= 7: return "STAR_5"
    if conditions_met >= 6: return "STAR_4"
    if conditions_met >= 5: return "STAR_3"
    if conditions_met >= 4: return "STAR_2"
    return "STAR_2"

def analyze_asset(ticker, df_1d, df_1h, df_15m, spy_data=None):
    """
    V11 Apex Multi-Factor Confluence Engine.

    Gate 1 — Market Regime (ADX):
        ADX < 25 → Use Mean Reversion (Strategy A)
        ADX > 25 → Use Momentum Breakout (Strategy B)

    Gate 2 — Multi-Factor Signal:
        Strategy A: RSI<30 + Z-Score<-1.5 + Below BB + Below VWAP
        Strategy B: Above BB + Vol>150% + MACD cross + ADX>25

    Gate 3 — Daily 200 SMA Macro Alignment

    Gate 4 — NLP News Safety Filter

    Target: 4 ATR (1:2 R:R proven optimal by backtest)
    Stop:   2 ATR
    """
    df1h = calculate_indicators(df_1h.copy()).dropna()
    if df1h.empty or len(df1h) < 5:
        return None

    # --- Daily 200 SMA ---
    daily_200_sma = None
    if df_1d is not None and len(df_1d) >= 200:
        df_1d = df_1d.copy()
        df_1d['sma_200'] = ta.trend.SMAIndicator(df_1d['Close'], window=200).sma_indicator()
        daily_200_sma = df_1d['sma_200'].iloc[-1]

    c = df1h.iloc[-1]

    rsi       = c['rsi']
    bb_lower  = c['bb_lower']
    bb_upper  = c['bb_upper']
    atr       = c['atr']
    adx       = c['adx']
    entry     = c['Close']
    vol_ratio = c['vol_ratio']
    macd_h    = c['macd_h']
    macd_prev = c['macd_h_prev']
    zscore    = c['zscore']
    vwap      = c['vwap']
    sma200h   = c['sma200']

    # Defaults
    rec        = "WAIT"
    signal     = "Scanning"
    reason     = "No confluence detected."
    score      = 0
    stop_loss  = 0.0
    upside_str = "N/A"
    rr_str     = "N/A"
    stars      = "STAR_2"

    bb_status = "Inside Bands"
    if entry < bb_lower: bb_status = "Below Lower Band"
    elif entry > bb_upper: bb_status = "Above Upper Band"

    # ================================================================
    # GATE 1: MARKET REGIME DETECTION via ADX
    # ================================================================
    market_is_ranging  = adx < 25   # Good for mean reversion
    market_is_trending = adx >= 25  # Good for momentum

    # ================================================================
    # STRATEGY A: MEAN REVERSION (only in ranging markets)
    # Requires: RSI<30 + Z-Score<-1.5 + At/Below BB Lower
    # VWAP below price is an optional booster (affects star rating)
    # ================================================================
    if market_is_ranging and rsi < 30 and zscore < -1.5 and entry <= bb_lower:

        # Gate 3: Daily Macro Filter — block longs in macro downtrend
        if daily_200_sma and entry < (daily_200_sma * 0.90):
            reason = "FILTERED (MTF): Price >10% below Daily 200 SMA. Macro downtrend too strong."
        # Gate 4: News filter
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec       = "LONG SNIPER"
            signal    = "Mean Reversion"
            stop_loss = entry - (2.0 * atr)
            target    = entry + (4.0 * atr)   # 1:2 R:R (backtested optimal)
            _, _, _, rr_str = _calc_rr(entry, stop_loss, target)
            upside_str = f"+{((target - entry) / entry) * 100:.2f}%"

            # Star rating — count how many extra conditions align
            confirmed = 3  # Base: RSI + ZScore + BB = 3 confirmed
            if entry < vwap:       confirmed += 1   # Below VWAP
            if vol_ratio > 1.3:    confirmed += 1   # Volume elevated
            if daily_200_sma and entry > daily_200_sma: confirmed += 1  # Macro uptrend
            stars = _star_rating(confirmed)
            score = confirmed * 15

            reason = (
                f"V11 MEAN REVERSION: ADX={adx:.1f}(ranging), "
                f"RSI={rsi:.1f}, Z={zscore:.2f}, BB=touched, "
                f"VWAP={'below' if entry < vwap else 'above'}"
            )

    # Strategy A SHORT — Overbought in ranging market
    elif market_is_ranging and rsi > 70 and zscore > 1.5 and entry >= bb_upper:
        if check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec       = "SHORT SNIPER"
            signal    = "Mean Reversion"
            stop_loss = entry + (2.0 * atr)
            target    = entry - (4.0 * atr)
            _, _, _, rr_str = _calc_rr(entry, stop_loss, target, is_short=True)
            upside_str = f"+{((entry - target) / entry) * 100:.2f}%"

            confirmed = 3
            if entry > vwap:       confirmed += 1
            if vol_ratio > 1.3:    confirmed += 1
            if daily_200_sma and entry < daily_200_sma: confirmed += 1
            stars = _star_rating(confirmed)
            score = confirmed * 15

            reason = (
                f"V11 SHORT REVERSION: ADX={adx:.1f}(ranging), "
                f"RSI={rsi:.1f}, Z={zscore:.2f}, BB=extended"
            )

    # ================================================================
    # STRATEGY B: MOMENTUM BREAKOUT (only in trending markets)
    # Requires: ADX>25 + Price above BB + Vol>150% + MACD cross
    # ================================================================
    elif market_is_trending and entry > bb_upper and vol_ratio > 1.5 and macd_h > 0 and macd_prev <= 0:
        # Must be in macro uptrend for LONG
        if daily_200_sma and entry < daily_200_sma:
            reason = "FILTERED (MTF): Momentum breakout blocked — below Daily 200 SMA."
        elif check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec       = "LONG MOMENTUM"
            signal    = "Trend Breakout"
            stop_loss = entry - (2.0 * atr)
            target    = entry + (4.0 * atr)
            _, _, _, rr_str = _calc_rr(entry, stop_loss, target)
            upside_str = f"+{((target - entry) / entry) * 100:.2f}%"

            confirmed = 3  # ADX + Vol + MACD
            if entry > vwap:    confirmed += 1
            if vol_ratio > 2.0: confirmed += 1  # Extra high volume
            if daily_200_sma and entry > daily_200_sma: confirmed += 1
            stars = _star_rating(confirmed)
            score = confirmed * 15

            reason = (
                f"V11 MOMENTUM: ADX={adx:.1f}(trending), "
                f"Vol={vol_ratio:.1f}x avg, MACD crossed positive"
            )

    elif market_is_trending and entry < bb_lower and vol_ratio > 1.5 and macd_h < 0 and macd_prev >= 0:
        if check_toxic_news(ticker):
            reason = "FILTERED (NLP): Toxic news keywords detected. Blocking trade."
        else:
            rec       = "SHORT MOMENTUM"
            signal    = "Trend Breakdown"
            stop_loss = entry + (2.0 * atr)
            target    = entry - (4.0 * atr)
            _, _, _, rr_str = _calc_rr(entry, stop_loss, target, is_short=True)
            upside_str = f"+{((entry - target) / entry) * 100:.2f}%"

            confirmed = 3
            if entry < vwap:    confirmed += 1
            if vol_ratio > 2.0: confirmed += 1
            stars = _star_rating(confirmed)
            score = confirmed * 15

            reason = (
                f"V11 SHORT MOMENTUM: ADX={adx:.1f}(trending), "
                f"Vol={vol_ratio:.1f}x avg, MACD crossed negative"
            )

    # ================================================================
    # WATCHLIST NEAR-MISS DETECTION
    # Only fires when asset is VERY CLOSE to a full signal.
    # All 3 conditions must be partially met simultaneously (tight thresholds).
    # ================================================================
    watch_alert = None
    if rec == "WAIT":
        # LONG WATCH: RSI within 3pts of trigger, Z within 0.3 of trigger,
        # price within 1% of lower BB, ADX confirms ranging market
        near_long_rsi  = rsi < 33          # within 3 points of RSI<30 trigger
        near_long_z    = zscore < -1.2     # within 0.3 of Z<-1.5 trigger
        near_long_bb   = entry <= (bb_lower * 1.01)  # within 1% of lower band
        near_long_adx  = adx < 27          # must be clearly ranging

        # ALL 3 must be close — prevents low-quality alerts
        if near_long_adx and near_long_rsi and near_long_z and near_long_bb:
            missing = []
            if not (rsi < 30):      missing.append(f"RSI={rsi:.1f} (needs <30)")
            if not (zscore < -1.5): missing.append(f"Z={zscore:.2f} (needs <-1.5)")
            if not (entry <= bb_lower): missing.append("Price must touch Lower BB")

            watch_alert = {
                "type":    "WATCH LONG",
                "missing": " | ".join(missing) if missing else "All conditions nearly met",
                "rsi":     f"{rsi:.1f}",
                "zscore":  f"{zscore:.2f}",
                "adx":     f"{adx:.1f}",
                "regime":  "RANGING",
                "conditions_met": sum([near_long_rsi, near_long_z, near_long_bb]),
            }

        # SHORT WATCH: RSI within 3pts of trigger, Z within 0.3 of trigger,
        # price within 1% of upper BB, ADX confirms ranging market
        near_short_rsi  = rsi > 67         # within 3 points of RSI>70 trigger
        near_short_z    = zscore > 1.2     # within 0.3 of Z>+1.5 trigger
        near_short_bb   = entry >= (bb_upper * 0.99)  # within 1% of upper band
        near_short_adx  = adx < 27

        if near_short_adx and near_short_rsi and near_short_z and near_short_bb:
            missing = []
            if not (rsi > 70):      missing.append(f"RSI={rsi:.1f} (needs >70)")
            if not (zscore > 1.5):  missing.append(f"Z={zscore:.2f} (needs >+1.5)")
            if not (entry >= bb_upper): missing.append("Price must touch Upper BB")

            watch_alert = {
                "type":    "WATCH SHORT",
                "missing": " | ".join(missing) if missing else "All conditions nearly met",
                "rsi":     f"{rsi:.1f}",
                "zscore":  f"{zscore:.2f}",
                "adx":     f"{adx:.1f}",
                "regime":  "RANGING",
                "conditions_met": sum([near_short_rsi, near_short_z, near_short_bb]),
            }

    return {
        "ticker":         ticker,
        "recommendation": rec,
        "signal":         signal,
        "score":          score,
        "stars":          stars,
        "reason":         reason,
        "upside":         upside_str,
        "stop_loss":      f"${stop_loss:.2f}" if stop_loss > 0 else "N/A",
        "rr":             rr_str,
        "rsi":            f"{rsi:.1f}",
        "adx":            f"{adx:.1f}",
        "zscore":         f"{zscore:.2f}",
        "bb_status":      bb_status,
        "watch_alert":    watch_alert,
    }

def analyze_crypto_asset(ticker, df_1d, df_1h, df_15m, btc_1d=None):
    """Applies V11 Engine to Crypto assets."""
    return analyze_asset(ticker, df_1d, df_1h, df_15m)
