import os
import time
import pandas as pd
import numpy as np
import json
import pathlib
from binance.client import Client
from binance.enums import *

# Binance API kimlik bilgilerinizi buraya ekleyin
api_key = 'wDlvMXEY27d35HaK5Unpcvu6faqbIZF5Mr4BHQgThyOJnjHHSTwycJNwPxDSc8ov'
api_secret = '3bGsXy3UAmAsPXcBQ71ndWOKloFZfau5GAXcjyKelMrSvvxXpOVbaDMQyfId1qTm'

# Binance istemcisini oluşturun
client = Client(api_key, api_secret)

# Alım emri için gerekli parametreleri belirleyin
symbol = "RNDRUSDT"
max_amount = 1  # Maksimum harcama tutarı

# Supertrend göstergesi hesaplama fonksiyonu
def calculate_supertrend(df, period=10, multiplier=3.0, change_atr=True):
    df['tr'] = df['high'] - df['low']
    src = df['close']
    tr = pd.DataFrame()
    tr['tr0'] = abs(df['high'] - df['low'])
    tr['tr1'] = abs(df['high'] - df['close'].shift())
    tr['tr2'] = abs(df['low'] - df['close'].shift())
    tr['true_range'] = tr.max(axis=1)
    atr2 = tr['true_range'].rolling(period).mean()
    atr = atr2 if change_atr else tr['true_range']
    up = src - (multiplier * atr)
    up1 = up.shift()
    up = np.where((df['close'].shift() > up1), np.maximum(up, up1), up)
    dn = src + (multiplier * atr)
    dn1 = dn.shift()
    dn = np.where((df['close'].shift() < dn1), np.minimum(dn, dn1), dn)
    trend = np.full(len(df), -1)
    for i in range(1, len(df)):
        if trend[i - 1] == -1 and df['close'][i] > dn1[i]:
            trend[i] = 1
        elif trend[i - 1] == 1 and df['close'][i] < up1[i]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
    supertrend_up = np.where(trend == 1, up, np.nan)
    supertrend_down = np.where(trend == -1, dn, np.nan)
    df['supertrend_up'] = supertrend_up
    df['supertrend_down'] = supertrend_down
    return df

# SuperTrend göstergesine dayalı alım sinyali kontrolü
def check_buy_signal(df, active_trade):
    last_row = df.iloc[-1]
    return last_row['close'] > last_row['supertrend_up'] and not active_trade


# Alım işlemi gerçekleştirme
def place_buy_order(quantity):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_BUY,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    print("Alım işlemi gerçekleştirildi.")
    trade_data["active_trade"] = True
    trade_data["oco_id"] = None
    save_trade_data()
    
def place_sell_order(quantity):
    # Cancel all open orders
    cancel_all_orders()
    
    time.sleep(3)
    
    # Place the sell order
    order = client.create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    print("Satış işlemi gerçekleştirildi.")
    trade_data["active_trade"] = False
    trade_data["oco_id"] = None
    save_trade_data()





# OCO satış emri kontrolü
def place_oco_sell_order(quantity, take_profit_percent, stop_loss_percent):
    current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    take_profit_price = round(current_price * (1 + take_profit_percent / 100), 2)
    stop_loss_price = round(current_price * (1 - stop_loss_percent / 100), 2)

    # Fiyat filtresini kontrol etme
    symbol_info = client.get_symbol_info(symbol)
    price_filter = next((filter for filter in symbol_info['filters'] if filter['filterType'] == 'PRICE_FILTER'), None)
    if price_filter:
        min_price = float(price_filter['minPrice'])
        max_price = float(price_filter['maxPrice'])

        if take_profit_price < min_price or take_profit_price > max_price:
            raise ValueError("Take Profit fiyatı fiyat filtresine uymuyor.")
        if stop_loss_price < min_price or stop_loss_price > max_price:
            raise ValueError("Stop Loss fiyatı fiyat filtresine uymuyor.")

    take_profit_order = client.create_oco_order(
        symbol=symbol,
        side=SIDE_SELL,
        quantity=quantity,
        price=take_profit_price,
        stopPrice=stop_loss_price,
        stopLimitPrice=stop_loss_price,
        stopLimitTimeInForce=TIME_IN_FORCE_GTC
    )

    print("OCO satış emri gönderildi.")
    print("Take Profit Fiyatı:", take_profit_price)
    print("Stop Loss Fiyatı:", stop_loss_price)
    trade_data["oco_id"] = take_profit_order["orderListId"]
    save_trade_data()
    
def get_open_oco_orders():
    orders = client.get_open_orders(symbol=symbol)
    open_oco_orders = [order for order in orders if order['type'] == 'OCO']
    return open_oco_orders

def cancel_all_orders():
    open_orders = client.get_open_orders(symbol=symbol)
    if open_orders:
        for order in open_orders:
            try:
                client.cancel_order(symbol=symbol, orderId=order['orderId'])
                print(f"Emir iptal edildi: {order['orderId']}")
            except Exception as e:
                print(f"Emir iptal edilemedi: {order['orderId']}. Hata: {str(e)}")
        print("Tüm açık emirler iptal edildi.")
    else:
        print("Açık emir bulunamadı.")



def save_trade_data():
    with open('trade_data.json', 'w') as file:
        json.dump(trade_data, file)

def load_trade_data():
    if pathlib.Path('trade_data.json').is_file():
        with open('trade_data.json', 'r') as file:
            return json.load(file)
    else:
        return {"active_trade": False, "oco_id": None}

# Load trade data
trade_data = load_trade_data()

# Botun ana döngüsü
def run_bot():
    while True:
        # Son 100 dakikalık veriyi al
        klines = client.get_klines(symbol=symbol, interval=KLINE_INTERVAL_1MINUTE, limit=100)
        df = pd.DataFrame(klines,
                          columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume',
                                   'trades', 'taker_base', 'taker_quote', 'ignore'])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        
        # SuperTrend göstergesini hesapla
        df = calculate_supertrend(df)
        
        # Alım sinyalini kontrol et
        buy_signal = check_buy_signal(df, trade_data["active_trade"])
        
        if buy_signal:
            place_buy_order(max_amount)
            
        # Satış sinyalini kontrol et
        sell_signal = df.iloc[-1]['close'] < df.iloc[-1]['supertrend_down'] and trade_data["active_trade"]
        
        if sell_signal:
            place_sell_order(max_amount)
            
        if not trade_data["oco_id"]:
            balance = client.get_asset_balance(asset='RNDR')
            wallet_balance = float(balance['free'])
            if wallet_balance > 0:
             place_oco_sell_order(wallet_balance, take_profit_percent=5, stop_loss_percent=2)
            
        # OCO satışının şartlarını kontrol et
        open_oco_orders = get_open_oco_orders()
        if open_oco_orders:
            oco_order = open_oco_orders[0]
            oco_id = oco_order["orderListId"]
            if oco_id == trade_data["oco_id"]:
                if oco_order["status"] == "FILLED":
                    place_buy_order(max_amount)
                elif oco_order["status"] == "CANCELED":
                    trade_data["oco_id"] = None
                    save_trade_data()
        last_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        balance = client.get_asset_balance(asset='USDT')
        wallet_balance = float(balance['free'])
        status = trade_data["active_trade"]
        print(f"Durum: {status} Son Fiyat: {last_price} USDT ---  Cüzdan Bakiyesi: {wallet_balance} USDT --- Zaman: {time.asctime()} SuperUP: {df['supertrend_up'].iloc[-1]} SuperDO: {df['supertrend_down'].iloc[-1]}", end='\r')
        
        time.sleep(5)  # Her dakika

run_bot()
