import asyncio
import websockets
import matplotlib.pyplot as plt

async def handle_connection(websocket):
    print(f"New connection from {websocket.remote_address}")
    times = []
    try:
        async for message in websocket:
            curr_time = asyncio.get_event_loop().time()
            times.append(curr_time)
            print(f"Received message: {message} at {curr_time}")
            await websocket.send(f"Echo: {message}")
    except websockets.ConnectionClosed:
        print(f"Connection closed from {websocket.remote_address}")
    finally:
        diff = [times[i] - times[i - 1] for i in range(1, len(times))]
        average_time = sum(diff) / len(diff) if diff else 0
        print(f"Average time between messages: {average_time:.4f} seconds")

        std = (sum((x - average_time) ** 2 for x in diff) / len(diff)) ** 0.5 if diff else 0
        print(f"Standard deviation of time differences: {std:.4f} seconds")
        # plot time differences at each time and also histogram of time differences
        diff = [0] + diff  # prepend 0 for the first message
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        plt.plot(times, diff, marker='o')
        plt.title("Time Differences Between Messages")
        plt.xlabel("Time")
        plt.ylabel("Time Difference (seconds)")
        plt.subplot(1, 2, 2)
        plt.hist(diff, bins=20, edgecolor='black')
        plt.title("Histogram of Time Differences")
        plt.xlabel("Time Difference (seconds)")
        plt.ylabel("Frequency")
        plt.tight_layout()
        plt.show()



async def main():
    async with websockets.serve(handle_connection, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")