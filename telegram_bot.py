import os
import sys
import json
import requests
import datetime
import yfinance as yf
import concurrent.futures

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyzer import analyze_asset
from data_fetcher import (
    US_EQUITIES, EU_EQUITIES, CHINA_EQUITIES, UAE_EQUITIES, CRYPTO,
    ASSET_MARKET_MAP, market_is_open
)

TELEGRAM_TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID              = os.environ.get("TELEGRAM_CHAT_ID")
ALL_TICKERS          = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES + CRYPTO
SIGNAL_CACHE_FILE    = "/tmp/v11_signal_cache.json"
SIGNAL_COOLDOWN_HRS  = 4

STAR_MAP = {
    "STAR_5": "[*****] ELITE",
    "STAR_4": "[****]  HIGH",
    "STAR_3": "[***]   MEDIUM",
    "STAR_2": "[**]    DEVELOPING",
}

# ============================================================
# DEDUPLICATION CACHE
# ============================================================
def load_cache():
    try:
        if os.path.exists(SIGNAL_CACHE_FILE):
            with open(SIGNAL_CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_cache(cache):
    try:
        with open(SIGNAL_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

def is_duplicate(key, cache, cooldown_hrs):
    if key in cache:
        last = datetime.datetime.fromisoformat(cache[key])
        if (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() / 3600 < cooldown_hrs:
            return True
    return False

def mark_sent(key, cache):
    cache[key] = datetime.datetime.now(datetime.timezone.utc).isoformat()

# ============================================================
# TELEGRAM
# ============================================================
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing Telegram credentials.")
        return
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload).raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")

# ============================================================
# SCAN ONE TICKER
# ============================================================
def process_ticker(ticker):
    """Fetch data and run V11 analysis on a single ticker."""
    market = ASSET_MARKET_MAP.get(ticker, "US")
    if not market_is_open(market):
        return None
    try:
        t   = yf.Ticker(ticker)
        d1d = t.history(period="1y",  interval="1d", prepost=False)
        d1h = t.history(period="60d", interval="1h", prepost=False)
        if d1d.empty or d1h.empty:
            return None
        res = analyze_asset(ticker, d1d, d1h, None)
        if res:
            res["price"] = d1h['Close'].iloc[-1]
        return res
    except Exception as e:
        print(f"Error {ticker}: {e}")
    return None

# ============================================================
# BUILD TELEGRAM MESSAGE (confirmed signals only)
# ============================================================
def build_signal_message(res):
    rec   = res["recommendation"]
    stars = STAR_MAP.get(res.get("stars", "STAR_2"), "[**] DEVELOPING")
    label = "MOMENTUM BREAKOUT" if "MOMENTUM" in rec else rec
    msg  = f"<b>{label}</b>\n"
    msg += f"{stars}\n\n"
    msg += f"<b>Asset:</b> {res['ticker']}\n"
    msg += f"<b>Price:</b> ${res['price']:.4f}\n"
    msg += f"<b>RSI-14:</b> {res['rsi']}\n"
    msg += f"<b>ADX:</b> {res['adx']}\n"
    msg += f"<b>Z-Score:</b> {res['zscore']}\n"
    msg += f"<b>Target:</b> {res['upside']} (4 ATR)\n"
    msg += f"<b>Stop Loss:</b> {res['stop_loss']} (2 ATR)\n"
    msg += f"<b>Risk/Reward:</b> {res['rr']}\n\n"
    msg += f"<i>{res['reason']}</i>"
    return msg

# ============================================================
# MAIN SCAN — confirmed signals only, no noise
# ============================================================
def run_scan():
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"V11 Scan started at {ts}")

    cache       = load_cache()
    new_signals = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for res in ex.map(process_ticker, ALL_TICKERS):
            if res is None:
                continue
            rec = res["recommendation"]
            if rec not in ["LONG SNIPER", "SHORT SNIPER", "LONG MOMENTUM", "SHORT MOMENTUM"]:
                continue

            key = f"{res['ticker']}_{rec}"
            if is_duplicate(key, cache, SIGNAL_COOLDOWN_HRS):
                print(f"Duplicate skipped: {res['ticker']}")
                continue

            msg = build_signal_message(res)
            send_message(msg)
            mark_sent(key, cache)
            new_signals.append(res['ticker'])
            print(f"Signal sent: {res['ticker']} {rec}")

    save_cache(cache)

    if not new_signals:
        print("No confirmed signals this scan.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_message(
            "<b>Cycle &amp; Wave Scanner V11 (Apex Multi-Factor Engine)</b>\n\n"
            "Connected. Monitoring 226 global assets every 15 minutes.\n"
            "Confirmed signals only — no noise, no watchlist alerts.\n"
            "ADX regime filter + RSI + Z-Score + VWAP + 1:2 R:R."
        )
    else:
        run_scan()
