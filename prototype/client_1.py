import websocket
import time
import threading

def on_message(ws, message):
    print(f"Server responded: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")

def on_open(ws):
    print("Connected to server")
    # Send messages in a loop
    def send_messages():
        for i in range(100):
            message = f"Message {i+1}"
            ws.send(message)
            time.sleep(0.001)
        ws.close()  # Close after sending
    threading.Thread(target=send_messages).start()

ws = websocket.WebSocketApp("ws://127.0.0.1:8765",
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)
ws.on_open = on_open
ws.run_forever()