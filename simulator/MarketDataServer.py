

import asyncio
import websockets
import json

from typing import List, Dict


class MarketDataServer:
    def __init__(self, order_book, host="127.0.0.1", port=8766):
        self.order_book = order_book
        self.host = host
        self.port = port
        self.clients = set()  # Maps websocket to set of subscriptions (e.g., 'real_time')
        self.subscribers = {}  # websocket -> dict of {'trades': True, 'order_book': {'interval': 1.0}}  # For now, fixed interval; later per-user customizable
        self.order_book_interval = 0.5  # seconds
        # self.order_book_interval = 1.0  # seconds

    async def listen_to_events(self):
        while True:
            event = await self.order_book.event_queue.get()
            if event['type'] == 'new_trades':  # Can extend for other events
                message = json.dumps(event)
                for client, subs in list(self.subscribers.items()):
                    if subs.get('trades', False):
                        try:
                            await client.send(message)
                        except Exception:
                            self.clients.discard(client)
                            self.subscribers.pop(client, None)

    async def handle_client(self, websocket):
        self.clients.add(websocket)
        self.subscribers[websocket] = {'trades': False, 'order_book': False}  # Start unsubscribed; client must subscribe
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type')
                    if msg_type == 'request_historical':
                        from_time = data.get('from_time')
                        to_time = data.get('to_time')
                        historical = await self.order_book.get_historical_trades(from_time, to_time)
                        await websocket.send(json.dumps({'type': 'historical_trades', 'trades': historical}))
                    elif msg_type == 'request_historical_ohlc':
                        print("got a request for historical ohlc")
                        from_time = data.get('from_time')
                        to_time = data.get('to_time')
                        candle_interval = data.get('candle_interval', 60.0)  # Default 1min
                        ohlc = await self.get_historical_ohlc(from_time, to_time, candle_interval)
                        await websocket.send(json.dumps({'type': 'historical_ohlc', 'data': ohlc}))
                    elif msg_type == 'subscribe_trades':
                        self.subscribers[websocket]['trades'] = True
                    elif msg_type == 'unsubscribe_trades':
                        self.subscribers[websocket]['trades'] = False
                    elif msg_type == 'subscribe_order_book':
                        # For now, fixed interval; later: interval = data.get('interval', 1.0)
                        self.subscribers[websocket]['order_book'] = True  # Or {'interval': interval}
                    elif msg_type == 'unsubscribe_order_book':
                        self.subscribers[websocket]['order_book'] = False
                except json.JSONDecodeError:
                    pass  # Ignore invalid messages
        finally:
            self.clients.remove(websocket)
            self.subscribers.pop(websocket, None)

    async def get_historical_ohlc(self, from_time: float = None, to_time: float = None, interval: float = 60.0) -> List[Dict]:
        async with self.order_book.lock:
            if interval <= 0:
                raise ValueError("Interval must be positive")
            params = {'interval': interval}
            query = '''
                WITH buckets AS (
                    SELECT
                        floor(timestamp / :interval) * :interval AS bucket_start,
                        timestamp,
                        price,
                        quantity,
                        ROW_NUMBER() OVER (PARTITION BY floor(timestamp / :interval) ORDER BY timestamp ASC) AS rn_asc,
                        ROW_NUMBER() OVER (PARTITION BY floor(timestamp / :interval) ORDER BY timestamp DESC) AS rn_desc
                    FROM trades
            '''
            if from_time is not None:
                query += ' WHERE timestamp >= :from_time'
                params['from_time'] = from_time
                if to_time is not None:
                    query += ' AND timestamp <= :to_time'
                    params['to_time'] = to_time
            elif to_time is not None:
                query += ' WHERE timestamp <= :to_time'
                params['to_time'] = to_time
            query += '''
                )
                SELECT
                    bucket_start,
                    MAX(CASE WHEN rn_asc = 1 THEN price END) AS open,
                    MAX(price) AS high,
                    MIN(price) AS low,
                    MAX(CASE WHEN rn_desc = 1 THEN price END) AS close,
                    SUM(quantity) AS volume
                FROM buckets
                GROUP BY bucket_start
                HAVING open IS NOT NULL  -- Skip empty buckets
                ORDER BY bucket_start ASC
            '''
            cursor = self.order_book.db_conn.execute(query, params)
            return [
                {'time': row[0], 'open': row[1], 'high': row[2], 'low': row[3], 'close': row[4], 'volume': row[5]}
                for row in cursor.fetchall()
            ]

    async def broadcast_order_book(self):
        while True:
            state = await self.order_book.get_order_book_state()
            message = json.dumps({'type': 'order_book_update', 'data': state})
            for client, subs in list(self.subscribers.items()):
                if subs.get('order_book', False):
                    try:
                        await client.send(message)
                    except Exception:
                        # Clean up
                        self.clients.discard(client)
                        self.subscribers.pop(client, None)
            await asyncio.sleep(self.order_book_interval)

    async def start(self):
        server = await websockets.serve(self.handle_client, self.host, self.port)
        asyncio.create_task(self.broadcast_order_book())  # Periodic for order book subscribers
        asyncio.create_task(self.listen_to_events())  # Event-driven for trades
        print(f"Market data server running on ws://{self.host}:{self.port}")
        await server.wait_closed()