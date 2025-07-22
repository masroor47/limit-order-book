import websocket
import json
import time
import threading
import random

class SimulatedTrader:
    def __init__(self, 
                 order_ws_url="ws://127.0.0.1:8765", 
                 md_ws_url="ws://127.0.0.1:8766", 
                 initial_price=100.0, 
                 price_sigma=0.5, 
                 qty_min=1, 
                 qty_max=20, 
                 arrival_rate=1.0):
        """
        SimulatedTrader class to automate random order generation for market simulation.

        :param order_ws_url: URL for the order server websocket.
        :param md_ws_url: URL for the market data server websocket.
        :param initial_price: Initial last price to use if no trades have occurred yet.
        :param price_sigma: Standard deviation for Gaussian deviation in price generation.
        :param qty_min: Minimum quantity for orders.
        :param qty_max: Maximum quantity for orders.
        :param arrival_rate: Rate parameter for exponential distribution (orders per second).
        """
        self.last_price = initial_price
        self.lock = threading.Lock()
        self.price_sigma = price_sigma
        self.qty_min = qty_min
        self.qty_max = qty_max
        self.arrival_rate = arrival_rate

        self.stop_event = threading.Event()
        self.send_thread = None

        # Market data websocket
        self.md_ws = websocket.WebSocketApp(
            md_ws_url,
            on_message=self.on_md_message,
            on_error=self.on_ws_error,
            on_close=self.on_ws_close
        )
        self.md_ws.on_open = self.on_md_open

        # Order submission websocket
        self.order_ws = websocket.WebSocketApp(
            order_ws_url,
            on_message=self.on_order_message,
            on_error=self.on_ws_error,
            on_close=self.on_ws_close
        )
        self.order_ws.on_open = self.on_order_open

    def on_md_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get('type') == 'order_book_update':
                last = data['data'].get('last_price')
                if last is not None:
                    with self.lock:
                        self.last_price = last
        except json.JSONDecodeError:
            print("Invalid JSON from market data server.")

    def on_md_open(self, ws):
        # Subscribe to order book updates
        ws.send(json.dumps({"type": "subscribe_order_book"}))
        # Optionally subscribe to trades
        ws.send(json.dumps({"type": "subscribe_trades"}))

    def on_order_open(self, ws):
        # Start the order sending loop in a separate thread if not already running
        if self.send_thread is None or not self.send_thread.is_alive():
            self.send_thread = threading.Thread(target=self.send_orders, daemon=False)
            self.send_thread.start()

    def on_order_message(self, ws, message):
        try:
            response = json.loads(message)
            print(f"Order server responded: {response}")
        except json.JSONDecodeError:
            print("Invalid JSON from order server.")

    def on_ws_error(self, ws, error):
        print(f"Websocket error: {error}")

    def on_ws_close(self, ws, close_status_code, close_msg):
        print("Websocket connection closed.")

    def send_orders(self):
        while not self.stop_event.is_set():
            with self.lock:
                current_last = self.last_price

            side = random.choice(["buy", "sell"])
            # Generate price with Gaussian deviation from last executed price
            price = random.gauss(0, self.price_sigma)
            order_price = max(0.1, round(current_last + price, 1))  # Prevent negative or zero prices
            quantity = random.randint(self.qty_min, self.qty_max)

            order = {
                "side": side,
                "price": order_price,
                "quantity": quantity
            }
            print(f"Simulating order: {order}")

            if not self.order_ws.keep_running:
                print("Order WS not running, stopping send_orders.")
                break

            try:
                self.order_ws.send(json.dumps(order))
            except websocket.WebSocketConnectionClosedException:
                print("Connection closed during send, stopping send_orders.")
                break
            except Exception as e:
                print(f"Error sending order: {e}")
                break

            delay = random.expovariate(self.arrival_rate)
            self.stop_event.wait(delay)

    def run_md_ws(self):
        while not self.stop_event.is_set():
            print("Connecting to MD server...")
            self.md_ws.run_forever(ping_interval=30, ping_timeout=20)
            if self.stop_event.is_set():
                break
            print("MD connection closed, reconnecting in 5 seconds...")
            time.sleep(5)

    def run_order_ws(self):
        while not self.stop_event.is_set():
            print("Connecting to order server...")
            self.order_ws.run_forever(ping_interval=30, ping_timeout=20)
            if self.stop_event.is_set():
                break
            print("Order connection closed, reconnecting in 5 seconds...")
            time.sleep(5)

    def run(self):
        # Run both websockets in separate threads with reconnect logic
        self.md_thread = threading.Thread(target=self.run_md_ws, daemon=False)
        self.order_thread = threading.Thread(target=self.run_order_ws, daemon=False)

        self.md_thread.start()
        self.order_thread.start()

        try:
            # Wait for threads to finish
            self.md_thread.join()
            self.order_thread.join()
        except KeyboardInterrupt:
            print("Shutting down connections...")
            self.stop_event.set()
            self.md_ws.close()
            self.order_ws.close()
            if self.send_thread:
                self.send_thread.join()
            self.md_thread.join()
            self.order_thread.join()

if __name__ == "__main__":
    trader = SimulatedTrader(
        price_sigma=0.7,  # Adjust sigma for volatility
        qty_min=1,
        qty_max=10,
        arrival_rate=5  # Average 5 orders per second; adjust for desired activity level
    )
    print("Starting simulated trader...")
    trader.run()
    print("Simulated trader stopped.")