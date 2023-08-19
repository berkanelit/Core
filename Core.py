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

# Alım emri için gerekli parametreleri belirleyin
symbol = "RNDRUSDT"

# Inside the run_bot() function, replace the existing max_amount assignment with:
max_amount = 30

def zerolagmacd(close, fast_period=12, slow_period=26, signal_period=12):
    
    macd = (2 * ta.ema(close, fast_period) - ta.ema(ta.ema(close, fast_period), fast_period)) - (2 * ta.ema(close, slow_period) - ta.ema(ta.ema(close, slow_period), slow_period))
    sig = (2 * ta.ema(macd, signal_period) - ta.ema(ta.ema(macd, signal_period), signal_period))
    hist = macd- sig
    return macd, sig, hist

def bb(close, length=20, mult=2):
    bb_bands = ta.bbands(close, length, mult)
    
    upper_band = bb_bands['BBL_20_2.0']
    middle_band = bb_bands['BBM_20_2.0']
    lower_band = bb_bands['BBU_20_2.0']
    
    return upper_band, middle_band, lower_band

def signals(prices, fast_period=12, slow_period=26, signal_period=12):
    zl_macd, zl_signal, zl_macd_hist = zerolagmacd(prices['close'], fast_period, slow_period, signal_period)
    upper_band, middle_band, lower_band = bb(prices['close'])
    
    buy_signal = zl_macd[198] > zl_signal[198] and zl_macd[197] < zl_signal[197] and zl_macd_hist[199] > zl_macd_hist[198] and (prices['close'][198] < middle_band[198] and prices['close'] > lower_band[198])
    sell_signal = zl_macd[198] < zl_signal[198] and zl_macd[197] > zl_signal[197] and zl_macd_hist[199] < zl_macd_hist[198]
    
    return buy_signal, sell_signal

def round_quantity(quantity, step_size):
    return round(quantity / step_size) * step_size

def place_buy_order(quantity):
    global trade_data
    try:
        order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
        )
        print("Alım işlemi gerçekleştirildi.")
        trade_data["active_trade"] = True
        save_trade_data()
    except Exception as e:
        print("Hata place_buy_order:", str(e))


def place_sell_order(quantity):
    global trade_data
    try:
        cancel_all_orders()
        order = client.create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
        )
        print("Satım işlemi gerçekleştirildi.")
        trade_data["active_trade"] = False
        trade_data["oco_id"] = None
        save_trade_data()
    except Exception as e:
        print("Hata place_sell_order:", str(e))


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


# OCO satış emri kontrolü
def place_oco_sell_order(quantity, take_profit_percent, stop_loss_percent):
    global trade_data
    try:
        symbol_info = client.get_symbol_info(symbol)
        lot_size_filter = next((filter for filter in symbol_info['filters'] if filter['filterType'] == 'LOT_SIZE'), None)
        if lot_size_filter:
            step_size = float(lot_size_filter['stepSize'])
            quantity = round_quantity(quantity, step_size)  # Yuvarlamayı uygula

        balance = client.get_asset_balance(asset='RNDR')
        wallet_balance = float(balance['free'])
        if wallet_balance > quantity:
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            take_profit_price = round(current_price * (1 + take_profit_percent / 100), 3)
            stop_loss_price = round(current_price * (1 - stop_loss_percent / 100), 3)

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
        else:
            print("Yetersiz bakiye")
    except Exception as e:
        print("Hata place_oco_sell_order:", str(e))

def save_trade_data():
    with open("trade_data.json", "w") as file:
        json.dump(trade_data, file)

def load_trade_data():
    if os.path.isfile("trade_data.json"):
        with open("trade_data.json", "r") as file:
            return json.load(file)
    return {"active_trade": False, "oco_id": None}

def check_rndr_balance():
    global trade_data
    balance = client.get_asset_balance(asset='RNDR')
    rndr_balance = float(balance['free'])
    locked_rndr_balance = float(balance['locked'])
    
    if trade_data["active_trade"] and rndr_balance + locked_rndr_balance <= 10:
        trade_data["active_trade"] = False
        trade_data["oco_id"] = None
        save_trade_data()
        print("Aktif Ticaret Durumu Olmadığı İçin False Edildi.")
        
def check_status():
    global trade_data
    try:
        bakiye = client.get_asset_balance(asset='RNDR')
        cfx_bakiye = float(bakiye['free'])
        open_orders = client.get_open_orders(symbol=symbol)
        if open_orders:
            trade_data["active_trade"] = True
        if not open_orders and cfx_bakiye > 10:
            trade_data["active_trade"] = True
            trade_data["oco_id"] = None
            
    except Exception as e:
        print("Ticaret Bulunamadı")
        

def run_bot():
    global trade_data
    trade_data = load_trade_data()
    
    while True:
        try:
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
              "timestamp",
              "open",
              "high",
              "low",
              "close",
              "volume",
              "close_time",
              "quote_asset_volume",
              "number_of_trades",
              "taker_buy_base_asset_volume",
              "taker_buy_quote_asset_volume",
              "ignore",
             ],
             )


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

            buy_signal, sell_signal = signals(df)
            
            # Aktif bir alım/satım işlemi yoksa ve alım sinyali varsa
            if not trade_data["active_trade"] and buy_signal.any():
                # Alım emri yerleştir
                place_buy_order(max_amount)
                save_trade_data()

            # Aktif bir alım işlemi varsa ve satım sinyali varsa
            elif trade_data["active_trade"] and sell_signal.any():
                # Satım emri yerleştir
                place_sell_order(max_amount)
                trade_data["active_trade"] = False
                save_trade_data()
                
            check_rndr_balance()

            if not trade_data["oco_id"] and trade_data["active_trade"] == True:
                balance = client.get_asset_balance(asset='RNDR')
                wallet_balance = float(balance['free'])
                if wallet_balance > 10:
                    place_oco_sell_order(max_amount, take_profit_percent=1, stop_loss_percent=2)
                    
            check_status()

            last_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            balance = client.get_asset_balance(asset='USDT')
            wallet_balance = float(balance['free'])
            status = trade_data["active_trade"]
            print(
                f"Durum: {status} Son Fiyat: {last_price} USDT ---  Cüzdan Bakiyesi: {wallet_balance} USDT",
                end="\r",
            )
            time.sleep(3)

        except Exception as e:
            print("Hata:", str(e))
            time.sleep(5)


# Ana işlevi çağır
trade_data = load_trade_data()
run_bot()
