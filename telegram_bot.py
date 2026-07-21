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

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID")

ALL_TICKERS = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES + CRYPTO

SIGNAL_CACHE_FILE    = "/tmp/v11_signal_cache.json"
SIGNAL_COOLDOWN_HRS  = 4
HEARTBEAT_COOLDOWN_HRS = 4

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
        if (datetime.datetime.utcnow() - last).total_seconds() / 3600 < cooldown_hrs:
            return True
    return False

def mark_sent(key, cache):
    cache[key] = datetime.datetime.utcnow().isoformat()

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
WATCH_COOLDOWN_HRS = 6  # Don't re-alert the same watchlist item within 6 hours

# ============================================================
# SCAN ONE TICKER
# ============================================================
def process_ticker(ticker):
    """Fetch data and analyze a single ticker."""
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
# BUILD TELEGRAM MESSAGES
# ============================================================
def build_signal_message(res):
    rec   = res["recommendation"]
    stars = STAR_MAP.get(res.get("stars", "STAR_2"), "[**] DEVELOPING")
    label = "MOMENTUM BREAKOUT" if "MOMENTUM" in rec else rec
    msg  = f"<b>{label}</b>\n"
    msg += f"{stars}\n\n"
    msg += f"<b>Asset:</b> {res['ticker']}\n"
    msg += f"<b>Price:</b> ${res['price']:.2f}\n"
    msg += f"<b>RSI-14:</b> {res['rsi']}\n"
    msg += f"<b>ADX:</b> {res['adx']}\n"
    msg += f"<b>Z-Score:</b> {res['zscore']}\n"
    msg += f"<b>Target:</b> {res['upside']} (4 ATR)\n"
    msg += f"<b>Stop Loss:</b> {res['stop_loss']} (2 ATR)\n"
    msg += f"<b>Risk/Reward:</b> {res['rr']}\n\n"
    msg += f"<i>{res['reason']}</i>"
    return msg

def build_watch_message(ticker, price, watch):
    direction = "LONG (BUY)" if "LONG" in watch["type"] else "SHORT (SELL)"
    emoji = "WATCH - Approaching LONG" if "LONG" in watch["type"] else "WATCH - Approaching SHORT"
    msg  = f"<b>[WATCHLIST] {emoji}</b>\n\n"
    msg += f"<b>Asset:</b> {ticker}\n"
    msg += f"<b>Price:</b> ${price:.4f}\n"
    msg += f"<b>Direction:</b> {direction}\n"
    msg += f"<b>RSI-14:</b> {watch['rsi']}\n"
    msg += f"<b>ADX:</b> {watch['adx']} ({watch['regime']})\n"
    msg += f"<b>Z-Score:</b> {watch['zscore']}\n"
    msg += f"<b>Conditions Met:</b> {watch['conditions_met']}/3\n\n"
    msg += f"<b>Still Needed:</b>\n<i>{watch['missing']}</i>\n\n"
    msg += "<i>This is a WATCHLIST alert. Not a confirmed trade signal yet. Monitor closely.</i>"
    return msg

# ============================================================
# MAIN SCAN
# ============================================================
def run_scan():
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"V11 Scan started at {ts}")

    cache = load_cache()
    new_signals  = []
    new_watchlist = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for res in ex.map(process_ticker, ALL_TICKERS):
            if res is None:
                continue

            ticker = res["ticker"]
            price  = res.get("price", 0)
            rec    = res["recommendation"]

            # --- Full Confirmed Signals ---
            if rec in ["LONG SNIPER", "SHORT SNIPER", "LONG MOMENTUM", "SHORT MOMENTUM"]:
                key = f"{ticker}_{rec}"
                if is_duplicate(key, cache, SIGNAL_COOLDOWN_HRS):
                    print(f"Duplicate signal skipped: {ticker}")
                    continue
                msg = build_signal_message(res)
                send_message(msg)
                mark_sent(key, cache)
                new_signals.append(ticker)
                print(f"Signal sent: {ticker} {rec}")

            # --- Watchlist Near-Miss Alerts ---
            elif res.get("watch_alert"):
                watch = res["watch_alert"]
                watch_key = f"{ticker}_watch_{watch['type']}"
                if is_duplicate(watch_key, cache, WATCH_COOLDOWN_HRS):
                    print(f"Duplicate watch skipped: {ticker}")
                    continue
                msg = build_watch_message(ticker, price, watch)
                send_message(msg)
                mark_sent(watch_key, cache)
                new_watchlist.append(ticker)
                print(f"Watch alert sent: {ticker} {watch['type']}")

    save_cache(cache)

    # Heartbeat — only once per 4 hours if nothing was sent at all
    if not new_signals and not new_watchlist:
        hb_key = "heartbeat_heartbeat"
        if not is_duplicate(hb_key, cache, HEARTBEAT_COOLDOWN_HRS):
            send_message(
                "<b>Scan Complete (V11 Apex)</b>\n\n"
                "No new signals or watchlist alerts. Monitoring 245+ global assets "
                "every 15 minutes across US, EU, China, UAE, and Crypto.\n\n"
                "<i>The system fires signals when all conditions align, "
                "and watchlist alerts when assets are getting close.</i>"
            )
            mark_sent(hb_key, cache)
            save_cache(cache)
            print("Heartbeat sent.")
        else:
            print("No new activity. Heartbeat already sent recently.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_message(
            "<b>Cycle &amp; Wave Scanner V11 (Apex Multi-Factor Engine)</b>\n\n"
            "Connected. Monitoring 245+ global assets every 15 minutes.\n"
            "V11 improvements: ADX regime filter, Z-Score confluence, "
            "VWAP alignment, 1:2 R:R targets, and star-rated signals."
        )
    else:
        run_scan()
