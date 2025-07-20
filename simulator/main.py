import asyncio
from OrderBook import OrderBook
from OrderServer import OrderServer
from MarketDataServer import MarketDataServer

async def main():
    order_book = OrderBook()
    order_server = OrderServer(order_book)
    market_data_server = MarketDataServer(order_book)
    await asyncio.gather(order_server.start(), market_data_server.start())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")