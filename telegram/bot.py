"""
telegram/bot.py — Single Telegram bot for both Stocks and Crypto.
Prefixes every message clearly: 📈 [STOCKS] or 🪙 [CRYPTO]
Only A and A+ signals sent by default. B+ logged but not sent.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import config

EMOJI = {
    "A+": "🔥",
    "A":  "🟢",
    "B+": "🟡",
    "B":  "⚪",
}

ASSET_PREFIX = {
    "STOCKS": "📈 [STOCKS]",
    "CRYPTO": "🪙 [CRYPTO]",
}

def _post(text: str):
    """Send raw text to Telegram."""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("  [Telegram] Missing credentials - message not sent.")
        return False
    url     = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"  [Telegram] Error: {e}")
        return False

def build_stock_message(signal: dict) -> str:
    """Format a stock signal for Telegram."""
    qc     = signal.get("quality_class", "B")
    emoji  = EMOJI.get(qc, "⚪")
    prefix = ASSET_PREFIX["STOCKS"]
    strat  = signal.get("strategy", "").replace("_", " ").title()
    direction = signal.get("direction", "LONG")
    ticker = signal.get("ticker", "")
    score  = signal.get("total_score", 0)

    # Market regime info
    regime_info = signal.get("regime_class", "")
    sector      = signal.get("sector", "")

    lines = [
        f"{emoji} {prefix} {qc} | {direction} — {strat}",
        f"",
        f"<b>Asset:</b> {ticker}",
        f"<b>Confirmation Grade:</b> {qc}",
        f"<b>Confidence Score:</b> {score}/100 ({score}%)",
        f"<b>Market:</b> {signal.get('market', '')}  <b>Sector:</b> {sector}",
        f"",
        f"<b>Entry:</b>  ${signal.get('entry', 0):.4f}",
        f"<b>Stop:</b>   ${signal.get('stop', 0):.4f}",
        f"<b>Target:</b> ${signal.get('target', 0):.4f}",
        f"<b>R:R:</b>    {signal.get('rr', 'N/A')}",
        f"",
        f"<b>Regime:</b> {regime_info}",
        f"<b>RSI:</b> {signal.get('rsi','N/A')}  <b>ADX:</b> {signal.get('adx','N/A')}  <b>RVOL:</b> {signal.get('rvol','N/A')}x",
        f"<b>Structure:</b> {signal.get('structure','N/A')}  <b>RS vs SPY:</b> {signal.get('rs_vs_spy','N/A')}",
        f"",
    ]

    # Top reasons
    reasons = signal.get("reason_top3", [])
    if reasons:
        lines.append("<b>Top reasons:</b>")
        for i, r in enumerate(reasons[:4], 1):
            lines.append(f"  {i}. {r}")

    # Score breakdown
    breakdown = signal.get("breakdown", {})
    if breakdown:
        lines.append("")
        lines.append("<b>Score breakdown:</b>")
        for group, data in breakdown.items():
            s = data.get("score", 0)
            m = data.get("max", 0)
            bar = "█" * int(s / m * 10) if m > 0 else ""
            lines.append(f"  {group.replace('_',' ').title():<22} {s:>4.0f}/{m:<3}  {bar}")

    return "\n".join(lines)

def build_crypto_message(signal: dict) -> str:
    """Format a crypto signal for Telegram."""
    qc     = signal.get("quality_class", "B")
    emoji  = EMOJI.get(qc, "⚪")
    prefix = ASSET_PREFIX["CRYPTO"]
    strat  = signal.get("strategy", "").replace("_", " ").title()
    direction = signal.get("direction", "LONG")
    ticker = signal.get("ticker", "")
    score  = signal.get("total_score", 0)

    lines = [
        f"{emoji} {prefix} {qc} | {direction} — {strat}",
        f"",
        f"<b>Asset:</b> {ticker}",
        f"<b>Confirmation Grade:</b> {qc}",
        f"<b>Confidence Score:</b> {score}/100 ({score}%)",
        f"<b>Narrative:</b> {signal.get('narrative', 'N/A')}",
        f"",
        f"<b>Entry:</b>  ${signal.get('entry', 0):.4f}",
        f"<b>Stop:</b>   ${signal.get('stop', 0):.4f}",
        f"<b>Target:</b> ${signal.get('target', 0):.4f}",
        f"<b>R:R:</b>    {signal.get('rr', 'N/A')}",
        f"",
        f"<b>BTC Regime:</b> {signal.get('btc_regime', 'N/A')}",
        f"<b>RS vs BTC:</b>  {signal.get('rs_vs_btc', 'N/A')}",
        f"",
        f"<b>OI:</b>      {signal.get('oi_summary', 'N/A')}",
        f"<b>Funding:</b> {signal.get('funding_summary', 'N/A')}",
        f"<b>CVD:</b>     {signal.get('cvd_summary', 'N/A')}",
        f"",
    ]

    reasons = signal.get("reason_top3", [])
    if reasons:
        lines.append("<b>Top reasons:</b>")
        for i, r in enumerate(reasons[:4], 1):
            lines.append(f"  {i}. {r}")

    # Warnings
    warnings = signal.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("<b>⚠️ Warnings:</b>")
        for w in warnings:
            lines.append(f"  • {w}")

    breakdown = signal.get("breakdown", {})
    if breakdown:
        lines.append("")
        lines.append("<b>Score breakdown:</b>")
        for group, data in breakdown.items():
            s = data.get("score", 0)
            m = data.get("max", 0)
            bar = "█" * int(s / m * 10) if m > 0 else ""
            lines.append(f"  {group.replace('_',' ').title():<24} {s:>4.0f}/{m:<3}  {bar}")

    return "\n".join(lines)

def build_result_message(signal: dict) -> str:
    """Format a trade outcome (Target Hit / Stopped Out / Expired)."""
    outcome  = signal.get("outcome", "UNKNOWN")
    asset_class = signal.get("asset_class", "STOCKS")
    prefix   = ASSET_PREFIX.get(asset_class, "📈 [STOCKS]")
    pnl      = signal.get("pnl_pct", 0)
    sign     = "+" if pnl >= 0 else ""
    outcome_emoji = "✅" if outcome == "TARGET HIT" else ("❌" if outcome == "STOPPED OUT" else "⏱")

    return (
        f"{outcome_emoji} {prefix} TRADE RESULT: <b>{outcome}</b>\n\n"
        f"<b>Asset:</b>     {signal.get('ticker', '')}\n"
        f"<b>Strategy:</b>  {signal.get('rec', '')}\n"
        f"<b>Entry:</b>     ${signal.get('entry', 0):.4f}\n"
        f"<b>Exit:</b>      ${signal.get('exit_price', 0):.4f}\n"
        f"<b>P&amp;L:</b>       {sign}{pnl:.2f}%\n"
        f"<b>Duration:</b>  {signal.get('age_hours', 0):.1f} hours\n"
        f"<b>Stop was:</b>  ${signal.get('stop', 0):.4f} | "
        f"<b>Target was:</b> ${signal.get('target', 0):.4f}"
    )

def send_signal(signal: dict) -> bool:
    """
    Route and send a signal to Telegram.
    Returns True if sent, False if suppressed (score too low) or error.
    """
    score        = signal.get("total_score", 0)
    quality_class = signal.get("quality_class", "C")
    asset_class   = signal.get("asset_class", "STOCKS")

    # Check if it meets alert threshold - send B grade and above (user manages risk)
    if quality_class == "C":
        return False  # Only C grade is suppressed

    msg = (build_crypto_message(signal)
           if asset_class == "CRYPTO"
           else build_stock_message(signal))
    return _post(msg)

def send_result(signal: dict) -> bool:
    """Send a trade outcome message."""
    return _post(build_result_message(signal))

def send_raw(text: str) -> bool:
    """Send any raw text (for system messages)."""
    return _post(text)
