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
    print("Connection opened")

    def send_trades():
        trades = [
            {"side": "buy", "price": 100.0, "quantity": 10},
            {"side": "buy", "price": 101.0, "quantity": 10},
            {"side": "buy", "price": 102.0, "quantity": 10},
        ]
        for trade in trades:
            ws.send(json.dumps(trade))
            time.sleep(1)
        ws.close()  # Close after sending all trades
    threading.Thread(target=send_trades).start()


ws = websocket.WebSocketApp("ws://127.0.0.1:8765",
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)
ws.on_open = on_open
ws.run_forever()