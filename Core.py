import ccxt
import time
import pandas as pd
import json

# Binance API anahtarları
api_key = 'wDlvMXEY27d35HaK5Unpcvu6faqbIZF5Mr4BHQgThyOJnjHHSTwycJNwPxDSc8ov'
api_secret = '3bGsXy3UAmAsPXcBQ71ndWOKloFZfau5GAXcjyKelMrSvvxXpOVbaDMQyfId1qTm'

# Binance bağlantısı
binance = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
})

# Ticaret parametreleri
symbol = 'RNDR/USDT'  # Ticaret yapmak istediğiniz parite
timeframe = '15m'  # Zaman dilimi

# Supertrend göstergesi parametreleri
supertrend_period = 10
supertrend_multiplier = 3.0

# Alım satım durumu ve OCO emri
active_trade = False
oco_order_id = None

# Veritabanı dosyası
database_file = 'trading_data.json'

# Veritabanı dosyasını yükle veya boş bir veritabanı oluştur
try:
    with open(database_file, 'r') as file:
        database = json.load(file)
except FileNotFoundError:
    database = {
        'active_trade': False,
        'oco_order_id': None,
        'profit_rate': 0.0,
        'trades': []
    }

# Başlangıç bakiyesi
initial_balance = 10000  # USD

# Supertrend göstergesini hesapla
def calculate_supertrend(df):
    hl2 = (df['high'] + df['low']) / 2
    atr = df['high'] - df['low']
    atr = atr.rolling(supertrend_period).mean()

    df['upper_band'] = hl2 - (supertrend_multiplier * atr)
    df['lower_band'] = hl2 + (supertrend_multiplier * atr)

    return df

# Alım satım işlemlerini gerçekleştir
def perform_trade():
    global active_trade, oco_order_id

    # Son kapanış fiyatını al
    ticker = binance.fetch_ticker(symbol)
    close_price = ticker['close']

    # OHLCV verilerini al
    ohlcv = binance.fetch_ohlcv(symbol, timeframe)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Supertrend göstergesini hesapla
    df = calculate_supertrend(df)

    # Al sinyali
    if close_price > df['lower_band'].iloc[-1] and close_price < df['upper_band'].iloc[-2] and not active_trade:
        # Alım yap
        print("Alım")
        max_usdt = 30  # Maksimum USDT tutarı
        usdt_balance = binance.fetch_balance()['total']['USDT']
        rndr_price = binance.fetch_ticker(symbol)['ask']
        rndr_quantity = min(max_usdt / rndr_price, usdt_balance)
        quantity = binance.amount_to_precision(symbol, rndr_quantity)

        buy_order = binance.create_market_buy_order(symbol, quantity)

        # OCO emri oluştur
        stop_loss, take_profit = set_stop_loss_take_profit(df)
        
        stop_loss_price = stop_loss  # Set your stop-loss price
        take_profit_price = take_profit  # Set your take-profit price

        oco_order = binance.create_order(
            symbol,
            'OCO',
            'limit',
            quantity,
            None,
            {
                'stopLoss': {
                    'stopPrice': stop_loss_price,
                    'type': 'STOP_MARKET'
                },
                'takeProfit': {
                    'stopPrice': take_profit_price,
                    'type': 'TAKE_PROFIT_MARKET'
                }
            }
        )

        oco_order_id = oco_order['id']
        active_trade = True

        print(f"Alım yapıldı. Alınan RNDR miktarı: {quantity}")

        # Yapılan ticaretin bilgilerini kaydet
        trade_info = {
            'trade_type': 'buy',
            'quantity': quantity,
            'buy_price': close_price,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'timestamp': int(time.time())
        }
        database['trades'].append(trade_info)

    # Sat sinyali
    elif close_price < df['upper_band'].iloc[-1] and close_price > df['lower_band'].iloc[-2] and active_trade:
        # Aktif alım işlemi varsa iptal et
        print("Satım")
        if oco_order_id is not None:
            binance.cancel_order(oco_order_id)
            print('Alım işlemi iptal edildi.')

        # Satış yap
        rndr_balance = binance.fetch_balance()['total']['RNDR']
        quantity = binance.amount_to_precision(symbol, rndr_balance)
        sell_order = binance.create_market_sell_order(symbol, quantity)

        active_trade = False

        print(f"Satış yapıldı. Satılan RNDR miktarı: {quantity}")

        # Yapılan ticaretin bilgilerini kaydet
        trade_info = {
            'trade_type': 'sell',
            'quantity': quantity,
            'sell_price': close_price,
            'timestamp': int(time.time())
        }
        database['trades'].append(trade_info)

# Stop loss ve take profit seviyelerini ayarla
def set_stop_loss_take_profit(df):
    atr = df['high'] - df['low']
    atr = atr.rolling(supertrend_period).mean()
    atr_current = atr.iloc[-1]
    close_price = df['close'].iloc[-1]

    stop_loss = close_price - (atr_current * 0.02)
    take_profit = close_price + (atr_current * 0.04)

    return stop_loss, take_profit

# Veritabanını güncelle
def update_database():
    global active_trade, oco_order_id
    database['active_trade'] = active_trade
    database['oco_order_id'] = oco_order_id

    with open(database_file, 'w') as file:
        json.dump(database, file)

# Açık olan tüm emirleri iptal et
def cancel_all_orders():
    orders = binance.fetch_open_orders(symbol)
    for order in orders:
        binance.cancel_order(order['id'])
        print(f"Iptal edilen emir: {order['id']}")

# Kar oranını hesapla ve JSON dosyasına kaydet
def calculate_profit_rate():
    trade_count = len(database['trades'])
    if trade_count == 0:
        return 0.0

    total_profit = 0.0
    for trade in database['trades']:
        if trade['trade_type'] == 'sell':
            buy_price = trade['buy_price']
            sell_price = trade['sell_price']
            quantity = trade['quantity']

            profit = (sell_price - buy_price) * quantity
            total_profit += profit

    profit_rate = (total_profit / initial_balance) * 100
    database['profit_rate'] = profit_rate

# Ticaret durumunu kontrol et
def check_trade_status():
    global active_trade, oco_order_id

    if oco_order_id is not None:
        # OCO emrini kontrol et
        oco_order = binance.fetch_order(oco_order_id)

        if oco_order['status'] == 'closed':
            # OCO emri gerçekleşti
            if oco_order['side'] == 'sell':
                print('OCO emri gerçekleşti. %4 karda satış yapıldı.')
            elif oco_order['side'] == 'stop_loss':
                print('OCO emri gerçekleşti. %2 zararda satış yapıldı.')

            oco_order_id = None

            # Kar oranını hesapla ve JSON dosyasına kaydet
            calculate_profit_rate()

# Ana döngü
while True:
    try:
        perform_trade()
        check_trade_status()
        update_database()
        calculate_profit_rate()

        ticker = binance.fetch_ticker(symbol)
        close_price = ticker['close']
        trade_status = "Açık" if active_trade else "Kapalı"
        print(f"Aktif Ticaret Durumu: {trade_status} - {symbol} Fiyatı: {close_price}", end="\r")

        time.sleep(5)
    except Exception as e:
        print('Hata oluştu:', str(e))
        cancel_all_orders()
        update_database()
        calculate_profit_rate()
        time.sleep(10)
