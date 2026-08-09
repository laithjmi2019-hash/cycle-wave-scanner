"""
data/fetcher.py — Unified data fetcher with strict quality validation.
POLICY: Missing or stale data = DATA QUALITY FAILURE → no signal.
Never silently pass on missing data.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import config
from data.universe import BINANCE_PERP_MAP

# ── VWAP helper (shared across engines) ─────────────────────────────────
def calc_daily_vwap(df: pd.DataFrame) -> pd.Series:
    """Proper daily-reset VWAP: cumsum(TP*Vol)/cumsum(Vol) per date."""
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df['_date'] = df.index.normalize()
    df['_tp']   = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['_tpv']  = df['_tp'] * df['Volume']
    df['_cvol'] = df.groupby('_date')['Volume'].cumsum()
    df['_ctpv'] = df.groupby('_date')['_tpv'].cumsum()
    vwap = (df['_ctpv'] / df['_cvol']).replace([np.inf, -np.inf], np.nan)
    return vwap

# ── DATA QUALITY CHECKS ──────────────────────────────────────────────────
def validate(df: pd.DataFrame, ticker: str,
             min_bars: int = 20, max_stale_mins: int = 120) -> tuple[bool, list]:
    """
    Strict data validation. Returns (is_valid, [issues]).
    NEVER returns (True, []) when data is actually problematic.
    """
    issues = []
    if df is None or df.empty:
        return False, ["DataFrame is None or empty"]

    if len(df) < min_bars:
        issues.append(f"Only {len(df)} bars (need {min_bars})")

    # Freshness check
    last_ts = df.index[-1]
    if hasattr(last_ts, 'tzinfo') and last_ts.tzinfo is None:
        last_ts = last_ts.tz_localize("UTC")
    age_mins = (datetime.datetime.now(datetime.timezone.utc) - last_ts).seconds / 60
    if age_mins > max_stale_mins:
        issues.append(f"Data stale: last bar {age_mins:.0f} min ago (max {max_stale_mins})")

    # Volume quality
    recent = df.tail(5)
    nonzero = (recent['Volume'] > 0).sum()
    if nonzero < config.MIN_VOLUME_BARS:
        issues.append(f"Low volume quality: only {nonzero}/5 bars have volume")

    # OHLC integrity
    bad_ohlc = ((df['Close'] > df['High']) | (df['Close'] < df['Low'])).sum()
    if bad_ohlc > 0:
        issues.append(f"OHLC integrity: {bad_ohlc} bars have close outside high/low")

    neg_prices = (df['Close'] <= 0).sum()
    if neg_prices > 0:
        issues.append(f"Invalid prices: {neg_prices} bars with close <= 0")

    # Duplicate timestamps
    dupes = df.index.duplicated().sum()
    if dupes > 0:
        issues.append(f"Duplicate timestamps: {dupes} duplicates")

    return len(issues) == 0, issues

# ── FETCH FUNCTIONS ──────────────────────────────────────────────────────
def fetch_stock(ticker: str) -> dict:
    """
    Fetch 1D, 1H, 15M data for a stock ticker.
    Returns: {"ok": bool, "ticker": str, "df_1d", "df_1h", "df_15m",
              "price": float, "issues": list}
    DATA UNAVAILABLE = NOT OK. Never silently pass.
    """
    result = {"ok": False, "ticker": ticker, "df_1d": None,
              "df_1h": None, "df_15m": None, "price": None, "issues": []}
    try:
        t    = yf.Ticker(ticker)
        d1d  = t.history(period="1y",  interval="1d",  prepost=False)
        d1h  = t.history(period="60d", interval="1h",  prepost=False)
        d15m = t.history(period="5d",  interval="15m", prepost=False)

        ok_1d,  i1d  = validate(d1d,  ticker, min_bars=200, max_stale_mins=1500)
        ok_1h,  i1h  = validate(d1h,  ticker, min_bars=50,  max_stale_mins=120)

        if not ok_1d:
            result["issues"] += [f"1D: {x}" for x in i1d]
        if not ok_1h:
            result["issues"] += [f"1H: {x}" for x in i1h]

        # 15M is optional but logged if missing
        ok_15m, i15m = validate(d15m, ticker, min_bars=10, max_stale_mins=30)
        if not ok_15m:
            result["issues"] += [f"15M (non-critical): {x}" for x in i15m]
            d15m = None

        if not ok_1h:  # 1H is mandatory for signal generation
            return result

        result.update({
            "ok":     True,
            "df_1d":  d1d if ok_1d else None,
            "df_1h":  d1h,
            "df_15m": d15m,
            "price":  float(d1h['Close'].iloc[-1]),
        })
    except Exception as e:
        result["issues"].append(f"Fetch exception: {e}")

    return result

def fetch_crypto(ticker: str) -> dict:
    """
    Fetch 1D, 1H, 15M data for a crypto ticker.
    Also maps to Binance symbol for derivatives data.
    Returns same structure as fetch_stock + binance_symbol key.
    """
    result = {"ok": False, "ticker": ticker, "df_1d": None,
              "df_1h": None, "df_15m": None, "price": None,
              "binance_symbol": BINANCE_PERP_MAP.get(ticker), "issues": []}
    try:
        t    = yf.Ticker(ticker)
        d1d  = t.history(period="1y",  interval="1d",  prepost=False)
        d1h  = t.history(period="60d", interval="1h",  prepost=False)
        d15m = t.history(period="5d",  interval="15m", prepost=False)

        # Crypto markets are 24/7 so use shorter stale threshold
        ok_1h, i1h = validate(d1h, ticker, min_bars=50, max_stale_mins=60)
        if not ok_1h:
            result["issues"] += [f"1H: {x}" for x in i1h]
            return result

        ok_15m, _ = validate(d15m, ticker, min_bars=10, max_stale_mins=30)

        result.update({
            "ok":     True,
            "df_1d":  d1d if not d1d.empty else None,
            "df_1h":  d1h,
            "df_15m": d15m if ok_15m else None,
            "price":  float(d1h['Close'].iloc[-1]),
        })
    except Exception as e:
        result["issues"].append(f"Fetch exception: {e}")

    return result

def fetch_regime_data() -> dict:
    """
    Fetch market-wide data for regime engines.
    Fetches: SPY, QQQ, IWM, VIX, DXY, TNX, sector ETFs, BTC-USD.
    Returns dict of {ticker: df_1h} — None on fetch failure.
    """
    benchmarks = ["SPY","QQQ","IWM","^VIX","^DXY","^TNX",
                  "XLK","XLF","XLE","XLV","XLY","XLC","XLI","XLP",
                  "BTC-USD","ETH-USD"]
    result = {}
    for sym in benchmarks:
        try:
            df = yf.Ticker(sym).history(period="5d", interval="1h", prepost=False)
            ok, _ = validate(df, sym, min_bars=5, max_stale_mins=180)
            result[sym] = df if ok else None
        except Exception:
            result[sym] = None
    return result
