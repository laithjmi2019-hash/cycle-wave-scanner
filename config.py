"""
config.py — Single source of truth for all system parameters.
Every threshold, toggle, weight, and credential lives here.
Change values here; never hardcode in engine files.
"""
import os

# ═══════════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")   # single chat for both

# ═══════════════════════════════════════════════════════════════════════
# SIGNAL QUALITY ALERT THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════
SCORE_THRESHOLDS = {
    "A+": 82,   # Elite — always alert
    "A":  68,   # High quality — always alert
    "B+": 54,   # Selective — OFF by default (logging/research only)
    "B":  40,   # Watchlist — never alert
    "C":   0,   # No trade — never alert
}
# Production default: only A and A+ go to Telegram
B_PLUS_ALERTS_ENABLED = os.environ.get("B_PLUS_ALERTS", "true").lower() == "true"
MIN_ALERT_SCORE = SCORE_THRESHOLDS["A"]   # 68

# ═══════════════════════════════════════════════════════════════════════
# HARD VETO THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════
VIX_PANIC_BLOCK    = 35.0   # Absolute block all long mean-reversion
VIX_CAUTION        = 25.0   # Caution zone — raises score bar
MIN_RR_RATIO       = 1.5    # Minimum acceptable Risk:Reward (1:1.5)
STALE_DATA_MINUTES = 120    # Data older than this = stale feed veto
MIN_VOLUME_BARS    = 3      # Require at least 3 non-zero volume bars in last 5

# ═══════════════════════════════════════════════════════════════════════
# EARNINGS / EVENTS
# ═══════════════════════════════════════════════════════════════════════
# Test alternatives: 24, 48, 72, 96 hours — current baseline 72
EARNINGS_BLOCK_HOURS = int(os.environ.get("EARNINGS_BLOCK_HOURS", 72))

# ═══════════════════════════════════════════════════════════════════════
# ATR STOP / TARGET — baseline from V13 backtesting
# ═══════════════════════════════════════════════════════════════════════
STOP_ATR_MULT   = 2.0
TARGET_ATR_MULT = 4.0

# ═══════════════════════════════════════════════════════════════════════
# POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════
ACCOUNT_SIZE_USD     = 10_000.0
BASE_RISK_PCT        = 0.01        # 1% risk per trade = $100 on $10k
QUALITY_RISK_MULT = {
    "A+": 1.00,
    "A":  0.75,
    "B+": 0.50,
    "B":  0.25,
    "C":  0.00,
}

# ═══════════════════════════════════════════════════════════════════════
# PORTFOLIO RISK CONTROLS
# ═══════════════════════════════════════════════════════════════════════
MAX_PORTFOLIO_RISK_PCT    = 5.0   # Max % of account open risk at any time
MAX_SECTOR_RISK_PCT       = 2.0   # Max % of account in one sector
MAX_CORRELATED_POSITIONS  = 2     # Max simultaneous positions in same correlation cluster

# ═══════════════════════════════════════════════════════════════════════
# SIGNAL DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════
STOCK_COOLDOWN_HRS  = 4
CRYPTO_COOLDOWN_HRS = 4
SIGNAL_CACHE_FILE   = "/tmp/dual_engine_cache.json"

# ═══════════════════════════════════════════════════════════════════════
# GITHUB — signal tracking persistence
# ═══════════════════════════════════════════════════════════════════════
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "laithjmi2019-hash/cycle-wave-scanner"
LOG_FILE     = "data/signal_log.json"

# ═══════════════════════════════════════════════════════════════════════
# REGIME SCORE → CLASS MAPPING
# ═══════════════════════════════════════════════════════════════════════
REGIME_CLASSES = {
    (80, 100): "STRONG_RISK_ON",
    (60,  79): "MODERATE_RISK_ON",
    (40,  59): "NEUTRAL",
    (20,  39): "RISK_OFF",
    ( 0,  19): "PANIC",
}

def regime_class(score: float) -> str:
    for (lo, hi), label in REGIME_CLASSES.items():
        if lo <= score <= hi:
            return label
    return "NEUTRAL"

# ═══════════════════════════════════════════════════════════════════════
# STOCKS — SCORING WEIGHTS (must sum to 100)
# ═══════════════════════════════════════════════════════════════════════
STOCK_SCORE_WEIGHTS = {
    "market_regime":    20,
    "relative_strength":18,
    "participation":    14,
    "price_structure":  14,
    "liquidity":        12,
    "catalyst":         10,
    "volatility":        6,
    "rr_quality":        6,
}

# ═══════════════════════════════════════════════════════════════════════
# CRYPTO — SCORING WEIGHTS (must sum to 100)
# ═══════════════════════════════════════════════════════════════════════
CRYPTO_SCORE_WEIGHTS = {
    "btc_macro_regime":  20,
    "relative_strength": 16,
    "derivatives":       16,
    "flow_cvd":          14,
    "liquidity_structure":12,
    "participation":     10,
    "volatility":         6,
    "rr_quality":         6,
}

# ═══════════════════════════════════════════════════════════════════════
# SECTOR ETF MAP — for relative strength calculation
# ═══════════════════════════════════════════════════════════════════════
SECTOR_ETF_MAP = {
    "XLK": ["AAPL","MSFT","NVDA","AMD","INTC","AVGO","QCOM","CRM","ORCL","AMAT"],
    "XLF": ["JPM","BAC","WFC","GS","MS","BLK","SCHW","AXP","USB","PNC"],
    "XLE": ["XOM","CVX","COP","EOG","SLB","PSX","VLO","MPC","OXY","HAL"],
    "XLV": ["UNH","JNJ","LLY","ABBV","MRK","TMO","ABT","DHR","BMY","AMGN"],
    "XLY": ["AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","CMG","BKNG","TJX"],
    "XLC": ["META","GOOGL","NFLX","DIS","CMCSA","T","VZ","EA","TTWO","WBD"],
    "XLI": ["GE","RTX","BA","HON","CAT","DE","UPS","LMT","NOC","FDX"],
    "XLP": ["WMT","PG","KO","PEP","COST","MDLZ","CL","EL","GIS","CAG"],
    "XLRE":["AMT","PLD","CCI","EQIX","PSA","DLR","O","SBAC","WELL","AVB"],
    "XLB": ["LIN","APD","SHW","ECL","NUE","FCX","ALB","PPG","VMC","MLM"],
    "XLU": ["NEE","DUK","SO","D","AEP","EXC","XEL","SRE","ES","ETR"],
}

TICKER_SECTOR = {}
for etf, tickers in SECTOR_ETF_MAP.items():
    for t in tickers:
        TICKER_SECTOR[t] = etf

# ═══════════════════════════════════════════════════════════════════════
# CRYPTO NARRATIVE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════
CRYPTO_NARRATIVES = {
    "store_of_value": ["BTC-USD"],
    "L1":   ["ETH-USD","SOL-USD","ADA-USD","AVAX-USD","DOT-USD","ATOM-USD","NEAR-USD"],
    "L2":   ["MATIC-USD","ARB-USD","OP-USD","IMX-USD"],
    "DeFi": ["UNI-USD","AAVE-USD","LINK-USD","MKR-USD","CRV-USD","SNX-USD"],
    "AI":   ["FET-USD","RNDR-USD","WLD-USD"],
    "exchange":["BNB-USD","OKB-USD","FTT-USD"],
    "infrastructure":["LINK-USD","FIL-USD","GRT-USD","LPT-USD"],
    "gaming":["AXS-USD","SAND-USD","MANA-USD"],
}

TICKER_NARRATIVE = {}
for narr, tickers in CRYPTO_NARRATIVES.items():
    for t in tickers:
        TICKER_NARRATIVE[t] = narr

# ═══════════════════════════════════════════════════════════════════════
# TOXIC NEWS KEYWORDS
# ═══════════════════════════════════════════════════════════════════════
TOXIC_KEYWORDS = [
    "bankruptcy","scandal","fraud","lawsuit","investigation","delisted",
    "misses earnings","subpoena","criminal","sec probe","sued","default",
    "collapse","chapter 11","ponzi","indicted","class action","halt",
    "going concern","restatement","accounting irregularities",
]
