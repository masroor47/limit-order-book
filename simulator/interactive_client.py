import websocket
import json
import threading
import signal
import sys

def on_message(ws, message):
    try:
        response = json.loads(message)
        print(f"Server responded: {response}")
    except json.JSONDecodeError:
        print("Received invalid JSON response")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"Connection closed: {close_status_code}, {close_msg}")

def on_open(ws):
    print("Connection opened")

    def interactive_console():
        print("Enter order details (e.g., 'b' for buy, 's' for sell, 'q' to quit):")
        while ws.keep_running:  # Check if WebSocket is still active
            try:
                # Get order side
                side_input = input("Side (b/s) or 'q' to quit: ").strip().lower()
                if side_input == 'q':
                    ws.close()
                    break
                if side_input not in ('b', 's'):
                    print("Invalid side. Please enter 'b' for buy or 's' for sell.")
                    continue

                # Map input to full side name
                side = 'buy' if side_input == 'b' else 'sell'

                order_type = input("Order type (l/m) [default: limit]: ").strip().lower()
                if order_type not in ('l', 'm', ''):
                    print("Invalid order type. Please enter 'l' for limit or 'm' for market.")
                    continue
                order_type = 'limit' if order_type in ('l', '') else 'market'

                # Get price if limit order
                if order_type == 'limit':
                    try:
                        price = float(input("Limit price: ").strip())
                        if price <= 0:
                            print("Price must be positive.")
                            continue
                    except ValueError:
                        print("Invalid price. Please enter a valid number.")
                        continue

                # Get quantity
                try:
                    quantity = int(input("Quantity: ").strip())
                    if quantity <= 0:
                        print("Quantity must be positive.")
                        continue
                except ValueError:
                    print("Invalid quantity. Please enter a valid integer.")
                    continue

                # Create and send order
                order = {
                    "side": side,
                    "price": price,
                    "order_type": order_type,
                    "quantity": quantity
                }
                ws.send(json.dumps(order))
                print(f"Sent order: {order}")

            except EOFError:
                print("\nEOF received. Closing connection...")
                ws.close()
                break
            except Exception as e:
                print(f"Error in console input: {e}")

    # Start the interactive console in a separate thread
    threading.Thread(target=interactive_console, daemon=True).start()

# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print("\nCtrl+C received. Closing WebSocket connection...")
    ws.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Create WebSocket connection
ws = websocket.WebSocketApp(
    "ws://127.0.0.1:8765",
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)
ws.on_open = on_open
ws.run_forever()