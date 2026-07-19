import pandas as pd
import numpy as np
import ta

# ─────────────────────────────────────────────────────────────────
# CORE INDICATORS (V6 Inverted R:R Scalp Engine)
# ─────────────────────────────────────────────────────────────────
def calculate_indicators(df: pd.DataFrame, full: bool = True) -> pd.DataFrame:
    df = df.copy()

    # 14-period RSI
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    
    # Bollinger Bands (20, 2)
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2.0)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    
    # ATR for stop loss and target sizing
    df['atr_10'] = ta.volatility.AverageTrueRange(
        df['High'], df['Low'], df['Close'], window=10).average_true_range()

    return df

# ─────────────────────────────────────────────────────────────────
# RISK-TO-REWARD CALCULATOR (signed-aware)
# ─────────────────────────────────────────────────────────────────
def _calc_rr(entry: float, stop: float, target: float, is_short: bool = False):
    if is_short:
        reward = entry - target
        risk   = stop  - entry
    else:
        reward = target - entry
        risk   = entry  - stop

    if risk <= 0 or reward <= 0:
        return 0, "N/A", "N/A", "N/A", False

    rr        = reward / risk
    move_pct  = (reward / entry) * 100
    risk_pct  = (risk   / entry) * 100
    direction = "-" if is_short else "+"

    return (
        round(rr, 2),
        f"{direction}{round(move_pct, 2)}%",
        f"-{round(risk_pct, 2)}%",
        f"1:{round(rr, 2)}",
        True  # Always return True because Inverted R:R is designed this way
    )

# ─────────────────────────────────────────────────────────────────
# EQUITY ANALYZER — V6 Inverted Scalp
# ─────────────────────────────────────────────────────────────────
def analyze_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame,
                  data_15m: pd.DataFrame, spy_1d: pd.DataFrame) -> dict:
    
    EMPTY = {"ticker": ticker, "recommendation": "AVOID", "upside": "N/A",
             "stop_loss": "N/A", "rr": "N/A", "signal": "Avoid", "score": 0,
             "reason": "Insufficient Data", "rsi": "N/A",
             "bb_status": "N/A", "current_price": 0}

    df_1h  = calculate_indicators(data_1h,  full=True).dropna()
    df_15m = calculate_indicators(data_15m, full=False).dropna()

    if df_1h.empty or df_15m.empty:
        return EMPTY

    curr_15m = df_15m.iloc[-1]

    # Scalp Variables
    rsi       = curr_15m['rsi']
    bb_lower  = curr_15m['bb_lower']
    bb_upper  = curr_15m['bb_upper']
    entry     = curr_15m['Close']
    atr_15m   = curr_15m['atr_10']
    
    # BB Status string for UI
    if entry < bb_lower: bb_status = "Below Lower Band"
    elif entry > bb_upper: bb_status = "Above Upper Band"
    else: bb_status = "Inside Bands"

    score  = 50
    signal = "Avoid"
    reason = []
    rec    = "AVOID"
    upside_str = "N/A"
    rr_str = "N/A"
    stop = None

    is_bull_setup = (
        rsi < 30 and
        entry < bb_lower
    )
    
    is_short_setup = (
        rsi > 70 and
        entry > bb_upper
    )

    if is_bull_setup:
        signal = "Inverted Scalp"; score = 95; rec = "LONG SCALP"
        reason.append("HIGH-WINRATE SCALP: RSI < 30 outside Lower BB. Target microscopic mean-reversion with wide stop.")

        stop   = entry - (3.0 * atr_15m)
        target = entry + (1.0 * atr_15m)
        
        rr, upside_str, _, rr_str, _ = _calc_rr(entry, stop, target, is_short=False)

    elif is_short_setup:
        signal = "Inverted Scalp"; score = 95; rec = "SHORT SCALP"
        reason.append("HIGH-WINRATE SCALP: RSI > 70 outside Upper BB. Target microscopic mean-reversion with wide stop.")

        stop   = entry + (3.0 * atr_15m)
        target = entry - (1.0 * atr_15m)
        
        rr, upside_str, _, rr_str, _ = _calc_rr(entry, stop, target, is_short=True)
             
    else:
        signal = "Waiting"; score = 30; rec = "WAIT FOR EXTREME"
        reason.append("Waiting for price to breach Bollinger Bands alongside RSI extreme.")

    stop_str = f"${round(stop, 2)}" if stop is not None else "N/A"

    return {
        "ticker":         ticker,
        "recommendation": rec,
        "upside":         upside_str,
        "stop_loss":      stop_str,
        "rr":             rr_str,
        "signal":         signal,
        "score":          score,
        "reason":         " ".join(reason),
        "rsi":            round(rsi, 1),
        "bb_status":      bb_status,
        "current_price":  round(entry, 4)
    }


# ─────────────────────────────────────────────────────────────────
# CRYPTO ANALYZER — V6 Inverted Scalp
# ─────────────────────────────────────────────────────────────────
def analyze_crypto_asset(ticker: str, data_1d: pd.DataFrame, data_1h: pd.DataFrame,
                         data_15m: pd.DataFrame, btc_1d: pd.DataFrame) -> dict:
    
    # Exact same logic as equities for the Scalp engine
    return analyze_asset(ticker, data_1d, data_1h, data_15m, btc_1d)
