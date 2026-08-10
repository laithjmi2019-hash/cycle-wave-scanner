"""
main_crypto.py — Crypto engine entry point.
Scans BTC, ETH, and major liquid cryptocurrencies 24/7.
Sends 🪙 [CRYPTO] signals to Telegram (A and A+ only by default).
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
from data.universe import CRYPTO, BINANCE_PERP_MAP
from data.fetcher import fetch_crypto
from data.binance_api import get_open_interest, get_funding_rate, get_oi_history
from engines.scoring.score_engine import should_alert
from engines.risk.risk_engine import check_portfolio_risk, register_signal, calc_position_size
from telegram.bot import send_signal, send_result
from signal_tracker import log_signal, check_open_signals
from execution.binance_broker import execute_trade

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
    key = f"CRYPTO_{ticker}_{direction}"
    if key in cache:
        last = datetime.datetime.fromisoformat(cache[key])
        age  = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() / 3600
        return age < config.CRYPTO_COOLDOWN_HRS
    return False

def _mark_sent(ticker: str, direction: str, cache: dict):
    cache[f"CRYPTO_{ticker}_{direction}"] = \
        datetime.datetime.now(datetime.timezone.utc).isoformat()

def process_ticker(args) -> dict | None:
    ticker, regime_data, btc_df, eth_df = args
    data = fetch_crypto(ticker)
    if not data["ok"]:
        if data["issues"]:
            print(f"  {ticker}: DATA FAIL — {data['issues'][0]}")
        return None

    # Fetch derivatives data from Binance
    binance_sym  = data.get("binance_symbol")
    derivatives_data = None
    if binance_sym:
        try:
            from engines.crypto.derivatives import DerivativesAnalyzer
            derivatives_data = DerivativesAnalyzer().analyze(binance_sym)
        except Exception as e:
            print(f"  {ticker}: Derivatives fetch error — {e}")

    # CVD proxy
    cvd_data = None
    try:
        from engines.crypto.cvd_proxy import cvd_analysis
        cvd_data = cvd_analysis(data["df_1h"])
    except Exception:
        pass

    # Relative strength vs BTC
    rs_data = None
    if btc_df is not None:
        try:
            from engines.crypto.relative_strength import calc_crypto_rs
            rs_data = calc_crypto_rs(data["df_1h"], btc_df, eth_df)
        except Exception:
            pass

    # Run crypto engine
    try:
        from engines.crypto.crypto_engine import analyze_crypto
        signal = analyze_crypto(
            ticker           = ticker,
            df_1d            = data["df_1d"],
            df_1h            = data["df_1h"],
            df_15m           = data["df_15m"],
            regime_data      = regime_data,
            derivatives_data = derivatives_data,
            cvd_data         = cvd_data,
            rs_data          = rs_data,
        )
    except Exception as e:
        print(f"  {ticker}: Crypto engine error — {e}")
        return None

    return signal

def run_crypto_scan():
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*60}")
    print(f"CRYPTO ENGINE SCAN — {ts}")
    print(f"{'='*60}")

    # Step 1: Check open signal outcomes
    print("Checking open signal outcomes...")
    try:
        resolved = check_open_signals()
        for sig in resolved:
            if sig.get("asset_class", "CRYPTO") == "CRYPTO":
                send_result(sig)
                print(f"  Result: {sig['ticker']} {sig.get('outcome')}")
    except Exception as e:
        print(f"  Outcome check error: {e}")

    # Step 2: Crypto regime engine
    print("Computing crypto market regime...")
    try:
        from engines.regime.crypto_regime import CryptoRegimeEngine
        regime_engine = CryptoRegimeEngine()
        regime_data   = regime_engine.compute()
        print(f"  Crypto Regime: {regime_data.get('regime_class')} ({regime_data.get('score')}/100)")
    except Exception as e:
        print(f"  Crypto regime error: {e}. Using neutral defaults.")
        regime_data = {"score": 50, "regime_class": "NEUTRAL", "breakdown": {},
                       "btc_price": None, "funding_current": None}

    # Fetch BTC + ETH data once for RS calculations
    try:
        btc_data = fetch_crypto("BTC-USD")
        btc_df   = btc_data["df_1h"] if btc_data["ok"] else None
        eth_data = fetch_crypto("ETH-USD")
        eth_df   = eth_data["df_1h"] if eth_data["ok"] else None
    except Exception:
        btc_df = eth_df = None

    # Step 3: Scan all crypto tickers
    cache       = _load_cache()
    new_signals = []

    args_list = [(t, regime_data, btc_df, eth_df) for t in CRYPTO]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(process_ticker, args_list))

    # Rank candidates by score
    candidates = [r for r in results if r and r.get("total_score", 0) > 0]
    candidates.sort(key=lambda x: x.get("total_score", 0), reverse=True)

    for signal in candidates:
        ticker    = signal.get("ticker")
        direction = signal.get("direction", "LONG")
        score     = signal.get("total_score", 0)
        qc        = signal.get("quality_class", "C")

        if signal.get("hard_veto"):
            print(f"  {ticker}: VETO — {signal['hard_veto']}")
            continue

        if _is_duplicate(ticker, direction, cache):
            continue

        risk_chk = check_portfolio_risk(ticker, "crypto", qc)
        if not risk_chk["allowed"]:
            print(f"  {ticker}: Risk limit — {risk_chk['reason']}")
            continue

        sizing = calc_position_size(signal["entry"], signal["stop"], qc)
        signal["pos_size"] = sizing["formatted"]

        try:
            log_signal({**signal, "rec": f"{direction} {signal.get('strategy','')}",
                        "stop_loss_raw": signal["stop"], "target_raw": signal["target"]})
        except Exception:
            pass

        if should_alert(score):
            sent = send_signal(signal)
            if sent:
                _mark_sent(ticker, direction, cache)
                register_signal(signal)
                new_signals.append(ticker)
                print(f"  + Signal sent: {ticker} {qc} {direction} ({score}/100)")
                
                # Automated Execution
                try:
                    executed = execute_trade(signal)
                    if executed:
                        print(f"  💸 Trade executed natively on Binance Futures!")
                except Exception as e:
                    print(f"  ⚠️ Execution Exception: {e}")
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
            "🪙 [CRYPTO] <b>Dual Engine V14 — Connected</b>\n\n"
            "Crypto engine online. Scanning 25 major assets 24/7.\n"
            "OI + Funding data: Binance public API.\n"
            "Quality gate: A and A+ only (scores 68-100)."
        )
    else:
        run_crypto_scan()
