import os
import time
import pandas as pd
import pandas_ta as ta
import json
from binance.client import Client
from binance.enums import SIDE_BUY, ORDER_TYPE_MARKET, SIDE_SELL, TIME_IN_FORCE_GTC

# Binance API kimlik bilgilerinizi buraya ekleyin
api_key = ''
api_secret = ''

# Binance istemcisini oluşturun
client = Client(api_key, api_secret)

# Alım emri için kullanılan sembol
symbol = "RNDRUSDT"

# İşlem verilerini saklamak için dictionary
trade_data = {}
TRADE_DATA_PATH = "trade_data.json"

# Ticaret verilerini yükle
def load_trade_data():
    if os.path.isfile(TRADE_DATA_PATH):
        with open(TRADE_DATA_PATH, "r") as file:
            return json.load(file)
    return {"active_trade": False, "oco_id": None, "buy_order_id": None, "buy_price": None}

# Ticaret verilerini kaydet
def save_trade_data():
    with open("trade_data.json", "w") as file:
        json.dump(trade_data, file)     

# Alım miktarını hesapla
def calculate_max_amount(df):
    try:
        balance = client.get_asset_balance(asset='USDT')
        usdt_balance = float(balance['free'])
        balances = usdt_balance / df.iloc[-1]
        max_rndr_amount = round(balances * 0.9)
        return max_rndr_amount
    except Exception as e:
        print("Hata calculate_max_amount:", str(e))
        return 0

# Alım ve satım sinyallerini hesapla
def signals(prices):
    buy_signal = False
    sell_signal = False
    
    # RSI ve DEMA göstergelerini hesapla
    rsi = ta.rsi(prices['close'], 14)
    dema20 = ta.dema(prices['close'], 20)
    dema50 = ta.dema(prices['close'], 50)
    
    hist = dema20 - dema50

    # Satış sinyali koşulu: RSI 70'in üzerindeyse
    if rsi.iloc[-1] >= 70:
        sell_signal = True
    
    if dema20.iloc[-2] > dema50.iloc[-2] and dema20.iloc[-3] < dema50.iloc[-3] and hist.iloc[-1] >= hist.iloc[-2]:
        buy_signal = True
        
    if dema20.iloc[-2] < dema50.iloc[-2] and dema20.iloc[-3] > dema50.iloc[-3]:
        sell_signal = True
        
    return buy_signal, sell_signal

# Alım emri yerleştir
def place_buy_order(quantity):
    try:
        order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
        )
        print("Alım işlemi gerçekleştirildi.", order)
        trade_data["active_trade"] = True
        trade_data["buy_order_id"] = order["orderId"]
        trade_data["buy_price"] = float(order["fills"][0]["price"])
        save_trade_data()
    except Exception as e:
        print("Hata place_buy_order:", str(e))

# Satım emri yerleştir
def place_sell_order(quantity):
    try:
        cancel_all_orders()

        order = client.create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
        )
        print("Satım işlemi gerçekleştirildi.", order)
        trade_data["active_trade"] = False
        trade_data["oco_id"] = None
        save_trade_data()
    except Exception as e:
        print("Hata place_sell_order:", str(e))

# Tüm RNDR varlığını satış emri olarak yerleştir
def place_sell_order_all_rndr():
    try:
        cancel_all_orders()
        time.sleep(1)
        balance = client.get_asset_balance(asset='RNDR')
        rndr_balance = float(balance['free'])
        rndr_to_sell = int(rndr_balance)

        if rndr_to_sell > 0:
            place_sell_order(rndr_to_sell)
    except Exception as e:
        print("Hata place_sell_order_all_rndr:", str(e))

# Tüm açık emirleri iptal et
def cancel_all_orders():
    try:
        open_orders = client.get_open_orders(symbol=symbol)
        if open_orders:
            for order in open_orders:
                try:
                    client.cancel_order(
                        symbol=symbol, orderId=order['orderId'])
                    print(f"Emir iptal edildi: {order['orderId']}")
                except Exception as e:
                    print(
                        f"Emir iptal edilemedi: {order['orderId']}. Hata: {str(e)}")
            print("Tüm açık emirler iptal edildi.")
        else:
            print("Açık emir bulunamadı.")
    except Exception as e:
        print("Hata cancel_all_orders:", str(e))

# OCO satış emri yerleştirme kontrolü
def place_oco_sell_order(quantity):
    try:
        symbol_info = client.get_symbol_info(symbol)
        lot_size_filter = next(
            (filter for filter in symbol_info['filters'] if filter['filterType'] == 'LOT_SIZE'), None)

        if lot_size_filter:
            quantity = int(quantity)
            take_profit_price = round(trade_data["buy_price"] * 1.05, 3)
            stop_loss_price = round(trade_data["buy_price"] * 0.98, 3)

            take_profit_order = client.create_oco_order(
                symbol=symbol,
                side=SIDE_SELL,
                quantity=quantity,
                price=take_profit_price,
                stopPrice=stop_loss_price,
                stopLimitPrice=stop_loss_price,
                stopLimitTimeInForce=TIME_IN_FORCE_GTC,
            )

            print("OCO satış emri gönderildi.")
            print("Take Profit Fiyatı:", take_profit_price)
            print("Stop Loss Fiyatı:", stop_loss_price)
            trade_data["oco_id"] = take_profit_order["orderListId"]
            save_trade_data()
        else:
            print("Yetersiz bakiye")
    except Exception as e:
        print("Hata place_oco_sell_order:", str(e))

# RNDR bakiyesini kontrol et ve gerektiğinde ticareti durdur
def check_rndr_balance():
    try:
        balance = client.get_asset_balance(asset='RNDR')
        rndr_balance = float(balance['free'])
        locked_rndr_balance = float(balance['locked'])

        if trade_data["active_trade"] and rndr_balance + locked_rndr_balance <= 3:
            trade_data["active_trade"] = False
            trade_data["oco_id"] = None
            trade_data["buy_price"] = None
            save_trade_data()
            print("Aktif Ticaret Durumu Olmadığı İçin False Edildi.")
    except Exception as e:
        print("Hata check_rndr_balance:", str(e))

# Botu çalıştır
def run_bot():
    global trade_data
    trade_data = load_trade_data()
    
    while True:
        try:
            check_rndr_balance()
            # Kripto para verilerini al
            klines = client.get_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_15MINUTE,
                limit=200,
            )

            # Kripto para verilerini DataFrame'e dönüştür
            df = pd.DataFrame(
                klines,
                columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "number_of_trades",
                    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume",
                    "ignore",
                ],
            )

            # Sütunları uygun veri tiplerine dönüştür
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric)

            # Zaman damgalarını datetime veri tiplerine dönüştür
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            max_amount = calculate_max_amount(df["close"])

            buy_signal, sell_signal = signals(df)

            # Aktif bir alım/satım işlemi yoksa ve alım sinyali varsa
            if not trade_data["active_trade"] and buy_signal:
                print("Alım sinyali algılandı.")
                # Alım emri yerleştir
                place_buy_order(max_amount)

            # Aktif bir alım işlemi varsa ve satım sinyali varsa
            if trade_data["active_trade"] and sell_signal:
                print("Satış sinyali algılandı.")
                # Satım emri yerleştir
                place_sell_order_all_rndr()

            if not trade_data["oco_id"] and trade_data["active_trade"] and trade_data["buy_price"]:
                balance = client.get_asset_balance(asset='RNDR')
                wallet_balance = float(balance['free'])
                if wallet_balance > 10:
                    place_oco_sell_order(wallet_balance)

            if not trade_data["active_trade"] and not client.get_open_orders(symbol=symbol):
                trade_data = {"active_trade": False, "oco_id": None,
                    "buy_order_id": None, "buy_price": None}
                save_trade_data()

            last_price = float(
                client.get_symbol_ticker(symbol=symbol)['price'])
            balance = client.get_asset_balance(asset='USDT')
            wallet_balance = float(balance['free'])
            status = trade_data["active_trade"]
            print(
                f"Durum: {status} Son Fiyat: {last_price} ---  Cüzdan Bakiyesi: {wallet_balance} --- SF: {trade_data['buy_price']}",
                end="\r",
            )
            time.sleep(3)

        except Exception as e:
            time.sleep(1)
            print(f"Hata: {str(e)}")
            time.sleep(5)

# Ana işlevi çağır
if __name__ == '__main__':
    print("Bot çalıştırılıyor...")
    run_bot()
