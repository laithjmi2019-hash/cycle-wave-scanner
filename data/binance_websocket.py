import websocket
import json
import threading
import time
from collections import defaultdict

# Store the last 5 minutes of liquidations per symbol
liquidation_cache = defaultdict(list)

def on_message(ws, message):
    data = json.loads(message)
    # The payload structure for forceOrder is inside data['o']
    if 'o' in data:
        order = data['o']
        symbol = order['s']
        side = order['S'] # SELL means Long Liquidation, BUY means Short Liquidation
        price = float(order['p'])
        qty = float(order['q'])
        usd_value = price * qty
        
        timestamp = time.time()
        
        liquidation_cache[symbol].append({
            'time': timestamp,
            'side': side,
            'usd_value': usd_value,
            'price': price
        })
        
        # Cleanup old entries (older than 300 seconds)
        liquidation_cache[symbol] = [x for x in liquidation_cache[symbol] if timestamp - x['time'] < 300]
        
        if usd_value > 500000: # Highlight liquidations > $500k
            print(f"🚨 LIQUIDATION: {symbol} | {side} | ${usd_value:,.2f} at {price}")

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket Closed. Reconnecting...")
    time.sleep(5)
    start_websocket()

def on_open(ws):
    print("Connected to Binance Liquidation Stream (!forceOrder@arr)")

def start_websocket():
    ws_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()

def get_recent_liquidations(symbol, seconds=300):
    """Returns total USD value of Longs and Shorts liquidated recently"""
    current_time = time.time()
    recent = [x for x in liquidation_cache[symbol] if current_time - x['time'] < seconds]
    long_liq = sum(x['usd_value'] for x in recent if x['side'] == 'SELL')
    short_liq = sum(x['usd_value'] for x in recent if x['side'] == 'BUY')
    return long_liq, short_liq

def run_in_background():
    t = threading.Thread(target=start_websocket, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    start_websocket()
