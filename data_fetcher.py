import ccxt
import pandas as pd
import time
import os

def fetch_data(symbol='BTC/USDT', timeframe='1d', since='2020-01-01T00:00:00Z'):
    filename = f"data/{symbol.replace('/', '_')}_{timeframe}.csv"
    print(f"Fetching {symbol} {timeframe} data from KuCoin starting {since}...")

    # Initialize the exchange
    exchange = ccxt.kucoin({
        'enableRateLimit': True,
    })

    # Convert since string to timestamp in milliseconds
    since_timestamp = exchange.parse8601(since)

    all_ohlcv = []

    while True:
        try:
            # Fetch OHLCV data
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since_timestamp, limit=1000)

            if len(ohlcv) == 0:
                break

            all_ohlcv.extend(ohlcv)

            # Update 'since' to the last timestamp + 1 ms to avoid fetching the same candle
            since_timestamp = ohlcv[-1][0] + 1

            # Respect rate limit implicitly handled by ccxt, but adding small sleep just in case
            time.sleep(exchange.rateLimit / 1000)

        except Exception as e:
            print(f"An error occurred fetching {symbol}: {e}")
            break

    if not all_ohlcv:
        print(f"No data fetched for {symbol}.")
        return

    # Convert to Pandas DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # Convert timestamp to datetime and set as index
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Save to CSV
    # Reorder columns to standard format
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    df.to_csv(filename, index=False)

    print(f"Data saved to {filename} (Total rows: {len(df)})")

if __name__ == "__main__":
    # Fetch a diversified portfolio of major crypto assets
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
    for symbol in symbols:
        fetch_data(symbol=symbol)
