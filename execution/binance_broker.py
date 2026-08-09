"""
execution/binance_broker.py
Handles direct API execution of trades on Binance Futures.
"""
import os
import hmac
import hashlib
import time
import requests

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_SECRET = os.environ.get("BINANCE_SECRET", "")
BASE_URL = "https://fapi.binance.com" # Use testnet for dry runs: https://testnet.binancefuture.com

def _sign_request(query_string: str) -> str:
    return hmac.new(
        BINANCE_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def execute_trade(signal: dict) -> bool:
    """
    Executes a trade based on the generated signal.
    signal dictionary requires: ticker, direction, pos_size, stop, target
    """
    if not BINANCE_API_KEY or not BINANCE_SECRET:
        print("Binance Execution Error: API Keys not configured.")
        return False
        
    try:
        # Format symbol for Binance (BTC-USD -> BTCUSDT)
        symbol = signal['ticker'].replace('-', '') + "T"
        side = "BUY" if signal['direction'] == "LONG" else "SELL"
        qty = round(signal.get('pos_size', 0), 3) # Note: Actual precision depends on the specific coin
        
        if qty <= 0:
            print("Binance Execution Error: Position size is 0.")
            return False
            
        print(f"Executing {side} for {qty} of {symbol}...")
        
        headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
        
        # 1. Place Market Entry Order
        timestamp = int(time.time() * 1000)
        query = f"symbol={symbol}&side={side}&type=MARKET&quantity={qty}&timestamp={timestamp}"
        signature = _sign_request(query)
        
        url = f"{BASE_URL}/fapi/v1/order?{query}&signature={signature}"
        r = requests.post(url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            print(f"Execution Failed: {r.json()}")
            return False
            
        print(f"✅ Market Order Filled: {r.json()}")
        
        # 2. Place Stop Loss Order
        sl_side = "SELL" if side == "BUY" else "BUY"
        sl_price = round(signal['stop'], 2)
        
        ts = int(time.time() * 1000)
        sl_query = f"symbol={symbol}&side={sl_side}&type=STOP_MARKET&stopPrice={sl_price}&closePosition=true&timestamp={ts}"
        sl_sig = _sign_request(sl_query)
        
        sl_url = f"{BASE_URL}/fapi/v1/order?{sl_query}&signature={sl_sig}"
        r_sl = requests.post(sl_url, headers=headers, timeout=10)
        print(f"🛡️ Stop Loss Placed at {sl_price}")
        
        # 3. Place Take Profit Order
        tp_price = round(signal['target'], 2)
        ts2 = int(time.time() * 1000)
        tp_query = f"symbol={symbol}&side={sl_side}&type=TAKE_PROFIT_MARKET&stopPrice={tp_price}&closePosition=true&timestamp={ts2}"
        tp_sig = _sign_request(tp_query)
        
        tp_url = f"{BASE_URL}/fapi/v1/order?{tp_query}&signature={tp_sig}"
        r_tp = requests.post(tp_url, headers=headers, timeout=10)
        print(f"🎯 Take Profit Placed at {tp_price}")
        
        return True
    except Exception as e:
        print(f"Binance Execution Exception: {e}")
        return False
