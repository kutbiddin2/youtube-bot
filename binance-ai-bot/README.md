# 🤖 Binance AI Trading Bot

**Hibrit yapay zeka destekli kripto trading botu**

Teknik analiz + duygu analizi + risk yönetimi birleşiminde çalışan, Binance spot piyasasında otomatik alım-satım yapan Python botu.

---

## ⚠️ ÖNEMLİ UYARI

> Bu yazılım **eğitim amaçlıdır**. Kripto para ticareti yüksek risk içerir.
> Kaybetmeyi göze alamayacağınız parayı asla yatırmayın.
> **Önce mutlaka TESTNET'te test edin!**

---

## 🚀 Hızlı Başlangıç (Adım Adım)

### 1. Python Kurulumu
Python 3.10+ gereklidir. [python.org](https://python.org) adresinden indirin.

### 2. Projeyi İndirin
```bash
# Klasörü bilgisayarınıza kopyalayın
cd binance-ai-bot
```

### 3. Gereksinimleri Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Binance Testnet API Anahtarı Alın
1. [testnet.binance.vision](https://testnet.binance.vision/) adresine gidin
2. GitHub hesabınızla giriş yapın
3. "Generate HMAC_SHA256 Key" butonuna tıklayın
4. API Key ve Secret Key'i kopyalayın

### 5. Yapılandırma
`config.py` dosyasını açın ve ayarlayın:

```python
# Testnet anahtarlarınız
USE_TESTNET = True  # Önce True bırakın!
TESTNET_API_KEY = "buraya_testnet_key"
TESTNET_API_SECRET = "buraya_testnet_secret"

# İşlem ayarları
TRADE_AMOUNT_USDT = 10.0  # Küçük başlayın
TRADING_PAIRS = ["BTCUSDT", "ETHUSDT"]
```

### 6. Botu Başlatın

```bash
# Simülasyon modu (emir göndermez, öğrenmek için ideal)
python bot.py --dry-run

# Testnet'te gerçek emirlerle (sahte para)
python bot.py

# Durum raporu
python bot.py --status
```

---

## 📁 Proje Yapısı

```
binance-ai-bot/
├── bot.py                      # Ana bot (başlatma noktası)
├── config.py                   # Tüm ayarlar (bunu düzenleyin)
├── requirements.txt            # Python kütüphaneleri
├── modules/
│   ├── binance_client.py       # Binance API bağlantısı
│   ├── technical_analysis.py   # RSI, MACD, BB, EMA hesaplama
│   ├── sentiment_analyzer.py   # Haber duygu analizi
│   ├── strategy_engine.py      # Sinyalleri birleştiren motor
│   └── risk_manager.py         # Stop-loss, take-profit, limitler
├── trades_history.json         # İşlem geçmişi (otomatik oluşur)
└── bot.log                     # Log dosyası (otomatik oluşur)
```

---

## 🧠 Bot Nasıl Çalışır?

### Sinyal Üretimi (Her döngüde)

1. **Teknik Analiz (%80 ağırlık)**
   - RSI: Aşırı alım/satım tespiti
   - MACD: Trend yönü ve momentum
   - Bollinger Bands: Volatilite ve fiyat konumu
   - EMA Crossover: Trend değişimi (Golden/Death Cross)
   - Hacim Analizi: İşlem hacmi anomalileri

2. **Duygu Analizi (%20 ağırlık)**
   - Haber başlıklarından otomatik duygu tespiti
   - OpenAI varsa: LLM ile gelişmiş analiz
   - Yoksa: Anahtar kelime tabanlı analiz

3. **Birleşik Skor**
   - Tüm sinyaller -1 ile +1 arasında normalize edilir
   - Ağırlıklı ortalama hesaplanır
   - Güvenilirlik skoru oluşturulur
   - Skor > +0.25 ve güven > %60 → AL
   - Skor < -0.25 ve güven > %60 → SAT
   - Aksi halde → BEKLE

### Risk Yönetimi (Sürekli)

- **Stop-Loss**: Zarar %2'yi geçerse otomatik sat
- **Take-Profit**: Kâr %3'e ulaşırsa otomatik sat
- **Trailing Stop**: Fiyat zirveden %1.5 düşerse sat
- **Günlük Limit**: Toplam zarar %5'i geçerse dur
- **Pozisyon Limiti**: Aynı anda max 3 açık pozisyon

---

## ⚙️ Ayarlar Rehberi

### Muhafazakâr (Düşük Risk)
```python
STOP_LOSS_PERCENT = 1.5
TAKE_PROFIT_PERCENT = 2.0
MIN_SIGNAL_CONFIDENCE = 0.7
MAX_OPEN_POSITIONS = 2
SCAN_INTERVAL_SECONDS = 300  # 5 dakika
```

### Dengeli (Orta Risk)
```python
STOP_LOSS_PERCENT = 2.0
TAKE_PROFIT_PERCENT = 3.0
MIN_SIGNAL_CONFIDENCE = 0.6
MAX_OPEN_POSITIONS = 3
SCAN_INTERVAL_SECONDS = 60  # 1 dakika
```

### Agresif (Yüksek Risk) ⚠️
```python
STOP_LOSS_PERCENT = 3.0
TAKE_PROFIT_PERCENT = 5.0
MIN_SIGNAL_CONFIDENCE = 0.5
MAX_OPEN_POSITIONS = 5
SCAN_INTERVAL_SECONDS = 30  # 30 saniye
```

---

## 📱 Telegram Bildirimi (Opsiyonel)

1. Telegram'da @BotFather'a `/newbot` yazın
2. Bot adı verin, token'ı kopyalayın
3. @userinfobot'a yazarak chat ID'nizi öğrenin
4. `config.py`'da ilgili alanları doldurun

---

## 🔒 Güvenlik Kuralları

1. API anahtarına **ASLA çekim izni vermeyin**
2. IP kısıtlaması ekleyin (Binance API ayarları)
3. API anahtarlarını `.env` dosyasına taşıyın (prodüksiyon için)
4. Düzenli olarak anahtarları yenileyin
5. Botun çalıştığı sistemi güvende tutun

---

## 🐛 Sık Karşılaşılan Sorunlar

**"python-binance kütüphanesi gerekli"**
→ `pip install python-binance` çalıştırın

**"API key hatası"**
→ config.py'daki anahtarları kontrol edin, testnet/gerçek karıştırmayın

**"Yetersiz bakiye"**
→ Testnet'te bakiye almak için faucet kullanın

**"Filter failure: MIN_NOTIONAL"**
→ TRADE_AMOUNT_USDT değerini artırın (min 10 USDT)

---

## 📜 Lisans ve Sorumluluk Reddi

Bu proje eğitim amaçlıdır. Yatırım tavsiyesi değildir.
Kripto para ticareti yüksek risk içerir ve sermayenizin
tamamını kaybedebilirsiniz. Gerçek parayla kullanım
tamamen kendi sorumluluğunuzdadır.
