# Stock Exchange Simulator

This is a from-scratch stock exchange simulator which I'm building to understand how it all works.

## How Works

It consists of:

- limit order book which matches orders
- order generator that randomly adds buy and sell orders
- last price line chart
- real-time bid ask bar plot

## Later

In the future I will create different types of counterparties like market makers, market movers and just random noise (sorry retail traders)

Currently everything is in a python file but in the future the system will be made out of independenlty running services written in c++ which will use network messages or sockets to communicate with each other.

## Sample Output

Figure generated at the end of the simulation showing candle sticks.

![Figure showing the simulated trades as well as volume](./plots/60s_500_orders_0.1.png)

Real-time order book showing bids and asks as bars.

![Bid ask order book.](./plots/bid-ask-order-book.png)
