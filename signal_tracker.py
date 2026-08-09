"""
SIGNAL TRACKER — Persistent outcome logging via GitHub API.
Stores signal_log.json in the repo. Every scan:
  1. Checks open signals vs current price → sends TARGET HIT / STOPPED OUT
  2. Logs newly fired signals
"""
import os
import json
import base64
import requests
import datetime
import yfinance as yf

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO         = "laithjmi2019-hash/cycle-wave-scanner"
LOG_FILE     = "data/signal_log.json"
API_BASE     = f"https://api.github.com/repos/{REPO}/contents/{LOG_FILE}"
EXPIRE_HOURS = 72   # Auto-expire open signals after 72 hours

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

def _fetch_log():
    """Read signal_log.json from GitHub repo. Returns (data_dict, sha)."""
    try:
        r = requests.get(API_BASE, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            sha     = r.json()["sha"]
            return json.loads(content), sha
        if r.status_code == 404:
            return {"open": [], "resolved": []}, None
    except Exception as e:
        print(f"Signal tracker read error: {e}")
    return {"open": [], "resolved": []}, None

def _save_log(data, sha):
    """Write signal_log.json to GitHub repo."""
    if not GITHUB_TOKEN:
        print("No GITHUB_TOKEN — skipping signal log save.")
        return
    try:
        content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
        body = {
            "message": "chore: update signal log",
            "content": content,
        }
        if sha:
            body["sha"] = sha
        r = requests.put(API_BASE, headers=HEADERS, json=body, timeout=10)
        if r.status_code not in (200, 201):
            print(f"Signal tracker save error: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"Signal tracker save exception: {e}")

def _current_price(ticker):
    """Get latest close price for a ticker."""
    try:
        t  = yf.Ticker(ticker)
        df = t.history(period="1d", interval="5m")
        if not df.empty:
            return float(df['Close'].iloc[-1])
    except Exception:
        pass
    return None

def log_signal(signal_dict):
    """
    Add a newly fired signal to the open log.
    signal_dict keys: ticker, recommendation, entry, stop_loss_raw,
                      target_raw, stars, timestamp (ISO str)
    """
    data, sha = _fetch_log()
    rec = signal_dict.get("recommendation", signal_dict.get("rec", "UNKNOWN"))
    uid = f"{signal_dict['ticker']}_{rec}_{signal_dict['timestamp'][:10]}"

    # Avoid duplicating same signal on same day
    existing_ids = [s.get("id") for s in data["open"]]
    if uid in existing_ids:
        return

    data["open"].append({
        "id":          uid,
        "ticker":      signal_dict["ticker"],
        "rec":         rec,
        "asset_class": signal_dict.get("asset_class", "STOCKS"),
        "entry":       signal_dict["entry"],
        "stop":        signal_dict["stop_loss_raw"],
        "target":      signal_dict["target_raw"],
        "stars":       signal_dict.get("stars", "STAR_2"),
        "timestamp":   signal_dict["timestamp"],
    })

    # Keep only last 100 resolved
    data["resolved"] = data["resolved"][-100:]
    _save_log(data, sha)
    print(f"Signal logged: {uid}")

def check_open_signals():
    """
    Checks all open signals vs current price.
    Returns list of resolved signal dicts with 'outcome' key.
    """
    data, sha = _fetch_log()
    if not data["open"]:
        return []

    now        = datetime.datetime.now(datetime.timezone.utc)
    resolved   = []
    still_open = []

    for sig in data["open"]:
        ticker  = sig["ticker"]
        entry   = sig["entry"]
        stop    = sig["stop"]
        target  = sig["target"]
        direction = sig["direction"]

        ts      = datetime.datetime.fromisoformat(sig["timestamp"])
        age_hrs = (now - ts).total_seconds() / 3600

        price = _current_price(ticker)

        outcome = None
        if price is None:
            still_open.append(sig)
            continue

        if direction == "LONG":
            if price <= stop:
                outcome = "STOPPED OUT"
            elif price >= target:
                outcome = "TARGET HIT"
        else:  # SHORT
            if price >= stop:
                outcome = "STOPPED OUT"
            elif price <= target:
                outcome = "TARGET HIT"

        if outcome is None and age_hrs > EXPIRE_HOURS:
            outcome = f"EXPIRED ({age_hrs:.0f}h)"

        if outcome:
            sig["outcome"]       = outcome
            sig["exit_price"]    = price
            sig["age_hours"]     = round(age_hrs, 1)
            sig["pnl_pct"]       = round(
                ((price - entry) / entry * 100) * (1 if direction == "LONG" else -1), 2
            )
            resolved.append(sig)
            data["resolved"].append(sig)
        else:
            still_open.append(sig)

    if resolved:
        data["open"] = still_open
        _save_log(data, sha)

    return resolved
