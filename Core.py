import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import datetime
from binance.client import Client
from binance.enums import *
import numpy as np
import time

# Binance API kimlik bilgileri
api_key = 'wDlvMXEY27d35HaK5Unpcvu6faqbIZF5Mr4BHQgThyOJnjHHSTwycJNwPxDSc8ov'
api_secret = '3bGsXy3UAmAsPXcBQ71ndWOKloFZfau5GAXcjyKelMrSvvxXpOVbaDMQyfId1qTm'

# Binance API istemci bağlantısı
client = Client(api_key, api_secret)

print('API başlatıldı. Bağlantı kuruldu...')

# İşlem çifti
symbol = 'RNDRBUSD'

max_kullanilabilir_bakiye = 15

# Ana uygulama penceresini başlat
window = tk.Tk()
window.title("Binance-Bot")
window.geometry("800x600")

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
    symbol = 'RNDRBUSD'
    quantity = 1  # İstenilen miktarı ayarlayın
    price = None  # İstediğiniz fiyatı ayarlayın (isteğe bağlı)
    
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

# Fiyat tablosunu güncelleme işlevi
def update_price_chart():
    symbol = 'RNDRBUSD'
    kline_data = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=100)
    
    timestamps = [datetime.datetime.fromtimestamp(entry[0] / 1000) for entry in kline_data]
    close_prices = [float(entry[4]) for entry in kline_data]
    
    price_axes.cla()
    price_axes.plot(timestamps, close_prices)
    price_axes.xaxis.set_major_locator(mdates.AutoDateLocator())
    price_axes.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    price_axes.set_ylabel('Price')
    price_axes.set_title('Price Chart')
    price_canvas.draw()

def update_charts():
    update_price_chart()
    window.after(5000, update_charts) 

update_charts()

window.mainloop()

# Zero Lag MACD parametreleri
hizli_uzunluk = 12
yavas_uzunluk = 26
sinyal_uzunluk = 12
macd_ema_uzunluk = 12
ema_kullan = True
eski_algoritma_kullan = False

# Üssel Hareketli Ortalama (EMA)
def ema(degerler, periyot):
    agirliklar = np.exp(np.linspace(-1., 0., periyot))
    agirliklar /= agirliklar.sum()
    ema = np.convolve(degerler, agirliklar, mode='full')[:len(degerler)]
    return ema

# Basit Hareketli Ortalama (SMA)
def sma(degerler, periyot):
    sma = np.convolve(degerler, np.ones((periyot,))/periyot, mode='valid')
    return sma

# Zero Lag MACD indikatörünü hesapla
def zerolag_macd_hesapla(kline_verileri):
    kapanis_fiyatlari = np.array([float(kline[4]) for kline in kline_verileri])

    ma1 = ema(kapanis_fiyatlari, hizli_uzunluk) if ema_kullan else sma(kapanis_fiyatlari, hizli_uzunluk)
    ma2 = ema(ma1, hizli_uzunluk) if ema_kullan else sma(ma1, hizli_uzunluk)
    zerolag_ema = (2 * ma1) - ma2

    mas1 = ema(kapanis_fiyatlari, yavas_uzunluk) if ema_kullan else sma(kapanis_fiyatlari, yavas_uzunluk)
    mas2 = ema(mas1, yavas_uzunluk) if ema_kullan else sma(mas1, yavas_uzunluk)
    zerolag_yavas_ma = (2 * mas1) - mas2

    zerolag_macd = zerolag_ema - zerolag_yavas_ma

    emasig1 = ema(zerolag_macd, sinyal_uzunluk)
    emasig2 = ema(emasig1, sinyal_uzunluk)
    sinyal = sma(zerolag_macd, sinyal_uzunluk) if eski_algoritma_kullan else (2 * emasig1) - emasig2

    hist = zerolag_macd - sinyal

    return zerolag_macd, sinyal, hist

# Geçmiş kline verilerini al
def gecmis_kline_verilerini_al(zaman_araligi):
    kline_verileri = client.get_historical_klines(symbol, zaman_araligi, "1 gün önce UTC")
    return kline_verileri

# Hesap bakiyesini al
def bakiye_al(varlik, max_bakiye=None):
    bakiye = client.get_asset_balance(asset=varlik)
    serbest_bakiye = float(bakiye['free'])
    if max_bakiye is not None and serbest_bakiye > max_bakiye:
        serbest_bakiye = max_bakiye
    print(f"{varlik} bakiye: {serbest_bakiye}")
    return serbest_bakiye

# Limitli alış emri yerleştir
def limitli_alis_emri(yogunluk, fiyat):
    emir = client.create_order(
        symbol=symbol,
        side=SIDE_BUY,
        type=ORDER_TYPE_LIMIT,
        timeInForce=TIME_IN_FORCE_GTC,
        quantity=yogunluk,
        price=fiyat)
    print(f"Limitli alış emri yerleştirildi. Miktar: {yogunluk}, Fiyat: {fiyat}")
    return emir['orderId']

# Limitli satış emri yerleştir
def limitli_satis_emri(yogunluk, fiyat):
    emir = client.create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=ORDER_TYPE_LIMIT,
        timeInForce=TIME_IN_FORCE_GTC,
        quantity=yogunluk,
        price=fiyat)
    print(f"Limitli satış emri yerleştirildi. Miktar: {yogunluk}, Fiyat: {fiyat}")
    return emir['orderId']

# OCO satış emri yerleştir
def oco_satis_emri(stop_fiyati, limit_fiyati, yogunluk):
    emir = client.order_oco_sell(
        symbol=symbol,
        stopLimitTimeInForce=TIME_IN_FORCE_GTC,
        stopPrice=stop_fiyati,
        price=limit_fiyati,
        quantity=yogunluk)
    print(f"OCO satış emri yerleştirildi. Stop Fiyatı: {stop_fiyati}, Limit Fiyatı: {limit_fiyati}, Miktar: {yogunluk}")
    return emir['orderId']

# Tüm açık emirleri iptal et
def emirleri_iptal_et():
    emirler = client.get_open_orders(symbol=symbol)
    for emir in emirler:
        client.cancel_order(symbol=symbol, orderId=emir['orderId'])
    print("Tüm açık emirler iptal edildi.")

# Cüzdan bakiyelerini al
def cüzdan_bakiyelerini_al():
    bakiyeler = client.get_account()['balances']
    return {bakiye['asset']: float(bakiye['free']) for bakiye in bakiyeler}

# OCO emir durumunu kontrol et
def oco_emir_durumunu_kontrol_et(emir_id):
    emir = client.get_order(symbol=symbol, orderId=emir_id)
    return emir['status']

print('Ana nesne başlatıldı...')

# Ana işlem döngüsü
oco_emir_id = None
islem_aktif = False
while True:
    try:
        # Geçmiş kline verilerini al
        kline_verileri = gecmis_kline_verilerini_al(Client.KLINE_INTERVAL_1MINUTE)

        # Zero Lag MACD hesapla
        macd, sinyal, hist = zerolag_macd_hesapla(kline_verileri)
        
        np.shape(macd)

        if hist[-1] > 0 and macd[-1] > sinyal[-1] and hist[-2] < 0 and macd[-2] < sinyal[-2] and islem_aktif == False:
            # Alış emri yerleştir
            print("Alım")
            bakiye = bakiye_al('BUSD', max_kullanilabilir_bakiye)
            alis_miktari = bakiye / float(kline_verileri[-1][4])
            emir_id = limitli_alis_emri(alis_miktari, float(kline_verileri[-1][4]))
            
            time.sleep(3)

            # OCO satış emri yerleştir
            satis_durdur_fiyati = float(kline_verileri[-1][4]) * 0.98
            satis_limit_fiyati = float(kline_verileri[-1][4]) * 1.02
            oco_emir_id = oco_satis_emri(satis_durdur_fiyati, satis_limit_fiyati, alis_miktari)
            time.sleep(3)
            islem_aktif = True

        if hist[-1] < 0 and macd[-1] < sinyal[-1] and hist[-2] > 0 and macd[-2] > sinyal[-2] and islem_aktif:
            # Tüm açık emirleri iptal et
            emirleri_iptal_et()
            print("Satım")
            
            time.sleep(3)

            # Satış emri yerleştir
            bakiye = bakiye_al('RNDR')
            satis_miktari = bakiye
            satis_limit_fiyati = float(kline_verileri[-1][4]) * 0.98
            limitli_satis_emri(satis_miktari, satis_limit_fiyati)
            time.sleep(3)
            islem_aktif = False

        if oco_emir_id and oco_emir_durumunu_kontrol_et(oco_emir_id) == 'FILLED':
            # Emir ID'lerini sıfırla
            print("OCO")
            oco_emir_id = None
            islem_aktif = False

        # 60 saniye bekleyin
        mevcut_fiyat = float(kline_verileri[-1][4])
        print(f"Tarih Saat: {time.strftime('%Y-%m-%d %H:%M:%S')} Mevcut Fiyat: {mevcut_fiyat}", end="\r")
        time.sleep(5)

    except Exception as e:
        print(f"Bir hata oluştu: {e}")
        time.sleep(5)
