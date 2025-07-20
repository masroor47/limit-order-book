import websocket
import json
import time
import threading

def on_message(ws, message):
    try:
        response = json.loads(message)
        print(f"Server responded: {response}")
    except json.JSONDecodeError:
        print("Received invalid JSON response")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")

def on_open(ws):
    print("Connected to server")
    def send_trades():
        trades = [
            {"trade_id": "12345", "symbol": "AAPL", "quantity": 100, "price": 150.25, "side": "buy"},
            {"trade_id": "12346", "symbol": "GOOG", "quantity": 50, "price": 2800.50, "side": "sell"}
        ]
        for i in range(50):
            for trade in trades:
                ws.send(json.dumps(trade))
                time.sleep(0.0001)
        ws.close()
    threading.Thread(target=send_trades).start()

ws = websocket.WebSocketApp("ws://127.0.0.1:8765",
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)
ws.on_open = on_open
ws.run_forever()