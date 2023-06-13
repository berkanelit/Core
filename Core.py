import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import datetime
from binance.client import Client
from binance.enums import *
import numpy as np
import time
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from binance.client import Client
import numpy as np
from datetime import datetime

# Binance API kimlik bilgileri
api_key = 'wDlvMXEY27d35HaK5Unpcvu6faqbIZF5Mr4BHQgThyOJnjHHSTwycJNwPxDSc8ov'
api_secret = '3bGsXy3UAmAsPXcBQ71ndWOKloFZfau5GAXcjyKelMrSvvxXpOVbaDMQyfId1qTm'

# Binance API istemci bağlantısı
client = Client(api_key, api_secret)

print('API başlatıldı. Bağlantı kuruldu...')

# İşlem çifti
symbol = 'RNDRBUSD'

max_kullanilabilir_bakiye = 15

quantity = round(max_kullanilabilir_bakiye, 2)

# Ana uygulama penceresini başlat
window = tk.Tk()
window.title("Binance-Bot")
window.geometry("800x600")

# Fiyat grafiği için figür oluşturma
fig = plt.figure(figsize=(6, 4), dpi=100)
ax = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=window)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Cüzdan bilgisi için etiket oluşturma
balance_label = tk.Label(window, text="Balance: ")
balance_label.pack(side=tk.BOTTOM)

# Fiyat tablosu için bir çerçeve oluşturun
price_frame = tk.Frame(window)
price_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Fiyat tablosu için bir şekil ve eksen oluşturun
price_figure = Figure(figsize=(8, 4), dpi=100)
price_axes = price_figure.add_subplot(111)
price_canvas = FigureCanvasTkAgg(price_figure, master=price_frame)
price_canvas.draw()
price_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Düğmeler için bir çerçeve oluşturun
button_frame = tk.Frame(window)
button_frame.pack(side=tk.BOTTOM, fill=tk.X)

# Satın Al ve Sat düğmeleri oluşturun
buy_button = tk.Button(button_frame, text="Buy", width=10)
sell_button = tk.Button(button_frame, text="Sell", width=10)
buy_button.pack(side=tk.LEFT, padx=10, pady=10)
sell_button.pack(side=tk.LEFT, padx=10, pady=10)

# Satın alma veya satma emri verme işlevi
def place_order(order_type):
    global symbol, quantity
    if order_type == 'buy':
        # Satın al
        order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print("Buy order placed:", order)
    elif order_type == 'sell':
        # Sat
        order = client.create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print("Sell order placed:", order)

buy_button.config(command=lambda: place_order("buy"))
sell_button.config(command=lambda: place_order("sell"))

# Son 100 mum çubuğunu güncelleme ve fiyat grafiğini çizme işlevi
def update_price_chart():
    global symbol, ax

    # Son 100 mum çubuğunu al
    klines = client.get_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_15MINUTE,
        limit=100
    )

    # Mum çubuklarını çizme
    candles = np.array(klines)
    timestamps = candles[:, 0].astype(np.int64) / 1000
    dates = [datetime.fromtimestamp(ts) for ts in timestamps]
    opens = candles[:, 1].astype(np.float)
    highs = candles[:, 2].astype(np.float)
    lows = candles[:, 3].astype(np.float)
    closes = candles[:, 4].astype(np.float)

    ax.clear()
    ax.xaxis_date()
    ax.plot(dates, closes, "-")

    # Güncellenen fiyatı al ve ekranda gösterme
    current_price = float(closes[-1])
    current_price_label.config(text="Current Price: {:.2f}".format(current_price))

    # Cüzdan durumunu güncelleme ve ekranda gösterme
    balance = get_account_balance()
    balance_label.config(text="Balance: {}".format(balance))

    # Çizimi güncelleme
    canvas.draw()

# Hesap bakiyesini al ve güncellemeleri yapma işlevi
def get_account_balance():
    account_info = client.get_account()
    balances = account_info["balances"]
    for balance in balances:
        if balance["asset"] == "BUSD":
            return float(balance["free"])
    return 0.00

balance_label = tk.Label(window, text="Balance: 0.00")
balance_label.pack(side=tk.BOTTOM)

fig = Figure(figsize=(6, 4), dpi=100)
ax = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=window)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

current_price_label = tk.Label(window, text="Current Price: 0.00")
current_price_label.pack(side=tk.BOTTOM)



# Son 100 mum çubuğunu güncelleme ve fiyat grafiğini çizme işlevi
def update_price_chart():
    global symbol, ax

    # Son 100 mum çubuğunu al
    klines = client.get_historical_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_15MINUTE,
        limit=100
    )

    # Mum çubuklarını çizme
    candles = np.array(klines)
    timestamps = candles[:, 0].astype(np.int64) / 1000
    dates = [datetime.fromtimestamp(ts) for ts in timestamps]
    closes = candles[:, 4].astype(float)

    ax.clear()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    ax.plot(dates, closes, "-")

    # Güncellenen fiyatı al ve ekranda gösterme
    current_price = float(closes[-1])
    current_price_label.config(text="Current Price: {:.2f}".format(current_price))

    # Cüzdan durumunu güncelleme ve ekranda gösterme
    balance = get_account_balance()
    balance_label.config(text="Balance: {:.2f}".format(balance))

    # Çizimi güncelleme
    canvas.draw()

# Hesap bakiyesini al ve güncellemeleri yapma işlevi
def get_account_balance():
    account_info = client.get_account()
    balances = account_info["balances"]
    for balance in balances:
        if balance["asset"] == "USDT":
            return balance["free"]
    return "N/A"


# Sıfır Gecikmeli MACD göstergesi hesaplama işlevleri
def calculate_macd(prices, slow_period=26, fast_period=12, signal_period=9):
    exp1 = calculate_ema(prices, fast_period)
    exp2 = calculate_ema(prices, slow_period)
    macd_line = exp1 - exp2
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_ema(prices, period=12):
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    ema = np.convolve(prices, weights, mode='full')[:len(prices)]
    ema[:period] = ema[period]
    return ema

# İşlem emirleri verme işlevleri
def place_limit_order(order_type, price):
    global symbol, quantity
    if order_type == 'buy':
        # Alış limit emri
        order = client.create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=price
        )
        print("Buy limit order placed:", order)
    elif order_type == 'sell':
        # Satış limit emri
        order = client.create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=price
        )
        print("Sell limit order placed:", order)

def place_oco_order(stop_price, limit_price):
    global symbol, quantity
    oco_order = client.create_oco_order(
        symbol=symbol,
        side=SIDE_SELL,
        stopLimitTimeInForce=TIME_IN_FORCE_GTC,
        quantity=quantity,
        stopPrice=stop_price,
        price=limit_price
    )
    print("OCO order placed:", oco_order)

def cancel_orders():
    global symbol
    open_orders = client.get_open_orders(symbol=symbol)
    for order in open_orders:
        client.cancel_order(
            symbol=symbol,
            orderId=order['orderId']
        )

# Hesap bakiyesini ve işlem geçmişini almak için işlevler
def get_account_balance():
    account = client.get_account()
    for balance in account['balances']:
        if balance['asset'] == 'BUSD':
            return float(balance['free'])
    return 0.0

def get_trade_history():
    global symbol
    trades = client.get_my_trades(symbol=symbol)
    for trade in trades:
        print(trade)

# MACD göstergesini güncelleme ve işlem stratejisini uygulama işlevi
def update_macd_strategy():
    global symbol
    # Son 100 kapanış fiyatını al
    klines = client.get_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_15MINUTE,
        limit=100
    )
    close_prices = []
    for kline in klines:
        close_price = float(kline[4])
        close_prices.append(close_price)
    macd_line, signal_line, histogram = calculate_macd(close_prices)
    current_macd = macd_line[-1]
    current_signal = signal_line[-1]
    previous_macd = macd_line[-2]
    previous_signal = signal_line[-2]
    # MACD çizgisi, sinyal çizgisini yukarıdan aşağıya keserse
    if previous_macd > previous_signal and current_macd < current_signal:
        # Tüm açık emirleri iptal et
        cancel_orders()
        # En son fiyattan satın alma limit emri ver
        latest_price = float(klines[-1][4])
        buy_price = latest_price + 0.02 * latest_price  # Fiyatı %2 yükselt
        place_limit_order('buy', buy_price)
    # MACD çizgisi, sinyal çizgisini aşağıdan yukarıya keserse
    elif previous_macd < previous_signal and current_macd > current_signal:
        # Tüm açık emirleri iptal et
        cancel_orders()
        # En son fiyattan satış limit emri ver
        latest_price = float(klines[-1][4])
        sell_price = latest_price - 0.02 * latest_price  # Fiyatı %2 düşür
        place_limit_order('sell', sell_price)

# Fiyat grafiğini güncelleme işlevini düzenli aralıklarla çağırma
def update_price_chart_interval():
    update_price_chart()
    window.after(60000, update_price_chart_interval)  # Her dakikada bir güncelle

# MACD stratejisini düzenli aralıklarla çağırma
def update_macd_strategy_interval():
    update_macd_strategy()
    window.after(60000, update_macd_strategy_interval)  # Her dakikada bir güncelle

# Başlangıçta grafik ve strateji güncellemelerini çağır
update_price_chart()
update_macd_strategy()

# Hesap bakiyesini ve işlem geçmişini yazdır
print("Account Balance:", get_account_balance())
print("Trade History:")
get_trade_history()

# Güncelleme işlevlerini düzenli aralıklarla çağırma
window.after(60000, update_price_chart_interval)
window.after(60000, update_macd_strategy_interval)

# Ana döngüyü başlat
window.mainloop()
