import numpy as np
from binance import Client, ThreadedWebsocketManager
from binance.enums import *
import os

# Binance API credentials
api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')

# Binance API client connection
client = Client(api_key, api_secret)
symbol = 'RNDRBUSD'
max_usable_balance = 15

# Zero Lag MACD parameters
fast_length = 12
slow_length = 26
signal_length = 12
macd_ema_length = 9
use_ema = True
use_old_algo = False

# Exponential Moving Average (EMA)
def ema(values, period):
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    ema = np.convolve(values, weights, mode='full')[:len(values)]
    return ema

# Simple Moving Average (SMA)
def sma(values, period):
    sma = np.convolve(values, np.ones((period,))/period, mode='valid')
    return sma

# Calculate Zero Lag MACD indicator
def calculate_zerolag_macd(close_prices):
    ma1 = ema(close_prices, fast_length) if use_ema else sma(close_prices, fast_length)
    ma2 = ema(ma1, fast_length) if use_ema else sma(ma1, fast_length)
    zerolag_ema = (2 * ma1) - ma2

    mas1 = ema(close_prices, slow_length) if use_ema else sma(close_prices, slow_length)
    mas2 = ema(mas1, slow_length) if use_ema else sma(mas1, slow_length)
    zerolag_slow_ma = (2 * mas1) - mas2

    zerolag_macd = zerolag_ema - zerolag_slow_ma

    emasig1 = ema(zerolag_macd, signal_length)
    emasig2 = ema(emasig1, signal_length)
    signal = sma(zerolag_macd, signal_length) if use_old_algo else (2 * emasig1) - emasig2

    hist = zerolag_macd - signal

    return zerolag_macd, signal, hist

# Get historical klines
def get_historical_klines(interval):
    klines = client.get_historical_klines(symbol, interval, "1 day ago UTC")
    return klines

# Get account balance
def get_balance(asset, max_balance=None):
    balance = client.get_asset_balance(asset=asset)
    free_balance = float(balance['free'])
    if max_balance is not None and free_balance > max_balance:
        free_balance = max_balance
    print(f"{asset} balance: {free_balance}")
    return free_balance

# Place a limit buy order
def limit_buy(quantity, price):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_BUY,
        type=ORDER_TYPE_LIMIT,
        timeInForce=TIME_IN_FORCE_GTC,
        quantity=quantity,
        price=price)
    print(f"Limit buy order placed. Quantity: {quantity}, Price: {price}")
    return order['orderId']

# Place a limit sell order
def limit_sell(quantity, price):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=ORDER_TYPE_LIMIT,
        timeInForce=TIME_IN_FORCE_GTC,
        quantity=quantity,
        price=price)
    print(f"Limit sell order placed. Quantity: {quantity}, Price: {price}")
    return order['orderId']

# Place an OCO sell order
def oco_sell(stop_price, limit_price, quantity):
    order = client.order_oco_sell(
        symbol=symbol,
        stopLimitTimeInForce=TIME_IN_FORCE_GTC,
        stopPrice=stop_price,
        price=limit_price,
        quantity=quantity)
    print(f"OCO sell order placed. Stop Price: {stop_price}, Limit Price: {limit_price}, Quantity: {quantity}")
    return order['orderId']

# Cancel all open orders
def cancel_orders():
    orders = client.get_open_orders(symbol=symbol)
    for order in orders:
        client.cancel_order(symbol=symbol, orderId=order['orderId'])
    print("All open orders cancelled.")

# Get wallet balances
def get_wallet_balances():
    balances = client.get_account()['balances']
    return {balance['asset']: float(balance['free']) for balance in balances}

# Check OCO order status
def check_oco_order_status(order_id):
    order = client.get_order(symbol=symbol, orderId=order_id)
    return order['status']

# WebSocket callback function for real-time data
def process_message(message):
    if message['e'] == 'error':
        print(f"WebSocket error: {message['m']}")
    elif message['e'] == 'kline':
        # New kline data received
        kline = message['k']
        current_price = float(kline['c'])
        print(f"New Kline - Time: {kline['t']}, Close Price: {current_price}")

        # Calculate Zero Lag MACD
        klines = get_historical_klines(Client.KLINE_INTERVAL_15MINUTE)
        close_prices = np.array([float(kline[4]) for kline in klines])
        macd, signal, hist = calculate_zerolag_macd(close_prices)

        # Check for buy signal
        buy_signal = (hist[-1] > 0) and (macd[-1] > signal[-1])

        # Check for sell signal
        sell_signal = (hist[-1] < 0) and (macd[-1] < signal[-1])

        # Check if trade is active
        trade_active = False
        if buy_signal or sell_signal:
            trade_active = True

        if buy_signal and not trade_active:
            # Place a buy order
            balance = get_balance('BUSD', max_usable_balance)
            buy_quantity = balance / float(klines[-1][4])
            order_id = limit_buy(buy_quantity, float(klines[-1][4]))

            # Place an OCO sell order
            sell_stop_price = float(klines[-1][4]) * 0.98
            sell_limit_price = float(klines[-1][4]) * 1.02
            oco_order_id = oco_sell(sell_stop_price, sell_limit_price, buy_quantity)

        if sell_signal and trade_active:
            # Cancel all open orders
            cancel_orders()

            # Place a sell order
            balance = get_balance('RNDR')
            sell_quantity = balance
            sell_limit_price = float(klines[-1][4]) * 0.98
            limit_sell(sell_quantity, sell_limit_price)

        if oco_order_id and check_oco_order_status(oco_order_id) == 'FILLED':
            # Reset order IDs
            oco_order_id = None

# Main function
def main():
    # Create a WebSocket manager
    twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)
    twm.start()

    # Subscribe to kline data stream
    twm.start_kline_socket(callback=process_message, symbol=symbol, interval=ThreadedWebsocketManager.KLINE_INTERVAL_15MINUTE)

    # Wait for the WebSocket to connect
    twm.join()

if __name__ == '__main__':
    main()
