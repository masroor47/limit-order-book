



class MarketDataServer:
    def __init__(self, host='localhost', port=8766, order_book=None):
        self.host = host
        self.port = port
        self.order_book = order_book
        self.server = None

    def start(self):
        pass

    def broadcast_data(self, data):
        pass

    def subscribe_client(self, websocket):
        pass