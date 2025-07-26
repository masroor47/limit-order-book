import asyncio
import websockets
import json
import time
import uuid

from OrderBook import Order

class OrderServer:
    def __init__(self, order_book, host="127.0.0.1", port=8765):
        self.order_book = order_book
        self.host = host
        self.port = port
        self.trader_ids = {}  # Maps websocket to trader_id
        self.websocket_traders = {}  # Maps trader_id to websocket

    async def handle_order(self, websocket):
        print(f"New connection from {websocket.remote_address}")
        print(self.trader_ids)
        if websocket not in self.trader_ids:
            self.trader_ids[websocket] = str(uuid.uuid4())
            self.websocket_traders[self.trader_ids[websocket]] = websocket
        trader_id = self.trader_ids[websocket]
        try:
            async for message in websocket:
                order_dict = json.loads(message)
                order_id = str(uuid.uuid4())
                order = Order(
                    order_id=order_id,
                    trader_id=trader_id,
                    side=order_dict["side"],
                    order_type=order_dict.get("order_type", "limit"),
                    price=float(order_dict["price"]),
                    quantity=int(order_dict["quantity"]),
                    timestamp=time.time()
                )
                trades = await self.order_book.add_order(order)
                await websocket.send(json.dumps(trades))

                for trade in trades:
                    buyer_ws = self.websocket_traders.get(trade['buyer_id'])
                    seller_ws = self.websocket_traders.get(trade['seller_id'])
                    if buyer_ws and buyer_ws != websocket:
                        await buyer_ws.send(json.dumps([trade]))
                    if seller_ws and seller_ws != websocket:
                        await seller_ws.send(json.dumps([trade]))
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed for trader {trader_id}")
        finally:
            # Clean up both mappings
            if websocket in self.trader_ids:
                print(f"Cleaning up trader {trader_id}")
                del self.trader_ids[websocket]
            if trader_id in self.websocket_traders:
                del self.websocket_traders[trader_id]

    async def start(self):
        async with websockets.serve(self.handle_order, self.host, self.port):
            print(f"Order server running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

    