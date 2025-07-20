import asyncio
import sortedcontainers

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
    def __init__(self):
        self.bids = sortedcontainers.SortedDict()
        self.asks = sortedcontainers.SortedDict()
        self.order_map = {}
        self.last_trade_price = None
        self.trades = []
        self.time_history = []
        self.price_history = []
        self.volume_history = []
        self.lock = asyncio.Lock()  # For async safety

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
                'timestamp': asyncio.get_event_loop().time(),
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
        self.trades.extend(trades)
        for trade in trades:
            self.price_history.append(trade['price'])
            self.volume_history.append(trade['quantity'])
            self.time_history.append(trade['timestamp'])

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
                'recent_trades': self.trades[-10:]  # Last 10 trades
            }
        
    def get_best_bid(self):
        if not self.bids:
            return None, []
        return self.bids.peekitem(-1)

    def get_best_ask(self):
        if not self.asks:
            return None, []
        return self.asks.peekitem(0)

    def cancel_order(self, order_id):
        pass

    def get_last_price(self):
        pass
