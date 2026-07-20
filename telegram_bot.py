import os
import sys
import json
import requests
import datetime
import yfinance as yf
import concurrent.futures

# Load env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyzer import analyze_asset
from data_fetcher import US_EQUITIES, EU_EQUITIES, CHINA_EQUITIES, UAE_EQUITIES, CRYPTO

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TICKERS = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES + CRYPTO

# ============================================================
# SIGNAL DEDUPLICATION: Do not resend the same signal
# within 4 hours. Uses a JSON file to track last sent times.
# ============================================================
SIGNAL_CACHE_FILE = "/tmp/signal_cache.json"
SIGNAL_COOLDOWN_HOURS = 4

def load_signal_cache():
    try:
        if os.path.exists(SIGNAL_CACHE_FILE):
            with open(SIGNAL_CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_signal_cache(cache):
    try:
        with open(SIGNAL_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

def is_duplicate(ticker, signal_type, cache):
    """Returns True if this signal was already sent within the cooldown window."""
    key = f"{ticker}_{signal_type}"
    if key in cache:
        last_sent = datetime.datetime.fromisoformat(cache[key])
        age_hours = (datetime.datetime.utcnow() - last_sent).total_seconds() / 3600
        if age_hours < SIGNAL_COOLDOWN_HOURS:
            return True
    return False

def mark_signal_sent(ticker, signal_type, cache):
    key = f"{ticker}_{signal_type}"
    cache[key] = datetime.datetime.utcnow().isoformat()

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing Telegram credentials.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending message: {e}")

def process_ticker(ticker):
    """Fetch data and analyze a single ticker."""
    try:
        t = yf.Ticker(ticker)
        d1d = t.history(period="1y", interval="1d", prepost=False)
        d1h = t.history(period="60d", interval="1h", prepost=False)
        if d1d.empty or d1h.empty:
            return None
        res = analyze_asset(ticker, d1d, d1h, None)
        if res and res["recommendation"] in ["LONG SNIPER", "SHORT SNIPER", "LONG MOMENTUM", "SHORT MOMENTUM"]:
            res["price"] = d1h['Close'].iloc[-1]
            return res
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
    return None

def run_scan():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Starting V10.1 Global Scan at {now}")
    
    cache = load_signal_cache()
    signals_found = []
    new_signals = []

    # Concurrent scan of all 245 tickers
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(process_ticker, TICKERS)
        for res in results:
            if res:
                signals_found.append(res)

    for res in signals_found:
        ticker = res["ticker"]
        rec = res["recommendation"]
        
        # Skip duplicate signals sent within the last 4 hours
        if is_duplicate(ticker, rec, cache):
            print(f"Skipping duplicate signal for {ticker} ({rec})")
            continue
        
        # It's a new signal — send it!
        emoji = "🚀" if "MOMENTUM" in rec else "🎯"
        msg  = f"{emoji} <b>{rec}</b> {emoji}\n\n"
        msg += f"<b>Asset:</b> {ticker}\n"
        msg += f"<b>Price:</b> ${res['price']:.2f}\n"
        msg += f"<b>RSI-14:</b> {res['rsi']}\n"
        msg += f"<b>Target:</b> {res['upside']}\n"
        msg += f"<b>Stop Loss:</b> {res['stop_loss']}\n"
        msg += f"<b>Risk/Reward:</b> {res['rr']}\n\n"
        msg += f"<i>{res['reason']}</i>"
        
        send_telegram_message(msg)
        mark_signal_sent(ticker, rec, cache)
        new_signals.append(ticker)
        print(f"New signal sent for {ticker}: {rec}")

    save_signal_cache(cache)

    # Only send heartbeat once every 4 hours (not every 15 minutes)
    heartbeat_key = "heartbeat"
    if not new_signals:
        if not is_duplicate("heartbeat", "heartbeat", cache):
            send_telegram_message(
                "✅ <b>Scan Complete</b>\n\n"
                "No new Sniper or Momentum signals found. "
                "Continuing to monitor 245 assets every 15 minutes..."
            )
            mark_signal_sent("heartbeat", "heartbeat", cache)
            save_signal_cache(cache)
            print("Heartbeat sent.")
        else:
            print("No new signals. Heartbeat already sent recently, skipping.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_telegram_message(
            "✅ <b>Cycle &amp; Wave Scanner V10.1 (Global Edition)</b>\n\n"
            "Your automated background scanner has successfully connected to Telegram "
            "and is now tracking 245 global assets (US, EU, China, UAE, Crypto)."
        )
    else:
        run_scan()
