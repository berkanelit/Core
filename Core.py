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
max_amount = 15  # Maksimum harcama tutarı

# Supertrend göstergesi hesaplama fonksiyonu
def supertrend(df, periods=10, multiplier=3, change_atr=True):
    df['hl'] = (df['high'] + df['low']) / 2
    df['tr'] = abs(df['high'] - df['low'])
    df['atr'] = df['tr'].rolling(periods).mean()
    atr = df['atr'] if change_atr else df['atr'].rolling(periods).mean()
    df['up'] = df['hl'] - (multiplier * atr)
    df['up1'] = df['up'].shift()
    df['up'] = np.where(df['close'].shift() > df['up1'], np.maximum(df['up'], df['up1']), df['up'])
    df['dn'] = df['hl'] + (multiplier * atr)
    df['dn1'] = df['dn'].shift()
    df['dn'] = np.where(df['close'].shift() < df['dn1'], np.minimum(df['dn'], df['dn1']), df['dn'])
    df['trend'] = 1
    df.loc[df['close'] <= df['dn1'], 'trend'] = -1
    df.loc[(df['trend'] == -1) & (df['close'] > df['dn1']), 'trend'] = 1
    print(df['dn1'])
    return df

def supertrend_signals(df):
    buy_signal = (df['trend'] == 1) & (df['trend'].shift() == -1)
    sell_signal = (df['trend'] == -1) & (df['trend'].shift() == 1)
    return buy_signal, sell_signal

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
        cancel_all_orders()
        time.sleep(3)
        order = client.create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print("Satım işlemi gerçekleştirildi.")
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
    with open("trade_data.json", "w") as file:
        json.dump(trade_data, file)

def load_trade_data():
    if os.path.isfile("trade_data.json"):
        with open("trade_data.json", "r") as file:
            return json.load(file)
    return {"active_trade": False, "oco_id": None}

def run_bot():
    trade_data = load_trade_data()
    while True:
        try:
            # Kripto para verilerini al
            klines = client.get_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1MINUTE,
                limit=100
            )
            
            # Kripto para verilerini DataFrame'e dönüştür
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                                               'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                                               'taker_buy_quote_asset_volume', 'ignore'])
            
            # Tarih/saat sütununu datetime veri tipine dönüştür
            # Convert relevant columns to numeric data type
            df['open'] = pd.to_numeric(df['open'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume'])
            # ... Convert other relevant columns to numeric data type

            # Tarih/saat sütununu datetime veri tipine dönüştür
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')


            
            # Supertrend göstergesini hesapla
            df = supertrend(df)
            
            # Alım ve satım sinyallerini belirle
            buy_signal, sell_signal = supertrend_signals(df)
            
            # Aktif bir alım/satım işlemi yoksa ve alım sinyali varsa
            if not trade_data["active_trade"] and buy_signal.any():
                # Alım emri yerleştir
                place_buy_order(max_amount)
            
            # Aktif bir alım işlemi varsa ve satım sinyali varsa
            elif trade_data["active_trade"] and sell_signal.any():
                # Satım emri yerleştir
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
                f"Durum: {status} Son Fiyat: {last_price} USDT ---  Cüzdan Bakiyesi: {wallet_balance} USDT", end="\r")
            time.sleep(15)
        except KeyboardInterrupt:
            print("\nBot durduruldu.")
            break
        except Exception as e:
            print("Hata run_bot:", str(e))
            time.sleep(5)

# Ana işlevi çağır
trade_data = load_trade_data()
run_bot()
