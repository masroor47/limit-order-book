import asyncio
import sortedcontainers
import time

import sqlite3
from collections import deque

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Order:
    order_id: str
    trader_id: str
    side: str
    price: float
    quantity: int
    timestamp: float

class OrderBook:
    def __init__(self, db_path='trades.db', buffer_size=1000):
        self.bids = sortedcontainers.SortedDict()
        self.asks = sortedcontainers.SortedDict()
        self.order_map = {}
        self.last_trade_price = None
        self.trades = deque(maxlen=buffer_size)
        self.time_history = deque(maxlen=buffer_size)
        self.price_history = deque(maxlen=buffer_size)
        self.volume_history = deque(maxlen=buffer_size)
        self.lock = asyncio.Lock()  # For async safety
        self.event_queue = asyncio.Queue()

        self.pending_trades = []  # Buffer for batching DB inserts
        self.batch_size = 100  # Adjust based on expected volume; e.g., flush every 100 trades
        asyncio.create_task(self._flush_to_db_periodically())

        # initialize database
        self.db_conn = sqlite3.connect(db_path)
        self.db_conn.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                timestamp REAL,
                buyer_id TEXT,
                seller_id TEXT,
                price REAL,
                quantity INTEGER
            )
        ''')
        self.db_conn.commit()

    async def add_order(self, order: Order):
        async with self.lock:
            print(f"LOB: Adding order {order}")
            if not self._validate_order(order):
                raise ValueError("Invalid order: must have valid side, price, and quantity")
            
            self.order_map[order.order_id] = order
            trades = await self._match_order(order)
            print(f"LOB: Trades executed: {trades}")
            # add unmatched quantity to book
            if order.quantity > 0:
                print(f"LOB: Adding remaining order to book {order}")
                self._add_to_book(order)

            if trades:
                await self._record_trades(trades)

            return trades
        
    async def _match_order(self, order: Order) -> List[Dict]:
        trades = []
        opposite_book = self.asks if order.side == 'buy' else self.bids
        get_best_price = self.get_best_ask if order.side == 'buy' else self.get_best_bid
        buyer_id = order.trader_id if order.side == 'buy' else None
        seller_id = order.trader_id if order.side == 'sell' else None

        while order.quantity > 0 and opposite_book:
            best_price, opposite_orders = get_best_price()
            if best_price is None:
                break
            if (order.side == 'buy'  and best_price > order.price) or \
               (order.side == 'sell' and best_price < order.price):
                break # no overlapping price

            opposite_order = opposite_orders[0]
            trade_quantity = min(order.quantity, opposite_order.quantity)
            trade = {
                'timestamp': time.time(),
                'buyer_id': buyer_id or opposite_order.trader_id,
                'seller_id': seller_id or opposite_order.trader_id,
                'price': best_price,
                'quantity': trade_quantity
            }
            trades.append(trade)
            self.last_trade_price = best_price
            order.quantity -= trade_quantity
            opposite_order.quantity -= trade_quantity

            if opposite_order.quantity == 0:
                opposite_orders.pop(0)
                if not opposite_orders:
                    del opposite_book[best_price]
                del self.order_map[opposite_order.order_id]
            if order.quantity == 0:
                del self.order_map[order.order_id]

            # Log trade (optional, can be moved to _record_trades)
            print(f"Matched order {order.side} trade, price={best_price}, qty={trade_quantity}")

        return trades
    
    def _add_to_book(self, order: Order) -> None:
        book = self.bids if order.side == 'buy' else self.asks
        if order.price not in book:
            book[order.price] = []
        book[order.price].append(order)

    async def _record_trades(self, trades: List[Dict]) -> None:
        for trade in trades:
            # Add to short-term buffers
            self.trades.append(trade)
            self.time_history.append(trade['timestamp'])
            self.price_history.append(trade['price'])
            self.volume_history.append(trade['quantity'])
            # Buffer for DB
            self.pending_trades.append(trade)
        
        # Flush immediately if buffer is full (for high-volume bursts)
        if len(self.pending_trades) >= self.batch_size:
            await self._flush_to_db()
        
        # Notify real-time listeners (unchanged)
        if trades:
            await self.event_queue.put({'type': 'new_trades', 'trades': trades})

    def _validate_order(self, order: Order) -> bool:
        if order.side not in ("buy", "sell"):
            return False
        if order.price <= 0 or order.quantity <= 0:
            return False
        if order.order_id in self.order_map:
            return False  # duplicate order
        return True

    async def get_order_book_state(self) -> Dict:
        async with self.lock:
            return {
                'bids': {price: [o.__dict__ for o in orders] for price, orders in self.bids.items()},
                'asks': {price: [o.__dict__ for o in orders] for price, orders in self.asks.items()},
                'last_price': self.last_trade_price,
                'recent_trades': list(self.trades)[-10:]  # Last 10 from buffer
            }
        
    def get_best_bid(self):
        if not self.bids:
            return None, []
        return self.bids.peekitem(-1)

    def get_best_ask(self):
        if not self.asks:
            return None, []
        return self.asks.peekitem(0)

    async def cancel_order(self, order_id: str) -> bool:
        async with self.lock:
            if order_id not in self.order_map:
                return False
            order = self.order_map[order_id]
            book = self.bids if order.side == 'buy' else self.asks
            if order.price in book:
                book[order.price] = [o for o in book[order.price] if o.order_id != order_id]
                if not book[order.price]:
                    del book[order.price]
            del self.order_map[order_id]
            await self.event_queue.put({'type': 'cancel', 'order_id': order_id})
            return True

    def get_last_price(self):
        return self.last_trade_price
    
    async def get_historical_trades(self, from_time: float = None, to_time: float = None) -> List[Dict]:
        async with self.lock:
            query = 'SELECT timestamp, buyer_id, seller_id, price, quantity FROM trades'
            params = []
            conditions = []
            if from_time is not None:
                conditions.append('timestamp >= ?')
                params.append(from_time)
            if to_time is not None:
                conditions.append('timestamp <= ?')
                params.append(to_time)
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            query += ' ORDER BY timestamp ASC'
            
            cursor = self.db_conn.execute(query, params)
            return [
                {'timestamp': row[0], 'buyer_id': row[1], 'seller_id': row[2], 'price': row[3], 'quantity': row[4]}
                for row in cursor.fetchall()
            ]

    async def _flush_to_db(self):
        print("-------- Flushing trades to DB -------")
        async with self.lock:
            print(f"Pending trades to flush: {len(self.pending_trades)}")
            if self.pending_trades:
                # Use executemany for batch insert in a transaction
                query = 'INSERT INTO trades (timestamp, buyer_id, seller_id, price, quantity) VALUES (?, ?, ?, ?, ?)'
                args = [(trade['timestamp'], trade['buyer_id'], trade['seller_id'], trade['price'], trade['quantity']) for trade in self.pending_trades]
                print(query, args)
                self.db_conn.executemany(
                    query,
                    args
                )
                self.db_conn.commit()
                self.pending_trades.clear()

    async def _flush_to_db_periodically(self):
        while True:
            print("Flushing trades to DB...")
            await self._flush_to_db()
            await asyncio.sleep(5)