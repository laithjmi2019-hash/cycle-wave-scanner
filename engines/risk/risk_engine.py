"""
engines/risk/risk_engine.py — Portfolio risk tracking and position sizing.
Tracks open risk, correlation clusters, and sector exposure.
All signals pass through this before being sent.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import json
import datetime
import config

RISK_STATE_FILE = "/tmp/dual_engine_risk_state.json"

# Correlation clusters — assets in same cluster count together
CORRELATION_CLUSTERS = {
    "big_tech":     ["AAPL", "MSFT", "GOOGL", "META", "AMZN"],
    "semis":        ["NVDA", "AMD", "INTC", "AVGO", "QCOM"],
    "btc_cluster":  ["BTC-USD", "ETH-USD"],
    "alt_l1":       ["SOL-USD", "ADA-USD", "AVAX-USD", "DOT-USD", "NEAR-USD"],
    "defi":         ["UNI-USD", "AAVE-USD", "LINK-USD", "GRT-USD"],
    "eu_banks":     ["BNP.PA", "DBK.DE", "BBVA.MC", "SAN.MC", "HSBA.L"],
    "oil_majors":   ["XOM", "CVX", "TTE.PA", "SHEL.L", "BP.L"],
}

TICKER_CLUSTER = {}
for cluster, tickers in CORRELATION_CLUSTERS.items():
    for t in tickers:
        TICKER_CLUSTER[t] = cluster

def _load_state() -> dict:
    try:
        if os.path.exists(RISK_STATE_FILE):
            with open(RISK_STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"open_positions": [], "total_risk_pct": 0.0}

def _save_state(state: dict):
    try:
        with open(RISK_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def calc_position_size(entry: float, stop: float, quality_class: str) -> dict:
    """
    Calculate position size based on quality-adjusted risk.
    Returns: {"units", "dollar_risk", "risk_pct", "quality_mult"}
    """
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return {"units": 0, "dollar_risk": 0, "risk_pct": 0, "quality_mult": 0}

    base_risk    = config.ACCOUNT_SIZE_USD * config.BASE_RISK_PCT   # $100 on $10k
    quality_mult = config.QUALITY_RISK_MULT.get(quality_class, 0.0)
    dollar_risk  = base_risk * quality_mult
    units        = dollar_risk / risk_per_unit

    return {
        "units":        round(units, 1),
        "dollar_risk":  round(dollar_risk, 2),
        "risk_pct":     round(quality_mult * config.BASE_RISK_PCT * 100, 3),
        "quality_mult": quality_mult,
        "formatted":    f"{units:.1f} units (${dollar_risk:.0f} risk, {quality_mult*100:.0f}% base)"
    }

def check_portfolio_risk(ticker: str, sector: str, quality_class: str) -> dict:
    """
    Check if adding this position violates portfolio risk limits.
    Returns: {"allowed": bool, "reason": str}
    """
    state = _load_state()
    open_pos = state.get("open_positions", [])

    # Check max total positions open
    total_risk = sum(p.get("risk_pct", 1.0) for p in open_pos)
    if total_risk >= config.MAX_PORTFOLIO_RISK_PCT:
        return {"allowed": False,
                "reason": f"Portfolio risk at {total_risk:.1f}% (max {config.MAX_PORTFOLIO_RISK_PCT}%)"}

    # Check sector concentration
    sector_risk = sum(p.get("risk_pct", 1.0) for p in open_pos
                      if p.get("sector") == sector)
    if sector_risk >= config.MAX_SECTOR_RISK_PCT:
        return {"allowed": False,
                "reason": f"Sector {sector} at {sector_risk:.1f}% risk (max {config.MAX_SECTOR_RISK_PCT}%)"}

    # Check correlation cluster
    cluster = TICKER_CLUSTER.get(ticker)
    if cluster:
        cluster_count = sum(1 for p in open_pos
                            if TICKER_CLUSTER.get(p.get("ticker")) == cluster)
        if cluster_count >= config.MAX_CORRELATED_POSITIONS:
            return {"allowed": False,
                    "reason": f"Correlation cluster '{cluster}' already has "
                              f"{cluster_count}/{config.MAX_CORRELATED_POSITIONS} positions"}

    return {"allowed": True, "reason": ""}

def register_signal(signal: dict):
    """Register a new signal in the risk state."""
    state = _load_state()
    sizing = calc_position_size(
        signal.get("entry", 0),
        signal.get("stop", 0),
        signal.get("quality_class", "B"),
    )
    position = {
        "ticker":    signal.get("ticker"),
        "sector":    signal.get("sector", ""),
        "direction": signal.get("direction"),
        "entry":     signal.get("entry"),
        "stop":      signal.get("stop"),
        "target":    signal.get("target"),
        "risk_pct":  sizing["risk_pct"],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "quality":   signal.get("quality_class"),
    }
    state["open_positions"].append(position)
    state["total_risk_pct"] = sum(p.get("risk_pct", 0) for p in state["open_positions"])
    # Expire positions older than 72 hours
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=72)
    state["open_positions"] = [
        p for p in state["open_positions"]
        if datetime.datetime.fromisoformat(p["timestamp"]) > cutoff
    ]
    _save_state(state)

def get_portfolio_summary() -> dict:
    """Return current portfolio risk state."""
    state = _load_state()
    return {
        "open_count":   len(state.get("open_positions", [])),
        "total_risk":   state.get("total_risk_pct", 0.0),
        "positions":    state.get("open_positions", []),
    }
