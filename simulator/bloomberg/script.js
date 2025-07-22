// Helper function to format date for datetime-local
function formatDateTimeLocal(date) {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function convertDateToTimestamp(dateString) {
  const date = new Date(dateString);
  return Math.floor(date.getTime() / 1000); // Convert to seconds
}

// Initialize WebSocket connection
const ws = new WebSocket("ws://127.0.0.1:8766");

// Data storage for trades (assuming trades have 'timestamp' and 'price' fields)
let tradeData = {
  x: [], // timestamps (converted to Date objects)
  y: [], // prices
};

let ohlcTimes = [];
let opens = [];
let highs = [];
let lows = [];
let closes = [];
let volumes = [];
let currentBucket = null;
let currentCandle = {};

// For order book
let subscribedOrderBook = false;
let orderBookPlotInitialized = false;
const toggleButton = document.getElementById("toggle-orderbook");
let showOrderBook = false;

toggleButton.addEventListener("click", () => {
  showOrderBook = !showOrderBook;
  if (showOrderBook) {
    if (!subscribedOrderBook) {
      ws.send(JSON.stringify({ type: "subscribe_order_book" }));
      subscribedOrderBook = true;
    }
    document.getElementById("orderbook-plot").style.display = "block";
    toggleButton.textContent = "Hide Order Book";
  } else {
    if (subscribedOrderBook) {
      ws.send(JSON.stringify({ type: "unsubscribe_order_book" }));
      subscribedOrderBook = false;
    }
    document.getElementById("orderbook-plot").style.display = "none";
    toggleButton.textContent = "Show Order Book";
  }
});

// Date range elements
const startDateInput = document.getElementById("start-date");
const endDateInput = document.getElementById("end-date");
const candleIntervalSelect = document.getElementById("candle-interval");
const applyButton = document.getElementById("apply-range");

// Load persistent range from localStorage
const savedStart = localStorage.getItem("startDate");
const savedEnd = localStorage.getItem("endDate");
const savedCandleInterval = localStorage.getItem("candleInterval");

if (savedStart) startDateInput.value = savedStart;
if (savedEnd) endDateInput.value = savedEnd;
if (savedCandleInterval) candleIntervalSelect.value = savedCandleInterval;

// Set default start if not saved (market open today or previous day)
if (!startDateInput.value) {
  const now = new Date();
  let marketOpen = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    9,
    30,
    0,
    0
  );
  if (marketOpen > now) marketOpen.setDate(marketOpen.getDate() - 1);
  startDateInput.value = formatDateTimeLocal(marketOpen);
}

// Function to request data for a given range
function requestHistorical(fromTime, toTime) {
  ws.send(
    JSON.stringify({
      type: "request_historical",
      from_time: fromTime,
      to_time: toTime,
    })
  );
}

// Function to request OHLCV data
function requestOHLCV(fromTime, toTime, candleInterval) {
  ws.send(
    JSON.stringify({
      type: "request_historical_ohlc",
      from_time: fromTime,
      to_time: toTime,
      candle_interval: candleInterval,
    })
  );
}

// Function to initialize or update scatter plot
function updateScatterPlot(trades) {
  if (trades && Array.isArray(trades)) {
    // Sort by timestamp just in case
    trades.sort((a, b) => a.timestamp - b.timestamp);
    tradeData.x = trades.map((trade) => new Date(trade.timestamp * 1000));
    tradeData.y = trades.map((trade) => trade.price);

    const trace = {
      x: tradeData.x,
      y: tradeData.y,
      mode: "lines+markers",
      type: "scatter",
      name: "Trade Prices",
    };
    const layout = {
      title: "Equity Price",
      xaxis: { title: "Time" },
      yaxis: { title: "Price" },
    };
    Plotly.newPlot("plot", [trace], layout);
  }
}

// Function to initialize or update OHLCV plot
function updateOHLCVPlot(data) {
  if (!Array.isArray(data)) {
    console.error("Invalid historical OHLC data received:", data);

    return;
  }
  ohlcTimes = data.map((d) => new Date(d.time * 1000));
  opens = data.map((d) => d.open);
  highs = data.map((d) => d.high);
  lows = data.map((d) => d.low);
  closes = data.map((d) => d.close);
  volumes = data.map((d) => d.volume);
  //   const tickSize = parseInt(tickSizeSelect.value);

  const trace1 = {
    type: "candlestick",
    x: ohlcTimes,
    open: opens,
    high: highs,
    low: lows,
    close: closes,
    name: "Price",
    increasing: { line: { color: "green" } },
    decreasing: { line: { color: "red" } },
  };

  const trace2 = {
    type: "bar",
    x: ohlcTimes,
    y: volumes,
    name: "Volume",
    yaxis: "y2",
    marker: { color: "blue" },
  };

  const layout = {
    title: "OHLCV Chart",
    xaxis: {
      title: "Time",
      rangeslider: { visible: true }, // Optional: Add zoom slider, shows miniature copy of the chart
    },
    yaxis: {
      title: "Price",
      domain: [0.25, 1],
    },
    yaxis2: {
      title: "Volume",
      domain: [0, 0.2],
      showgrid: false,
      overlaying: false,
    },
    height: 600,
    margin: { t: 50, b: 50, l: 50, r: 50 },
  };

  Plotly.newPlot("plot", [trace1, trace2], layout);

  if (data.length > 0) {
    const last = data[data.length - 1];
    const candleInterval = parseInt(candleIntervalSelect.value);
    currentBucket =
      Math.floor(data[data.length - 1].time / candleInterval) * candleInterval;

    currentCandle = {
      open: last.open ?? null,
      high: last.high ?? null,
      low: last.low ?? null,
      close: last.close ?? null,
      volume: last.volume ?? 0,
    };
  } else {
    currentBucket = null;
    currentCandle = {};
  }
}

// Function to handle real-time OHLCV updates
function realTimeOHLCV(messageData) {
  if (!messageData.trades || !Array.isArray(messageData.trades)) {
    console.error("Invalid real-time trades data:", messageData);
    return;
  }

  messageData.trades.sort((a, b) => a.timestamp - b.timestamp);

  const candleInterval = parseInt(candleIntervalSelect.value);
  const currentFrom = convertDateToTimestamp(startDateInput.value);
  const currentTo = endDateInput
    ? convertDateToTimestamp(endDateInput.value)
    : Infinity;

  // Collect new candles to betch-extend Plotly traces
  const newX = [];
  const newOpens = [];
  const newHighs = [];
  const newLows = [];
  const newCloses = [];
  const newVolumes = [];

  let updatedLastCandle = false;

  messageData.trades.forEach((trade) => {
    if (trade.timestamp < currentFrom || trade.timestamp > currentTo) {
      console.log(`Ignoring trade outside range: ${trade.timestamp}`);
      return; // Ignore trades outside the current range
    }
    const bucket =
      Math.floor(trade.timestamp / candleInterval) * candleInterval;

    if (currentBucket == null || bucket > currentBucket) {
      console.log("making new candle");
      // Start a new candle
      newX.push(new Date(bucket * 1000));
      newOpens.push(trade.price);
      newHighs.push(trade.price);
      newLows.push(trade.price);
      newCloses.push(trade.price);
      newVolumes.push(trade.quantity);
      currentBucket = bucket;
      currentCandle = {
        open: trade.price,
        high: trade.price,
        low: trade.price,
        close: trade.price,
        volume: trade.quantity,
      };
    } else if (bucket === currentBucket) {
      // Update current candle
      if (currentCandle.open === null) currentCandle.open = trade.price;
      currentCandle.high = Math.max(
        currentCandle.high ?? trade.price,
        trade.price
      );
      currentCandle.low = Math.min(
        currentCandle.low ?? trade.price,
        trade.price
      );
      currentCandle.close = trade.price;
      currentCandle.volume += trade.quantity;
      updatedLastCandle = true;
      console.log(
        "updating current candle, updatedLastCandle:",
        updatedLastCandle
      );
    } else {
      // Trade in past bucket; ignore or handle as needed
      console.log(`Ignoring old trade in bucket ${bucket}`);
    }
  });

  //   Batch-extend Plotly traces only if we have new data
  if (newX.length > 0) {
    Plotly.extendTraces(
      "plot",
      {
        x: [newX],
        open: [newOpens],
        high: [newHighs],
        low: [newLows],
        close: [newCloses],
      },
      [0]
    );
    Plotly.extendTraces(
      "plot",
      {
        x: [newX],
        y: [newVolumes],
      },
      [1]
    );
    // Update arrays with new data
    ohlcTimes.push(...newX);
    opens.push(...newOpens);
    highs.push(...newHighs);
    lows.push(...newLows);
    closes.push(...newCloses);
    volumes.push(...newVolumes);
  }

  // Update the last candle if modified
  if (updatedLastCandle) {
    console.log("Updating last candle with new data");
    const lastIndex = ohlcTimes.length - 1;
    opens[lastIndex] = currentCandle.open;
    highs[lastIndex] = currentCandle.high;
    lows[lastIndex] = currentCandle.low;
    closes[lastIndex] = currentCandle.close;
    volumes[lastIndex] = currentCandle.volume;
    Plotly.restyle(
      "plot",
      {
        [`open[${lastIndex}]`]: currentCandle.open,
        [`high[${lastIndex}]`]: currentCandle.high,
        [`low[${lastIndex}]`]: currentCandle.low,
        [`close[${lastIndex}]`]: currentCandle.close,
      },
      [0]
    );
    Plotly.restyle(
      "plot",
      {
        [`y[${lastIndex}]`]: currentCandle.volume,
      },
      [1]
    );
  }
}

function updateOrderBook(messageData) {
  // Process order book update
  const state = messageData.data;

  if (!state || !state.bids || !state.asks) {
    console.error("Invalid order book data:", messageData);
    return;
  }

  //   Aggregate bids
  const bidLevels = Object.entries(state.bids).map(([priceStr, orders]) => {
    const price = parseFloat(priceStr);
    const totalQty = orders.reduce((sum, order) => {
      return sum + parseFloat(order.quantity);
    }, 0);
    return { price: price, quantity: totalQty };
  });
  bidLevels.sort((a, b) => b.price - a.price);
  const bids = bidLevels.slice(0, 10);

  //   Aggregate asks
  const askLevels = Object.entries(state.asks).map(([priceStr, orders]) => {
    const price = parseFloat(priceStr);
    const totalQty = orders.reduce((sum, order) => {
      return sum + parseFloat(order.quantity);
    }, 0);
    return { price: price, quantity: totalQty };
  });

  askLevels.sort((a, b) => a.price - b.price);
  const asks = askLevels.slice(0, 10);

  const bid_prices = bids.map((b) => b.price);
  const bid_quantities = bids.map((b) => -b.quantity); // Negative for left side

  const ask_prices = asks.map((a) => a.price);
  const ask_quantities = asks.map((a) => a.quantity);

  const allQuantities = [
    ...bids.map((b) => b.quantity),
    ...asks.map((a) => a.quantity),
  ];
  const maxQty = allQuantities.length > 0 ? Math.max(...allQuantities) : 0;

  const trace1 = {
    y: bid_prices,
    x: bid_quantities,
    type: "bar",
    orientation: "h",
    marker: { color: "green" },
    name: "Bids",
    width: 0.1,
  };

  const trace2 = {
    y: ask_prices,
    x: ask_quantities,
    type: "bar",
    orientation: "h",
    marker: { color: "red" },
    name: "Asks",
    width: 0.1,
  };

  const layout = {
    title: "Market Depth",
    yaxis: { title: "Price" },
    xaxis: {
      title: "Quantity",
      range: [-maxQty * 1.1, maxQty * 1.1],
      tickmode: "array",
      showgrid: true,
    },
    showlegend: true,
    barmode: "overlay",
  };

  if (!orderBookPlotInitialized) {
    Plotly.newPlot("orderbook-plot", [trace1, trace2], layout);
    orderBookPlotInitialized = true;
  } else {
    Plotly.react("orderbook-plot", [trace1, trace2], layout);
  }
}

function realTimeScatter(data) {
  // Append new trades if they fall within the current range
  const currentFrom = startDateInput.value
    ? new Date(startDateInput.value).getTime() / 1000
    : 0;
  const currentTo = endDateInput.value
    ? new Date(endDateInput.value).getTime() / 1000
    : Infinity;
  if (data.trades && Array.isArray(data.trades)) {
    const newX = [];
    const newY = [];
    for (const trade of data.trades) {
      if (trade.timestamp >= currentFrom && trade.timestamp <= currentTo) {
        tradeData.x.push(new Date(trade.timestamp * 1000));
        tradeData.y.push(trade.price);
        newX.push(new Date(trade.timestamp * 1000));
        newY.push(trade.price);
      }
    }
    if (newX.length > 0) {
      // Append to the existing trace (index 0, assuming single trace)
      Plotly.extendTraces("plot", { x: [newX], y: [newY] }, [0]);
    }
  }
}

ws.onopen = function () {
  console.log("WebSocket connected");

  const startValue = startDateInput.value;
  const endValue = endDateInput.value;
  const candleIntervalValue = parseInt(candleIntervalSelect.value);

  const fromTime = convertDateToTimestamp(startValue);
  const toTime = endValue
    ? convertDateToTimestamp(endValue)
    : Math.floor(Date.now() / 1000);
  requestOHLCV(fromTime, toTime, candleIntervalValue);
};

ws.onmessage = function (event) {
  let data;
  try {
    data = JSON.parse(event.data);
  } catch (e) {
    console.error("Invalid JSON received:", event.data);
    return;
  }

  if (data.type === "historical_trades") {
    updateScatterPlot(data.trades);
    ws.send(JSON.stringify({ type: "subscribe_trades" }));
  } else if (data.type == "historical_ohlc") {
    updateOHLCVPlot(data.data);
    ws.send(JSON.stringify({ type: "subscribe_trades" }));
  } else if (data.type === "new_trades") {
    realTimeOHLCV(data);
    // realTimeScatter(data);
  } else if (data.type === "order_book_update") {
    updateOrderBook(data);
  } else {
    console.warn("Unknown message type:", data.type);
  }
};

ws.onclose = function () {
  console.log("WebSocket disconnected");
  // Optionally, you can attempt to reconnect here
};

ws.onerror = function (error) {
  console.error("WebSocket error:", error);
};

// Apply range button listener

applyButton.addEventListener("click", () => {
  const startValue = startDateInput.value;
  const endValue = endDateInput.value;
  const candleIntervalValue = parseInt(candleIntervalSelect.value);

  // Save to localStorage for persistence
  localStorage.setItem("startDate", startValue || "");
  localStorage.setItem("endDate", endValue || "");
  localStorage.setItem("candleInterval", candleIntervalValue || "");

  const fromTime = convertDateToTimestamp(startValue);
  const toTime = endValue
    ? convertDateToTimestamp(endValue)
    : Math.floor(Date.now() / 1000);

  requestOHLCV(fromTime, toTime, candleIntervalValue);
});
