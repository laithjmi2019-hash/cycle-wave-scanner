"""
data/binance_api.py — Binance public REST API client.
No API key required. Provides OI, funding rates, and kline data.
All crypto derivatives data flows through this module.
"""
import requests
import datetime
import time
from typing import Optional

BASE_FAPI = "https://fapi.binance.com"   # perpetual futures
BASE_API  = "https://api.binance.com"    # spot

TIMEOUT = 8   # seconds

# ── CACHE: refresh expensive calls max once per 5 minutes ────────────────
_cache: dict = {}
CACHE_TTL = 300   # seconds

def _cached(key: str, fetch_fn, ttl: int = CACHE_TTL):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < ttl:
        return _cache[key]["data"]
    data = fetch_fn()
    _cache[key] = {"ts": now, "data": data}
    return data

# ── OPEN INTEREST ────────────────────────────────────────────────────────
def get_open_interest(symbol: str) -> Optional[dict]:
    """
    Returns current OI for a perpetual futures symbol.
    Returns: {"symbol", "openInterest", "time"} or None on failure.
    """
    def fetch():
        try:
            r = requests.get(f"{BASE_FAPI}/fapi/v1/openInterest",
                             params={"symbol": symbol}, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"oi_{symbol}", fetch, ttl=60)

def get_oi_history(symbol: str, period: str = "1h", limit: int = 48) -> Optional[list]:
    """
    Returns historical OI data (1h intervals, last 48 bars).
    Returns list of {"timestamp", "sumOpenInterest", "sumOpenInterestValue"} or None.
    """
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/futures/data/openInterestHist",
                params={"symbol": symbol, "period": period, "limit": limit},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"oi_hist_{symbol}_{period}", fetch, ttl=120)

# ── FUNDING RATES ────────────────────────────────────────────────────────
def get_funding_rate(symbol: str, limit: int = 10) -> Optional[list]:
    """
    Returns recent funding rates.
    Returns list of {"symbol", "fundingRate", "fundingTime"} or None.
    """
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/fapi/v1/fundingRate",
                params={"symbol": symbol, "limit": limit},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"funding_{symbol}", fetch, ttl=300)

def get_mark_price_and_funding(symbol: str) -> Optional[dict]:
    """
    Returns current mark price, index price, and next funding rate.
    Returns: {"symbol", "markPrice", "indexPrice", "lastFundingRate", "nextFundingTime"}
    """
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/fapi/v1/premiumIndex",
                params={"symbol": symbol},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"mark_{symbol}", fetch, ttl=60)

# ── LONG/SHORT RATIO ─────────────────────────────────────────────────────
def get_long_short_ratio(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Global long/short account ratio. Indicates crowd positioning."""
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/futures/data/globalLongShortAccountRatio",
                params={"symbol": symbol, "period": period, "limit": limit},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"lsr_{symbol}_{period}", fetch, ttl=120)

# ── LIQUIDATIONS PROXY ────────────────────────────────────────────────────
def get_liquidation_orders(symbol: str) -> Optional[list]:
    """
    Recent forced liquidation orders.
    NOTE: Binance only returns last 24h of liquidation data.
    Returns list of {"symbol","side","orderType","timeInForce","origQty",
                     "price","averagePrice","status","lastFilledQty",
                     "filledAccumulatedQty","tradeTime"} or None.
    """
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/fapi/v1/forceOrders",
                params={"symbol": symbol, "limit": 50},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"liq_{symbol}", fetch, ttl=120)

# ── 24H TICKER ───────────────────────────────────────────────────────────
def get_24h_ticker(symbol: str) -> Optional[dict]:
    """Returns 24h statistics including volume, price change, etc."""
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/fapi/v1/ticker/24hr",
                params={"symbol": symbol},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"24h_{symbol}", fetch, ttl=60)

# ── KLINES (OHLCV) ────────────────────────────────────────────────────────
def get_klines(symbol: str, interval: str = "1h", limit: int = 100) -> Optional[list]:
    """
    Returns OHLCV klines from Binance futures.
    Returns list of [open_time, open, high, low, close, volume, ...] or None.
    """
    def fetch():
        try:
            r = requests.get(
                f"{BASE_FAPI}/fapi/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
    return _cached(f"klines_{symbol}_{interval}", fetch, ttl=60)

# ── INTERPRETATION HELPERS ────────────────────────────────────────────────
def interpret_oi_price(oi_change_pct: float, price_change_pct: float) -> dict:
    """
    Interpret OI + Price combination.
    Returns: {"signal", "strength", "description"}
    """
    if price_change_pct > 0.5 and oi_change_pct > 1.0:
        return {"signal": "BULLISH_TREND", "strength": 0.8,
                "description": "Price up + OI up → new longs entering, trend continuation"}
    if price_change_pct > 0.5 and oi_change_pct < -1.0:
        return {"signal": "SHORT_COVER", "strength": 0.5,
                "description": "Price up + OI down → short covering, weaker move"}
    if price_change_pct < -0.5 and oi_change_pct > 1.0:
        return {"signal": "BEARISH_TREND", "strength": 0.8,
                "description": "Price down + OI up → new shorts entering, trend continuation"}
    if price_change_pct < -0.5 and oi_change_pct < -1.0:
        return {"signal": "LONG_LIQ", "strength": 0.7,
                "description": "Price down + OI down → long liquidation / exhaustion"}
    return {"signal": "NEUTRAL", "strength": 0.0, "description": "No clear OI signal"}

def interpret_funding(rate: float) -> dict:
    """
    Interpret funding rate.
    Returns: {"bias", "crowding", "score_adjustment", "description"}
    """
    pct = rate * 100
    if pct > 0.05:
        return {"bias": "LONG_CROWDED", "crowding": "EXTREME",
                "score_adjustment": -10,
                "description": f"Funding {pct:.4f}%: Longs dangerously crowded"}
    if 0.01 < pct <= 0.05:
        return {"bias": "LONG_LEAN", "crowding": "ELEVATED",
                "score_adjustment": -3,
                "description": f"Funding {pct:.4f}%: Elevated long bias, mild caution"}
    if -0.01 <= pct <= 0.01:
        return {"bias": "NEUTRAL", "crowding": "BALANCED",
                "score_adjustment": 0,
                "description": f"Funding {pct:.4f}%: Balanced positioning"}
    if -0.05 <= pct < -0.01:
        return {"bias": "SHORT_LEAN", "crowding": "ELEVATED_SHORT",
                "score_adjustment": 5,
                "description": f"Funding {pct:.4f}%: Short lean → bullish for squeeze"}
    return {"bias": "SHORT_CROWDED", "crowding": "EXTREME_SHORT",
            "score_adjustment": 8,
            "description": f"Funding {pct:.4f}%: Shorts dangerously crowded → high squeeze potential"}
