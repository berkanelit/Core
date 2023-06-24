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
max_amount = 15  # Maksimum harcama tutarı

# Supertrend göstergesi hesaplama fonksiyonu

def calculate_supertrend(df, period=10, multiplier=3.0):
    try:
        # Hesaplama için gerekli sütunları oluştur
        df['tr'] = df['high'] - df['low']
        df['atr'] = df['tr'].rolling(period).mean()
        df['lower_band'] = df['high'] + (multiplier * df['atr'])
        df['upper_band'] = df['low'] - (multiplier * df['atr'])
        
        return df
    except Exception as e:
        print("Hata calculate_supertrend:", str(e))
        return df



# SuperTrend göstergesine dayalı alım sinyali kontrolü
def check_buy_signal(df, active_trade):
    try:
        last_row = df.iloc[-1]
        return last_row['close'] > last_row['lower_band'] and not active_trade
    except Exception as e:
        print("Hata check_buy_signal:", str(e))
        return False


# Alım işlemi gerçekleştirme
def place_buy_order(quantity):
    try:
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
    except Exception as e:
        print("Hata place_buy_order:", str(e))


def place_sell_order(quantity):
    try:
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
    except Exception as e:
        print("Hata place_sell_order:", str(e))


# OCO satış emri kontrolü
def place_oco_sell_order(quantity, take_profit_percent, stop_loss_percent):
    try:
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
    except Exception as e:
        print("Hata place_oco_sell_order:", str(e))


def get_open_oco_orders():
    try:
        orders = client.get_open_orders(symbol=symbol)
        open_oco_orders = [order for order in orders if order['type'] == 'OCO']
        return open_oco_orders
    except Exception as e:
        print("Hata get_open_oco_orders:", str(e))
        return []


def cancel_all_orders():
    try:
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
    except Exception as e:
        print("Hata cancel_all_orders:", str(e))


def save_trade_data():
    try:
        with open('trade_data.json', 'w') as file:
            json.dump(trade_data, file)
    except Exception as e:
        print("Hata save_trade_data:", str(e))


def load_trade_data():
    try:
        if pathlib.Path('trade_data.json').is_file():
            with open('trade_data.json', 'r') as file:
                return json.load(file)
        else:
            return {"active_trade": False, "oco_id": None}
    except Exception as e:
        print("Hata load_trade_data:", str(e))
        return {"active_trade": False, "oco_id": None}


def run_bot():
    while True:
        try:
            # Son 100 dakikalık veriyi al
            klines = client.get_klines(symbol=symbol, interval=KLINE_INTERVAL_1MINUTE, limit=100)
            df = pd.DataFrame(klines,
                              columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                                       'quote_asset_volume',
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
            sell_signal = df.iloc[-1]['close'] < df.iloc[-1]['lower_band'] and trade_data["active_trade"]

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
            print(
                f"Durum: {status} Son Fiyat: {last_price} USDT ---  Cüzdan Bakiyesi: {wallet_balance} USDT SuperUP: {df['upper_band'].iloc[-1]} SuperDO: {df['lower_band'].iloc[-1]}", end="\r")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nBot durduruldu.")
            break
        except Exception as e:
            print("Hata run_bot:", str(e))
            time.sleep(5)


# Ana işlevi çağır
trade_data = load_trade_data()
run_bot()
