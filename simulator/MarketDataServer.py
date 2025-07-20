

import asyncio
import websockets
import json

class MarketDataServer:
    def __init__(self, order_book, host="127.0.0.1", port=8766):
        self.order_book = order_book
        self.host = host
        self.port = port
        self.clients = set()

    async def handle_client(self, websocket, path):
        self.clients.add(websocket)
        try:
            async for _ in websocket:  # Keep connection alive
                pass
        except websockets.exceptions.ConnectionClosed:
            self.clients.remove(websocket)

    async def broadcast_data(self):
        while True:
            state = await self.order_book.get_order_book_state()
            for client in self.clients:
                await client.send(json.dumps(state))
            await asyncio.sleep(1)  # Broadcast every second

    async def start(self):
        server = await websockets.serve(self.handle_client, self.host, self.port)
        asyncio.create_task(self.broadcast_data())
        print(f"Market data server running on ws://{self.host}:{self.port}")
        await server.wait_closed()