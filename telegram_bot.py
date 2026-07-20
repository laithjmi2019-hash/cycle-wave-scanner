import os
import sys
import requests
import datetime
import yfinance as yf

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

def run_scan():
    print(f"Starting V7.0 Global Sniper Scan at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    signals_found = []
    
    for ticker in TICKERS:
        try:
            t = yf.Ticker(ticker)
            d1d = t.history(period="6mo", interval="1d", prepost=False)
            d1h = t.history(period="60d", interval="1h", prepost=False)
            
            if d1d.empty or d1h.empty:
                continue
                
            res = analyze_asset(ticker, d1d, d1h, None) # df_15m is None for now as it's not used in V7
            
            if res and res["recommendation"] in ["LONG SNIPER", "SHORT SNIPER", "LONG MOMENTUM", "SHORT MOMENTUM"]:
                price = d1h['Close'].iloc[-1]
                
                # Use different emoji for momentum
                emoji = "🚀" if "MOMENTUM" in res["recommendation"] else "🚨"
                
                msg = f"{emoji} <b>{res['recommendation']}</b> {emoji}\n\n"
                msg += f"<b>Asset:</b> {ticker}\n"
                msg += f"<b>Price:</b> ${price:.2f}\n"
                msg += f"<b>RSI-14:</b> {res['rsi']}\n"
                msg += f"<b>Target:</b> {res['upside']}\n"
                msg += f"<b>Stop Loss:</b> {res['stop_loss']}\n"
                msg += f"<b>Risk/Reward:</b> {res['rr']}\n\n"
                msg += f"<i>{res['reason']}</i>"
                
                signals_found.append(msg)
                print(f"Signal found for {ticker}")
                
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            
    if signals_found:
        for msg in signals_found:
            send_telegram_message(msg)
    else:
        print("No sniper signals found this hour.")
        send_telegram_message("✅ <b>Scan Complete</b>\n\nNo Sniper or Momentum signals found in the last 30 minutes. Continuing to monitor 245 assets...")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_telegram_message("✅ <b>Cycle & Wave Scanner V7.0 (Global Edition)</b>\n\nYour automated background scanner has successfully connected to Telegram and is now tracking 245 global assets (US, EU, China, UAE, Crypto).")
    else:
        run_scan()
