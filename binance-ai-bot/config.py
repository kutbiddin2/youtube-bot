"""
╔══════════════════════════════════════════════════════════════╗
║           BINANCE AI TRADING BOT - YAPILANDIRMA             ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── BINANCE API ──
BINANCE_API_KEY = ""
BINANCE_API_SECRET = ""
USE_TESTNET = True
TESTNET_API_KEY = ""
TESTNET_API_SECRET = ""

# ── COIN LİSTESİ ──
TRADING_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT",
    "DOGEUSDT", "SHIBUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT",
    "APTUSDT", "OPUSDT", "ARBUSDT", "SUIUSDT", "PEPEUSDT",
]

# ── İŞLEM AYARLARI (YÜZDE BAZLI) ──
MAX_OPEN_POSITIONS = 8          # Aynı anda en fazla 8 farklı coin
COIN_MAX_PERCENT = 10           # Bakiyenin en fazla %10'u bir coine gider (1000$ → max 100$)
MAX_BUYS_PER_COIN = 10           # Aynı coine en fazla 5 kez alım
SMART_ROTATION = True           # Daha iyi fırsat gelince en kötüyü sat, yenisini al
SCAN_INTERVAL_SECONDS = 90

# ── AI / DUYGU ANALİZİ ──
AI_PROVIDER = "gemini"
GEMINI_API_KEY = ""
CLAUDE_API_KEY = ""
SENTIMENT_WEIGHT = 0.2

# ── TEKNİK ANALİZ ──
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD_DEV = 2.0
EMA_SHORT = 9
EMA_LONG = 21
KLINE_INTERVAL = "15m"
KLINE_LIMIT = 100

# ── RİSK YÖNETİMİ ──
STOP_LOSS_PERCENT = 2.5
TAKE_PROFIT_PERCENT = 4.0
USE_TRAILING_STOP = True
TRAILING_STOP_PERCENT = 1.5
MAX_DAILY_LOSS_PERCENT = 8.0
MAX_DAILY_TRADES = 60
MIN_SIGNAL_CONFIDENCE = 0.30

# ── TELEGRAM ──
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# ── DEPOLAMA ──
LOG_LEVEL = "INFO"
TRADES_LOG_FILE = "trades_history.json"

# ── ANAHTARLARI YÜKLE ──
try:
    from my_keys import *
    print("🔑 Anahtarlar my_keys.py'dan yüklendi!")
except ImportError:
    print("⚠️ my_keys.py bulunamadı")
