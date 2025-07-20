
import asyncio
import websockets
import json
import time

from OrderBook import OrderBook


class OrderServer:
    def __init__(self, 
                 host='localhost', 
                 port=8765, 
                 order_book=None):
        self.host = host
        self.port = port
        self.order_book = order_book
        self.server = None

    def start(self):
        pass

    async def handle_order(self, websocket, order):
        pass