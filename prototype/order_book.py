import sortedcontainers
import queue
import threading
import time
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
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
    """A simple limit order book with event-driven processing and candlestick plotting."""
    def __init__(self):

        self.bids = sortedcontainers.SortedDict()  # Price -> list of orders
        self.asks = sortedcontainers.SortedDict()  # Price -> list of orders
        self.trades = []  # List of (buyer_id, seller_id, price, quantity)
        self.order_map = {}  # Order ID -> Order
        self.last_trade_price = 100.0  # Initial market price for simulation
        self.event_queue = queue.Queue()  # Event queue
        self.running = True  # Control flag for event loop
        self.trades = pd.DataFrame(columns=['timestamp', 'buyer_id', 'seller_id', 'price', 'quantity'])

    def add_order(self, order: Order) -> List[Tuple[str, str, float, int]]:
        """Add an order, attempt to match it, and return executed trades."""
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
                    'timestamp': time.time(),  # Use event time
                    'buyer_id': order.trader_id,
                    'seller_id': ask_order.trader_id,
                    'price': best_ask_price,
                    'quantity': trade_quantity
                }
                trades.append(trade)
                self.last_trade_price = best_ask_price  # Update market price
                order.quantity -= trade_quantity
                ask_order.quantity -= trade_quantity
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
                order.quantity -= trade_quantity
                bid_order.quantity -= trade_quantity
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
        """Remove an order by ID and side."""
        if order_id not in self.order_map:
            return False # Order does not exist
        order = self.order_map[order_id]
        if order.side != side:
            return False # Side mismatch

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

    def process_events(self):
        """Run continuous event loop to process queue."""
        while self.running:
            try:
                # Check queue with timeout to allow graceful shutdown
                event = self.event_queue.get(timeout=0.1)
                if event["type"] == "add":
                    trades = self.add_order(event["order"])
                    print(f"[{time.time()}] Processed add order {event['order'].order_id}, trades: {trades}")
                elif event["type"] == "cancel":
                    success = self.remove_order(event["order_id"], event["side"])
                    print(f"[{time.time()}] Processed cancel order {event['order_id']}, success: {success}")

                if random.random() < 0.1:  # 10% chance per event
                    self.print_book_state()

            except queue.Empty:
                pass  # No events, continue looping
            time.sleep(0.01)  # Prevent CPU overload

    def print_book_state(self):
        """Print current order book state."""
        book = self.get_order_book()
        best_bid = self.get_best_bid()[0]
        best_ask = self.get_best_ask()[0]
        print(f"[{time.time()}] Order Book State:")
        print(f"  Best Bid: {best_bid if best_bid else 'None'}")
        print(f"  Best Ask: {best_ask if best_ask else 'None'}")
        print(f"  Last Trade Price: {book['last_trade_price']}")
        print(f"  Recent Trades: {book['trades'][-3:]}")  # Last 3 trades
        print(f"  Bid Depth: {len(book['bids'])} price levels, Ask Depth: {len(book['asks'])} price levels")
    
    def plot_ticker(self, save_path=None):
        """Plot a candlestick chart with volume and SMA for trade data."""
        if self.trades.empty:
            print("No trades to plot.")
            return
        # Prepare OHLCV data
        ohlcv = prepare_ohlc_data(self.trades, timeframe='1S')
        if ohlcv.empty:
            print("No valid OHLC data to plot.")
            return
        # Calculate 5-period Simple Moving Average
        ohlcv['SMA_5'] = ohlcv['close'].rolling(window=5).mean()
        
        # Define additional plots (SMA)
        add_plots = [
            mpf.make_addplot(ohlcv['SMA_5'], color='blue', linestyle='-', width=1, label='5-Period SMA')
        ]
        # Define plot style
        style = mpf.make_mpf_style(
            base_mpf_style='charles',
            # base_mpl_style='seaborn',
            marketcolors=mpf.make_marketcolors(
                up='green', down='red',
                edge='black',
                wick='black',
                volume='black'
            ),
            gridstyle='--',
            gridcolor='gray'
        )
        # Plot candlestick chart with volume and SMA
        mpf.plot(
            ohlcv,
            type='candle',
            style=style,
            title='Stock Ticker: Candlestick Chart',
            ylabel='Price',
            volume=True,
            ylabel_lower='Volume',
            addplot=add_plots,
            figscale=1.2,
            savefig=save_path
        )

    def stop(self):
        """Stop the event loop."""
        self.running = False

def prepare_ohlc_data(trades: pd.DataFrame, timeframe: str = '1S') -> pd.DataFrame:
    """Aggregate trade data into OHLC format for candlestick plotting."""
    # Ensure timestamp is datetime and set as index
    trades['timestamp'] = pd.to_datetime(trades['timestamp'], unit='s')
    trades.set_index('timestamp', inplace=True)
    # Resample trades into OHLC and compute volume
    ohlc = trades['price'].resample(timeframe).ohlc()
    volume = trades['quantity'].resample(timeframe).sum()
    # Combine OHLC and volume into a single DataFrame
    ohlcv = pd.concat([ohlc, volume.rename('volume')], axis=1)
    # Drop rows with NaN (no trades in that timeframe)
    ohlcv.dropna(inplace=True)
    return ohlcv

def generate_orders(order_book: OrderBook, num_orders: int, mean_interval: float = 0.5):
    """Simulate order arrivals in a separate thread."""
    order_id = 1
    while order_book.running and order_id <= num_orders:
        # Simulate inter-arrival time (exponential distribution)
        delay = np.random.exponential(mean_interval)
        time.sleep(delay)
        
        # Generate order or cancellation
        if random.random() < 0.1 and order_book.order_map:  # 10% chance to cancel
            order_id_to_cancel = random.choice(list(order_book.order_map.keys()))
            order = order_book.order_map[order_id_to_cancel]
            event = {"type": "cancel", "order_id": order_id_to_cancel, "side": order.side}
        else:
            # Generate new order
            side = random.choice(['buy', 'sell'])
            # Price centered around last trade price
            price = round(order_book.last_trade_price + random.gauss(0, 0.5), 2)
            quantity = random.randint(1, 10)
            timestamp = time.time()
            trader_id = f"trader{random.randint(1, 100)}"
            order = Order(order_id, side, price, quantity, timestamp, trader_id)
            event = {"type": "add", "order": order}
            order_id += 1
        
        order_book.event_queue.put(event)
        # print(f"[{time.time()}] Generated event: {event['type']} for order_id {order_id-1 if event['type'] == 'add' else event['order_id']}")

def main():
    order_book = OrderBook()
    
    # Start order book event loop in a separate thread
    event_thread = threading.Thread(target=order_book.process_events, daemon=True)
    event_thread.start()
    

    # Start order generation in a separate thread
    num_orders = 500
    mean_interval = 0.1
    order_gen_thread = threading.Thread(target=generate_orders, 
                                        args=(order_book, num_orders, mean_interval), 
                                        daemon=True)
    order_gen_thread.start()

    duration_seconds = 60
    try:
        time.sleep(duration_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        order_book.stop()
        event_thread.join(timeout=1.0)
        order_gen_thread.join(timeout=1.0)
        order_book.print_book_state()
        order_book.plot_ticker(save_path='ticker_plot.png')
    

if __name__ == "__main__":
    main()