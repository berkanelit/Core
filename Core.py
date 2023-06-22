import os
import time
import pandas as pd
import numpy as np
import json
from binance.client import Client
from binance.enums import *

# Binance API kimlik bilgilerinizi buraya ekleyin
api_key = 'wDlvMXEY27d35HaK5Unpcvu6faqbIZF5Mr4BHQgThyOJnjHHSTwycJNwPxDSc8ov'
api_secret = '3bGsXy3UAmAsPXcBQ71ndWOKloFZfau5GAXcjyKelMrSvvxXpOVbaDMQyfId1qTm'

# Binance istemcisini oluşturun
client = Client(api_key, api_secret)

# Alım emri için gerekli parametreleri belirleyin
symbol = "RNDRUSDT"
max_amount = 5  # Maksimum harcama tutarı

# Dosya adları
trade_data_file = "trade_data.json"
active_trade_file = "active_trade.json"

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
    trend = np.ones(len(df))
    for i in range(1, len(df)):
        if trend[i - 1] == -1 and df['close'][i] < dn1[i]:
            trend[i] = 1
        elif trend[i - 1] == 1 and df['close'][i] > up1[i]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
    df['supertrend_up'] = np.where(trend == 1, up, np.nan)
    df['supertrend_down'] = np.where(trend == -1, dn, np.nan)
    return df


# SuperTrend göstergesine dayalı alım sinyali kontrolü
def check_buy_signal(df):
    last_row = df.iloc[-1]
    return last_row['close'] > last_row['supertrend_down']


# Alım işlemi gerçekleştirme
def place_buy_order(quantity):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_BUY,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    print("Alım işlemi gerçekleştirildi.")


# Satış işlemi gerçekleştirme
def place_sell_order(quantity):
    order = client.create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    print("Satış işlemi gerçekleştirildi.")


# OCO satış emri kontrolü
def place_oco_sell_order(quantity, take_profit_percent, stop_loss_percent):
    current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    take_profit_price = current_price * (1 + take_profit_percent / 100)
    stop_loss_price = current_price * (1 - stop_loss_percent / 100)

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


# Alım-satım verilerini JSON dosyasına kaydetme
def save_trade_data(trade_id, datetime, action):
    data = {
        "trade_id": trade_id,
        "datetime": datetime,
        "action": action
    }
    with open(trade_data_file, "a") as file:
        file.write(json.dumps(data) + "\n")


# Aktif ticaret durumunu JSON dosyasına kaydetme
def save_active_trade(active_trade):
    data = {
        "active_trade": active_trade
    }
    with open(active_trade_file, "w") as file:
        json.dump(data, file)


# Aktif ticaret durumunu JSON dosyasından yükleme
def load_active_trade():
    if os.path.isfile(active_trade_file):
        with open(active_trade_file, "r") as file:
            data = json.load(file)
            return data.get("active_trade", False)
    return False


# Botun ana döngüsü
def run_bot():
    active_trade = load_active_trade()
    oco_id = None

    while True:
        # Son 100 dakikalık veriyi al
        klines = client.get_klines(symbol=symbol, interval=KLINE_INTERVAL_15MINUTE, limit=100)
        df = pd.DataFrame(klines,
                          columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume',
                                   'trades', 'taker_base', 'taker_quote', 'ignore'])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)

        # Supertrend göstergesini hesapla
        df = calculate_supertrend(df, period=10, multiplier=3.0, change_atr=True)

        # Alım sinyali kontrolü
        if check_buy_signal(df) and not active_trade:
            # Alım işlemi gerçekleştirme
            place_buy_order(max_amount)
            active_trade = True
            save_trade_data(trade_id="BUY", datetime=time.time(), action="BUY")
            save_active_trade(active_trade)

        # Satış sinyali kontrolü
        if not check_buy_signal(df) and active_trade:
            balance = client.get_asset_balance(asset='RNDR')
            quantity = float(balance['free'])
            place_sell_order(quantity)
            save_trade_data(trade_id="SELL", datetime=time.time(), action="SELL")
            active_trade = False
            oco_id = None
            save_active_trade(active_trade)

        # Aktif ticaret varsa ve OCO ID yoksa
        if active_trade and not oco_id:
            balance = client.get_asset_balance(asset='RNDR')
            quantity = float(balance['free'])
            take_profit_percent = 5.0  # %5 kar
            stop_loss_percent = 2.0  # %2 zarar

            # OCO satış emri gönderme
            place_oco_sell_order(quantity, take_profit_percent, stop_loss_percent)
            oco_id = True
        
        # Son fiyat durumu ve cüzdan bakiyesini güncelleme
        last_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        balance = client.get_asset_balance(asset='USDT')
        wallet_balance = float(balance['free'])
        print(f"Son Fiyat: {last_price} USDT ---  Cüzdan Bakiyesi: {wallet_balance} USDT ---  Aktif Ticaret: {active_trade} --- Zaman: {time.asctime()}")

        time.sleep(10)

# Botu çalıştır
run_bot()
