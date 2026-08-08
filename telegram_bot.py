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
from analyzer import analyze_asset, has_earnings_soon
from signal_tracker import log_signal, check_open_signals
from data_fetcher import (
    US_EQUITIES, EU_EQUITIES, CHINA_EQUITIES, UAE_EQUITIES, CRYPTO,
    ASSET_MARKET_MAP, market_is_open
)

TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID             = os.environ.get("TELEGRAM_CHAT_ID")
ALL_TICKERS         = US_EQUITIES + EU_EQUITIES + CHINA_EQUITIES + UAE_EQUITIES + CRYPTO
SIGNAL_CACHE_FILE   = "/tmp/v12_signal_cache.json"
SIGNAL_COOLDOWN_HRS = 4

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

def is_duplicate(key, cache):
    if key in cache:
        last = datetime.datetime.fromisoformat(cache[key])
        age  = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() / 3600
        return age < SIGNAL_COOLDOWN_HRS
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
        requests.post(url, json=payload, timeout=10).raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")

# ============================================================
# SCAN ONE TICKER
# ============================================================
def process_ticker(ticker):
    market = ASSET_MARKET_MAP.get(ticker, "US")
    if not market_is_open(market):
        return None
    try:
        t   = yf.Ticker(ticker)
        d1d = t.history(period="1y",  interval="1d",  prepost=False)
        d1h = t.history(period="60d", interval="1h",  prepost=False)
        d15m= t.history(period="5d",  interval="15m", prepost=False)
        if d1d.empty or d1h.empty:
            return None

        # Gate 1: Earnings filter (only for individual stocks, not crypto/ETFs)
        if "-USD" not in ticker:
            if has_earnings_soon(ticker, hours=72):
                print(f"  {ticker}: Earnings within 72h — skipped.")
                return None

        res = analyze_asset(ticker, d1d, d1h, d15m if not d15m.empty else None)
        if res:
            res["price"] = float(d1h['Close'].iloc[-1])
        return res
    except Exception as e:
        print(f"Error {ticker}: {e}")
    return None

# ============================================================
# BUILD TELEGRAM MESSAGES
# ============================================================
OUTCOME_EMOJI = {
    "TARGET HIT":  "TARGET HIT",
    "STOPPED OUT": "STOPPED OUT",
}

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
    msg += f"<b>Risk/Reward:</b> {res['rr']}\n"
    msg += f"<b>Position Size:</b> {res['pos_size']}\n\n"
    msg += f"<i>{res['reason']}</i>"
    return msg

def build_result_message(sig):
    outcome = sig.get("outcome", "UNKNOWN")
    label   = OUTCOME_EMOJI.get(outcome, outcome)
    pnl     = sig.get("pnl_pct", 0)
    sign    = "+" if pnl >= 0 else ""
    msg  = f"<b>TRADE RESULT: {label}</b>\n\n"
    msg += f"<b>Asset:</b> {sig['ticker']}\n"
    msg += f"<b>Direction:</b> {sig['rec']}\n"
    msg += f"<b>Entry:</b> ${sig['entry']:.4f}\n"
    msg += f"<b>Exit:</b> ${sig.get('exit_price', 0):.4f}\n"
    msg += f"<b>P&amp;L:</b> {sign}{pnl:.2f}%\n"
    msg += f"<b>Duration:</b> {sig.get('age_hours', 0):.1f} hours\n"
    msg += f"<b>Stop was:</b> ${sig['stop']:.4f} | <b>Target was:</b> ${sig['target']:.4f}"
    return msg

# ============================================================
# MAIN SCAN
# ============================================================
def run_scan():
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"V12 Scan started at {ts}")

    # ── Step 1: Check open signals for outcomes ──────────────────────────
    print("Checking open signal outcomes...")
    resolved = check_open_signals()
    for sig in resolved:
        msg = build_result_message(sig)
        send_message(msg)
        print(f"Result sent: {sig['ticker']} {sig.get('outcome')}")

    # ── Step 2: Scan all tickers for new signals ─────────────────────────
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
            if is_duplicate(key, cache):
                print(f"Duplicate skipped: {res['ticker']}")
                continue

            # Send Telegram signal
            msg = build_signal_message(res)
            send_message(msg)
            mark_sent(key, cache)
            new_signals.append(res['ticker'])
            print(f"Signal sent: {res['ticker']} {rec} {res.get('stars','')}")

            # Log to signal tracker for outcome tracking
            try:
                log_signal(res)
            except Exception as e:
                print(f"Signal log error: {e}")

    save_cache(cache)
    print(f"Scan complete. {len(new_signals)} new signal(s). {len(resolved)} outcome(s) resolved.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_message(
            "<b>Cycle &amp; Wave Scanner V12 (Institutional Grade)</b>\n\n"
            "Connected. Monitoring 226 global assets every 15-20 minutes.\n\n"
            "<b>V12 Upgrades:</b>\n"
            "- Proper daily-reset VWAP\n"
            "- 15-minute timeframe confirmation\n"
            "- Earnings calendar filter (72h block)\n"
            "- Position sizing in every signal\n"
            "- Signal outcome tracking (Target Hit / Stopped Out)"
        )
    else:
        run_scan()
