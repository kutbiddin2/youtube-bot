# 🎬 Alternatif Tarih Video Botu — Kurulum Rehberi

## 📋 Gereksinimler
- Python 3.9+
- Gemini API Key (ücretsiz)
- İnternet bağlantısı

---

## 🚀 Adım Adım Kurulum

### 1. Python Kütüphanelerini Kur
```bash
pip install google-generativeai edge-tts moviepy pillow
```

> MoviePy için ayrıca **FFmpeg** gerekli:
> - **Windows:** https://ffmpeg.org/download.html → PATH'e ekle
> - **Mac:** `brew install ffmpeg`
> - **Linux:** `sudo apt install ffmpeg`

---

### 2. API Key'i Ayarla
`alternatif_tarih_bot.py` dosyasını aç, şu satırı bul:
```python
GEMINI_API_KEY = "BURAYA_API_KEYINI_YAZ"
```
Kendi API key'inle değiştir.

---

### 3. Müzik Dosyasını Ekle
- YouTube Ses Kitaplığı'ndan epik/tarihi bir müzik indir
- `muzik.mp3` adıyla bot dosyasının yanına koy
- (Müzik yoksa bot yine de çalışır, müziksiz video üretir)

---

### 4. Çalıştır!
```bash
python alternatif_tarih_bot.py
```

---

## ⚙️ Özelleştirme

### Otomatik konu seçimi (varsayılan):
```python
main()
```

### Kendi konunu belirt:
```python
main("Osmanlı Sanayi Devrimini Başlatsaydı Ne Olurdu?")
```

### Sesi değiştir:
```python
TTS_SES = "tr-TR-AhmetNeural"   # Erkek
TTS_SES = "tr-TR-EmelNeural"    # Kadın
```

---

## 📁 Çıktı Klasör Yapısı
```
videolar/
├── Video_Basligi.mp4          ← Final video
└── Video_Basligi/
    ├── gorsel_01.png
    ├── gorsel_02.png
    ├── ...
    └── anlatim.mp3
```

---

## ❓ Sık Sorulan Sorular

**Imagen API çalışmıyor?**
Bot otomatik olarak yedek görsel sisteme geçer (koyu arka plan + metin). 
Imagen API henüz tüm hesaplarda aktif olmayabilir.

**Video çok kısa çıkıyor?**
Script'in kelime sayısını artır. `script_uret()` fonksiyonundaki promptta
"En az 1200 kelime" yaz.

**Altyazı görünmüyor?**
`imagemagick` kurulu olduğundan emin ol:
- Windows: https://imagemagick.org/script/download.php
- Linux: `sudo apt install imagemagick`
