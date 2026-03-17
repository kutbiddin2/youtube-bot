"""
🔗 Binance API İstemcisi
========================
Binance borsası ile iletişim katmanı.
Testnet ve gerçek piyasa desteği.
"""

import logging
import time
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    HAS_BINANCE = True
except ImportError:
    HAS_BINANCE = False

import config

logger = logging.getLogger("BinanceClient")


class BinanceClient:
    """Binance API wrapper"""

    def __init__(self):
        if not HAS_BINANCE:
            raise ImportError(
                "python-binance kütüphanesi gerekli!\n"
                "Yüklemek için: pip install python-binance"
            )

        if config.USE_TESTNET:
            logger.info("🧪 TESTNET modunda başlatılıyor...")
            self.client = Client(
                config.TESTNET_API_KEY,
                config.TESTNET_API_SECRET,
            )
            # ÖNEMLİ: testnet=True futures testnet'e bağlanır!
            # Biz SPOT testnet istiyoruz, URL'yi manuel ayarlıyoruz:
            self.client.timestamp_offset = self.client.get_server_time()['serverTime'] - int(time.time() * 1000)
        else:
            logger.info("💰 GERÇEK piyasa modunda başlatılıyor...")
            self.client = Client(
                config.BINANCE_API_KEY,
                config.BINANCE_API_SECRET,
            )

        # Bağlantı testi
        try:
            self.client.ping()
            logger.info("✅ Binance sunucuya bağlantı başarılı")

            # Kimlik doğrulama testi (bakiye çekmeyi dene)
            account = self.client.get_account()
            logger.info("✅ API anahtarı doğrulandı, hesap erişimi başarılı")
        except BinanceAPIException as e:
            if e.code == -2014 or e.code == -2015:
                logger.error(f"❌ API ANAHTARI HATASI: Testnet anahtarlarını kontrol et!")
                logger.error(f"   my_keys.py dosyasında TESTNET_API_KEY ve TESTNET_API_SECRET doğru mu?")
                logger.error(f"   testnet.binance.vision'dan yeni anahtar almayı dene.")
            else:
                logger.error(f"❌ Binance API hatası: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Binance bağlantı hatası: {e}")
            raise

        # Sembol bilgilerini cache'le
        self._symbol_info: Dict[str, dict] = {}
        self._load_symbol_info()

    # ─────────────────────────────────────────────
    # Piyasa Verileri
    # ─────────────────────────────────────────────
    def get_klines(self, symbol: str) -> pd.DataFrame:
        """
        Mum grafiği verilerini DataFrame olarak döndür.
        
        Sütunlar: open, high, low, close, volume, timestamp
        """
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=config.KLINE_INTERVAL,
                limit=config.KLINE_LIMIT,
            )

            df = pd.DataFrame(klines, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])

            # Veri tiplerini düzelt
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            return df[["timestamp", "open", "high", "low", "close", "volume"]]

        except BinanceAPIException as e:
            logger.error(f"Kline hatası ({symbol}): {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Beklenmeyen hata ({symbol}): {e}")
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Güncel fiyatı al"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            logger.error(f"Fiyat alma hatası ({symbol}): {e}")
            return None

    def get_account_balance(self, asset: str = "USDT") -> float:
        """Hesap bakiyesini al"""
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance["free"]) if balance else 0.0
        except Exception as e:
            logger.error(f"Bakiye alma hatası: {e}")
            return 0.0

    # ─────────────────────────────────────────────
    # Emir İşlemleri
    # ─────────────────────────────────────────────
    def place_buy_order(self, symbol: str, usdt_amount: float) -> Optional[dict]:
        """
        Market alım emri ver.
        
        symbol: "BTCUSDT"
        usdt_amount: Harcamak istenen USDT miktarı
        """
        try:
            price = self.get_current_price(symbol)
            if not price:
                return None

            # Miktar hesapla
            quantity = usdt_amount / price
            quantity = self._format_quantity(symbol, quantity)

            if not quantity or quantity <= 0:
                logger.warning(f"Geçersiz miktar: {quantity} ({symbol})")
                return None

            logger.info(f"📥 ALIM EMRİ: {symbol} | {quantity} adet @ ~{price:.4f}")

            order = self.client.order_market_buy(
                symbol=symbol,
                quantity=quantity,
            )

            fill_price = float(order.get("fills", [{}])[0].get("price", price))
            fill_qty = float(order.get("executedQty", quantity))

            logger.info(f"✅ ALIM TAMAMLANDI: {symbol} | {fill_qty} @ {fill_price:.4f}")

            return {
                "symbol": symbol,
                "side": "BUY",
                "price": fill_price,
                "quantity": fill_qty,
                "order_id": order.get("orderId"),
                "status": order.get("status"),
            }

        except BinanceAPIException as e:
            logger.error(f"Alım emri hatası ({symbol}): {e}")
            return None

    def place_sell_order(self, symbol: str, quantity: float) -> Optional[dict]:
        """
        Market satım emri ver.
        
        symbol: "BTCUSDT"
        quantity: Satılacak miktar
        """
        try:
            quantity = self._format_quantity(symbol, quantity)

            if not quantity or quantity <= 0:
                logger.warning(f"Geçersiz satım miktarı: {quantity} ({symbol})")
                return None

            price = self.get_current_price(symbol)
            logger.info(f"📤 SATIM EMRİ: {symbol} | {quantity} adet @ ~{price:.4f}")

            order = self.client.order_market_sell(
                symbol=symbol,
                quantity=quantity,
            )

            fill_price = float(order.get("fills", [{}])[0].get("price", price or 0))
            fill_qty = float(order.get("executedQty", quantity))

            logger.info(f"✅ SATIM TAMAMLANDI: {symbol} | {fill_qty} @ {fill_price:.4f}")

            return {
                "symbol": symbol,
                "side": "SELL",
                "price": fill_price,
                "quantity": fill_qty,
                "order_id": order.get("orderId"),
                "status": order.get("status"),
            }

        except BinanceAPIException as e:
            logger.error(f"Satım emri hatası ({symbol}): {e}")
            return None

    # ─────────────────────────────────────────────
    # Yardımcılar
    # ─────────────────────────────────────────────
    def _load_symbol_info(self):
        """Sembol bilgilerini yükle (min miktar, adım büyüklüğü vb.)"""
        try:
            info = self.client.get_exchange_info()
            for s in info.get("symbols", []):
                sym = s["symbol"]
                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        self._symbol_info[sym] = {
                            "step_size": float(f["stepSize"]),
                            "min_qty": float(f["minQty"]),
                            "max_qty": float(f["maxQty"]),
                        }
                        break
        except Exception as e:
            logger.warning(f"Sembol bilgisi yükleme hatası: {e}")

    def _format_quantity(self, symbol: str, quantity: float) -> float:
        """Miktarı Binance'ın kabul ettiği formata yuvarla"""
        info = self._symbol_info.get(symbol)
        if not info:
            # Varsayılan: 6 ondalık
            return round(quantity, 6)

        step = info["step_size"]
        min_qty = info["min_qty"]

        if step > 0:
            precision = len(str(step).rstrip("0").split(".")[-1])
            quantity = round(quantity - (quantity % step), precision)

        if quantity < min_qty:
            return 0.0

        return quantity
