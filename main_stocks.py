"""
main_stocks.py — Stocks engine entry point.
Scans US / EU / China-HK / UAE equities.
Sends 📈 [STOCKS] signals to Telegram (A and A+ only by default).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime
import json
import concurrent.futures

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

import config
from data.universe import ALL_STOCKS, ASSET_MARKET_MAP, ASSET_CLASS_MAP, market_is_open
from data.fetcher import fetch_stock, fetch_regime_data
from engines.scoring.score_engine import should_alert
from engines.risk.risk_engine import check_portfolio_risk, register_signal, calc_position_size
from telegram.bot import send_signal, send_result
from signal_tracker import log_signal, check_open_signals

# ── DEDUP CACHE ───────────────────────────────────────────────────────────
def _load_cache() -> dict:
    try:
        if os.path.exists(config.SIGNAL_CACHE_FILE):
            with open(config.SIGNAL_CACHE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_cache(cache: dict):
    try:
        with open(config.SIGNAL_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

def _is_duplicate(ticker: str, direction: str, cache: dict) -> bool:
    key = f"STOCKS_{ticker}_{direction}"
    if key in cache:
        last = datetime.datetime.fromisoformat(cache[key])
        age  = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() / 3600
        return age < config.STOCK_COOLDOWN_HRS
    return False

def _mark_sent(ticker: str, direction: str, cache: dict):
    cache[f"STOCKS_{ticker}_{direction}"] = \
        datetime.datetime.now(datetime.timezone.utc).isoformat()

# ── PROCESS ONE TICKER ────────────────────────────────────────────────────
def process_ticker(args) -> dict | None:
    ticker, regime_data = args
    market = ASSET_MARKET_MAP.get(ticker, "US")
    if not market_is_open(market):
        return None

    # Fetch + validate data
    data = fetch_stock(ticker)
    if not data["ok"]:
        if data["issues"]:
            print(f"  {ticker}: DATA FAIL - {data['issues'][0]}")
        return None

    # Run stocks engine
    try:
        from engines.stocks.stock_engine import analyze_stock
        signal = analyze_stock(
            ticker    = ticker,
            df_1d     = data["df_1d"],
            df_1h     = data["df_1h"],
            df_15m    = data["df_15m"],
            regime_data = regime_data,
        )
    except Exception as e:
        print(f"  {ticker}: Engine error - {e}")
        return None

    return signal

# ── MAIN SCAN ─────────────────────────────────────────────────────────────
def run_stocks_scan():
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*60}")
    print(f"STOCKS ENGINE SCAN - {ts}")
    print(f"{'='*60}")

    # Step 1: Check open signal outcomes
    print("Checking open signal outcomes...")
    try:
        resolved = check_open_signals()
        for sig in resolved:
            if sig.get("asset_class", "STOCKS") == "STOCKS":
                send_result(sig)
                print(f"  Result: {sig['ticker']} {sig.get('outcome')}")
    except Exception as e:
        print(f"  Outcome check error: {e}")

    # Step 2: Fetch regime data once (shared across all tickers)
    print("Fetching market regime data...")
    try:
        from engines.regime.stock_regime import StockRegimeEngine
        regime_engine = StockRegimeEngine()
        regime_data   = regime_engine.compute()
        print(f"  Stock Regime: {regime_data.get('regime_class')} ({regime_data.get('score')}/100)")
    except Exception as e:
        print(f"  Regime engine error: {e}. Using neutral defaults.")
        regime_data = {"score": 50, "regime_class": "NEUTRAL", "breakdown": {}, "vix": None}

    # Hard veto: PANIC regime blocks all scans
    if regime_data.get("regime_class") == "PANIC":
        print("  PANIC regime detected. No stock long signals allowed.")
        return

    # Step 3: Scan all stock tickers in parallel
    cache       = _load_cache()
    new_signals = []

    args_list = [(t, regime_data) for t in ALL_STOCKS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(process_ticker, args_list))

    # Filter, rank, and send signals
    candidates = [r for r in results if r and r.get("total_score", 0) > 0]
    candidates.sort(key=lambda x: x.get("total_score", 0), reverse=True)

    for signal in candidates:
        ticker    = signal.get("ticker")
        direction = signal.get("direction", "LONG")
        score     = signal.get("total_score", 0)
        qc        = signal.get("quality_class", "C")

        # Check hard veto
        if signal.get("hard_veto"):
            print(f"  {ticker}: VETO - {signal['hard_veto']}")
            continue

        # Deduplication
        if _is_duplicate(ticker, direction, cache):
            continue

        # Portfolio risk check
        sector   = signal.get("sector", "")
        risk_chk = check_portfolio_risk(ticker, sector, qc)
        if not risk_chk["allowed"]:
            print(f"  {ticker}: Risk limit - {risk_chk['reason']}")
            continue

        # Quality gate — enrich signal with position size
        sizing = calc_position_size(signal["entry"], signal["stop"], qc)
        signal["pos_size"] = sizing["formatted"]

        # Log to research database
        try:
            log_signal({**signal, "rec": f"{direction} {signal.get('strategy','')}",
                        "stop_loss_raw": signal["stop"], "target_raw": signal["target"]})
        except Exception:
            pass

        # Send to Telegram if meets threshold
        if should_alert(score):
            sent = send_signal(signal)
            if sent:
                _mark_sent(ticker, direction, cache)
                register_signal(signal)
                new_signals.append(ticker)
                print(f"  + Signal sent: {ticker} {qc} {direction} ({score}/100)")
        else:
            print(f"  - Logged only: {ticker} {qc} {direction} ({score}/100)")

    _save_cache(cache)
    print(f"\nScan complete. {len(new_signals)} signal(s) sent. "
          f"{len(candidates)} candidate(s) found.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        from telegram.bot import send_raw
        send_raw(
            "📈 [STOCKS] <b>Dual Engine V14 — Connected</b>\n\n"
            "Stocks engine online. Scanning US/EU/China/UAE equities.\n"
            "Quality gate: A and A+ only (scores 68-100).\n"
            "Portfolio risk controls active."
        )
    else:
        run_stocks_scan()
