import sortedcontainers
import queue
import threading
import time
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from typing import List, Tuple, Dict

class Order:
    def __init__(self, order_id: int, side: str, price: float, quantity: int, timestamp: float, trader_id: str):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.quantity = quantity
        self.timestamp = timestamp
        self.trader_id = trader_id
    
    def __repr__(self):
        return f"Order(order_id={self.order_id}, side={self.side}, price={self.price}, quantity={self.quantity}, timestamp={self.timestamp}, trader_id={self.trader_id})"

class OrderBook:
    def __init__(self):
        self.bids = sortedcontainers.SortedDict()
        self.asks = sortedcontainers.SortedDict()
        self.trades = pd.DataFrame(columns=['timestamp', 'buyer_id', 'seller_id', 'price', 'quantity'])
        self.order_map = {}
        self.last_trade_price = 100.0
        self.event_queue = queue.Queue()
        self.running = True
        # Lists for price, volume, and time history
        self.price_history = [self.last_trade_price]
        self.volume_history = [0]
        self.time_history = [time.time()]

    def add_order(self, order: Order) -> List[Dict]:
        self.order_map[order.order_id] = order
        trades = []

        if order.side == 'buy':
            while order.quantity > 0 and self.asks:
                best_ask_price, ask_orders = self.get_best_ask()
                if best_ask_price is None or best_ask_price > order.price:
                    break
                ask_order = ask_orders[0]
                trade_quantity = min(order.quantity, ask_order.quantity)
                trade = {
                    'timestamp': time.time(),
                    'buyer_id': order.trader_id,
                    'seller_id': ask_order.trader_id,
                    'price': best_ask_price,
                    'quantity': trade_quantity
                }
                trades.append(trade)
                self.last_trade_price = best_ask_price
                self.price_history.append(self.last_trade_price)
                self.volume_history.append(trade_quantity)
                self.time_history.append(trade['timestamp'])
                order.quantity -= trade_quantity
                ask_order.quantity -= trade_quantity
                print(f"buy trade, price={best_ask_price}, qty={trade_quantity}")
                if ask_order.quantity == 0:
                    ask_orders.pop(0)
                    if not ask_orders:
                        del self.asks[best_ask_price]
                    del self.order_map[ask_order.order_id]
                if order.quantity == 0:
                    del self.order_map[order.order_id]

        elif order.side == 'sell':
            while order.quantity > 0 and self.bids:
                best_bid_price, bid_orders = self.get_best_bid()
                if best_bid_price is None or best_bid_price < order.price:
                    break
                bid_order = bid_orders[0]
                trade_quantity = min(order.quantity, bid_order.quantity)
                trade = {
                    'timestamp': time.time(),
                    'buyer_id': bid_order.trader_id,
                    'seller_id': order.trader_id,
                    'price': best_bid_price,
                    'quantity': trade_quantity
                }
                trades.append(trade)
                self.last_trade_price = best_bid_price
                self.price_history.append(self.last_trade_price)
                self.volume_history.append(trade_quantity)
                self.time_history.append(trade['timestamp'])
                order.quantity -= trade_quantity
                bid_order.quantity -= trade_quantity
                print(f"sell trade, price={best_bid_price}, qty={trade_quantity}")
                if bid_order.quantity == 0:
                    bid_orders.pop(0)
                    if not bid_orders:
                        del self.bids[best_bid_price]
                    del self.order_map[bid_order.order_id]
                if order.quantity == 0:
                    del self.order_map[order.order_id]
        else:
            raise ValueError("Order side must be 'buy' or 'sell'")

        if order.quantity > 0:
            if order.side == 'buy':
                if order.price not in self.bids:
                    self.bids[order.price] = []
                self.bids[order.price].append(order)
            elif order.side == 'sell':
                if order.price not in self.asks:
                    self.asks[order.price] = []
                self.asks[order.price].append(order)

        self.trades = pd.concat([self.trades, pd.DataFrame(trades)], ignore_index=True)
        return trades

    def remove_order(self, order_id: int, side: str) -> bool:
        if order_id not in self.order_map:
            return False
        order = self.order_map[order_id]
        if order.side != side:
            return False

        if side == 'buy' and order.price in self.bids:
            orders = self.bids[order.price]
            self.bids[order.price] = [o for o in orders if o.order_id != order_id]
            if not self.bids[order.price]:
                del self.bids[order.price]
        elif side == 'sell' and order.price in self.asks:
            orders = self.asks[order.price]
            self.asks[order.price] = [o for o in orders if o.order_id != order_id]
            if not self.asks[order.price]:
                del self.asks[order.price]

        del self.order_map[order_id]
        return True

    def get_best_bid(self) -> Tuple[float, List[Order]]:
        if self.bids:
            return self.bids.peekitem(-1)
        return None, []

    def get_best_ask(self) -> Tuple[float, List[Order]]:
        if self.asks:
            return self.asks.peekitem(0)
        return None, []

    def get_order_book(self) -> Dict:
        return {
            'bids': {price: orders for price, orders in self.bids.items()},
            'asks': {price: orders for price, orders in self.asks.items()},
            'trades': self.trades,
            'last_trade_price': self.last_trade_price
        }

    def update_price_volume_plot(self, frame):
            """Update the price and volume plots."""
            self.line_price.set_data(self.time_history, self.price_history)
            self.line_volume.set_data(self.time_history, self.volume_history)
            if self.time_history:
                current_time = self.time_history[-1]
                self.ax_price.set_xlim(current_time - 60, current_time)
                if self.price_history:
                    min_price = min(self.price_history[-100:])
                    max_price = max(self.price_history[-100:])
                    padding = (max_price - min_price) * 0.1 or 1.0
                    self.ax_price.set_ylim(min_price - padding, max_price + padding)
                if self.volume_history:
                    max_volume = max(self.volume_history[-100:] + [10])  # Ensure minimum range
                    self.ax_volume.set_ylim(0, max_volume * 1.1)
            return self.line_price, self.line_volume

    def update_bid_ask_plot(self, frame):
        """Update the bid-ask order book plot."""
        # Clear previous bars
        if self.bid_bars is not None:
            for bar in self.bid_bars:
                bar.remove()
        if self.ask_bars is not None:
            for bar in self.ask_bars:
                bar.remove()
        
        # Get current bids and asks
        bids = self.bids
        asks = self.asks
        all_prices = sorted(set(bids.keys()) | set(asks.keys()))
        if not all_prices:
            all_prices = [self.last_trade_price]
        min_price = min(all_prices) - 1
        max_price = max(all_prices) + 1
        self.price_range = (min_price, max_price)
        self.ax_ba.set_xlim(self.price_range)
        
        # Calculate total quantities at each price
        bid_quantities = {price: sum(order.quantity for order in orders) for price, orders in bids.items()}
        ask_quantities = {price: sum(order.quantity for order in orders) for price, orders in asks.items()}
        
        # Prepare data for bar plots
        bid_prices = list(bid_quantities.keys())
        bid_volumes = [-qty for qty in bid_quantities.values()]  # Negative for bids
        ask_prices = list(ask_quantities.keys())
        ask_volumes = list(ask_quantities.values())  # Positive for asks
        
        # Plot bars
        self.bid_bars = self.ax_ba.bar(bid_prices, bid_volumes, width=0.1, color='green', align='center', label='Bids')
        self.ask_bars = self.ax_ba.bar(ask_prices, ask_volumes, width=0.1, color='red', align='center', label='Asks')
        
        # Adjust y-axis
        max_qty = max([max(bid_quantities.values(), default=0), max(ask_quantities.values(), default=0), 10])
        self.ax_ba.set_ylim(-max_qty * 1.1, max_qty * 1.1)
        # if 'Bids' not in [l.get_label() for l in self.ax_ba.get_legend_handles_labels()[1]]:
        #     self.ax_ba.legend()
        
        return self.bid_bars + self.ask_bars

    def process_events(self):
        """Run continuous event loop to process queue."""
        while self.running:
            try:
                event = self.event_queue.get(timeout=0.1)
                if event["type"] == "add":
                    trades = self.add_order(event["order"])
                    # print(f"[{time.time()}] Processed add order {event['order'].order_id}, trades: {trades}")
                elif event["type"] == "cancel":
                    success = self.remove_order(event["order_id"], event["side"])
                    # print(f"[{time.time()}] Processed cancel order {event['order_id']}, success: {success}")

                if random.random() < 0.1:
                    self.print_book_state()

            except queue.Empty:
                pass
            time.sleep(0.01)

    def print_book_state(self):
        book = self.get_order_book()
        best_bid = self.get_best_bid()[0]
        best_ask = self.get_best_ask()[0]
        # print("" + "="*40)
        # print(f"[{time.time()}] Order Book State:")
        # print(f"  Best Bid: {best_bid if best_bid else 'None'}")
        # print(f"  Best Ask: {best_ask if best_ask else 'None'}")
        # print(f"  Last Trade Price: {book['last_trade_price']}")
        # print(f"  Recent Trades: {book['trades'][-3:]}")
        # print(f"  Bid Depth: {len(book['bids'])} price levels, Ask Depth: {len(book['asks'])} price levels")

    def start_plotting(self):
        # Price and volume figure
        self.fig, (self.ax_price, self.ax_volume) = plt.subplots(2, 1, figsize=(10, 8), 
                                                                sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        self.line_price, = self.ax_price.plot([], [], 'b-', label='Last Trade Price')
        self.line_volume, = self.ax_volume.plot([], [], 'k-', label='Trade Volume')
        self.ax_price.set_ylabel('Price')
        self.ax_price.set_title('Real-Time Last Trade Price and Volume')
        self.ax_price.legend()
        self.ax_price.grid(True)
        self.ax_volume.set_xlabel('Time (s)')
        self.ax_volume.set_ylabel('Volume')
        self.ax_volume.legend()
        self.ax_volume.grid(True)
        self.ax_price.set_xlim(self.time_history[0], self.time_history[0] + 60)
        # self.ax_price.set_ylim(self.last_trade_price - 5, self.last_trade_price + 5)
        # self.ax_volume.set_ylim(0, 10)  # Initial volume range, will adjust dynamically
        # Bid-ask figure
        self.fig_ba, self.ax_ba = plt.subplots(figsize=(10, 6))
        self.ax_ba.set_xlabel('Price')
        self.ax_ba.set_ylabel('Quantity')
        self.ax_ba.set_title('Bid-Ask Order Book')
        self.ax_ba.grid(True)
        self.bid_bars = None
        self.ask_bars = None
        self.price_range = (95, 105)  # Initial price range for bid-ask plot
        self.ax_ba.set_xlim(self.price_range)
        self.ax_ba.set_ylim(-50, 50)  # Negative for bids, positive for asks
        self.ax_ba.axhline(0, color='black', linewidth=0.5)
        """Start the real-time price, volume, and bid-ask animations."""
        ani_pv = FuncAnimation(self.fig, self.update_price_volume_plot, interval=100, blit=False)  # Changed to blit=False
        ani_ba = FuncAnimation(self.fig_ba, self.update_bid_ask_plot, interval=100, blit=False)
        plt.show()

    def stop(self):
        self.running = False
        plt.close(self.fig)
        plt.close(self.fig_ba)

def generate_orders(order_book: OrderBook, num_orders: int, mean_interval: float = 0.5):
    order_id = 1
    while order_book.running and order_id <= num_orders:
        delay = np.random.exponential(mean_interval)
        time.sleep(delay)
        
        if random.random() < 0.1 and order_book.order_map:
            order_id_to_cancel = random.choice(list(order_book.order_map.keys()))
            order = order_book.order_map[order_id_to_cancel]
            event = {"type": "cancel", "order_id": order_id_to_cancel, "side": order.side}
        else:
            side = random.choice(['buy', 'sell'])
            price = round(order_book.last_trade_price + random.gauss(0, 0.5), 1)
            quantity = random.randint(1, 10)
            timestamp = time.time()
            trader_id = f"trader{random.randint(1, 100)}"
            order = Order(order_id, side, price, quantity, timestamp, trader_id)
            event = {"type": "add", "order": order}
            order_id += 1
        
        order_book.event_queue.put(event)

def main():
    random.seed(42)
    order_book = OrderBook()
    
    # Start order book event loop
    event_thread = threading.Thread(target=order_book.process_events, daemon=True)
    event_thread.start()
    
    # Start order generation
    num_orders = 500
    mean_interval = 0.1
    order_gen_thread = threading.Thread(target=generate_orders, 
                                      args=(order_book, num_orders, mean_interval), 
                                      daemon=True)
    order_gen_thread.start()
    
    # Start real-time plotting
    order_book.start_plotting()
    
    # Wait for threads to finish
    event_thread.join(timeout=1.0)
    order_gen_thread.join(timeout=1.0)
    order_book.stop()

if __name__ == "__main__":
    main()