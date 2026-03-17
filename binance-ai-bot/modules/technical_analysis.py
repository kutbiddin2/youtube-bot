"""
📊 Teknik Analiz Modülü
========================
RSI, MACD, Bollinger Bands, EMA hesaplamaları
Her gösterge -1 (sat) ile +1 (al) arasında sinyal üretir
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
import config


@dataclass
class TechnicalSignal:
    """Teknik analiz sinyali"""
    indicator: str       # Gösterge adı
    signal: float        # -1.0 (güçlü sat) ... +1.0 (güçlü al)
    value: float         # Göstergenin mevcut değeri
    description: str     # Türkçe açıklama


class TechnicalAnalyzer:
    """Teknik göstergeleri hesaplayan ana sınıf"""

    def __init__(self):
        self.rsi_period = config.RSI_PERIOD
        self.macd_fast = config.MACD_FAST
        self.macd_slow = config.MACD_SLOW
        self.macd_signal = config.MACD_SIGNAL
        self.bb_period = config.BB_PERIOD
        self.bb_std = config.BB_STD_DEV
        self.ema_short = config.EMA_SHORT
        self.ema_long = config.EMA_LONG

    def analyze(self, df: pd.DataFrame) -> List[TechnicalSignal]:
        """
        Tüm teknik göstergeleri hesapla ve sinyalleri döndür.
        
        df: OHLCV DataFrame (open, high, low, close, volume sütunları)
        """
        signals = []

        close = df["close"].astype(float)

        # 1. RSI
        rsi_signal = self._calculate_rsi(close)
        if rsi_signal:
            signals.append(rsi_signal)

        # 2. MACD
        macd_signal = self._calculate_macd(close)
        if macd_signal:
            signals.append(macd_signal)

        # 3. Bollinger Bands
        bb_signal = self._calculate_bollinger(close)
        if bb_signal:
            signals.append(bb_signal)

        # 4. EMA Crossover
        ema_signal = self._calculate_ema_crossover(close)
        if ema_signal:
            signals.append(ema_signal)

        # 5. Hacim Analizi
        if "volume" in df.columns:
            vol_signal = self._analyze_volume(df)
            if vol_signal:
                signals.append(vol_signal)

        return signals

    def get_combined_score(self, signals: List[TechnicalSignal]) -> float:
        """
        Tüm sinyalleri birleştirerek -1 ile +1 arasında toplam skor üret.
        Ağırlıklar: RSI=%30, MACD=%25, BB=%20, EMA=%15, Hacim=%10
        """
        weights = {
            "RSI": 0.30,
            "MACD": 0.25,
            "Bollinger Bands": 0.20,
            "EMA Crossover": 0.15,
            "Hacim": 0.10,
        }

        total_weight = 0
        weighted_sum = 0

        for sig in signals:
            w = weights.get(sig.indicator, 0.1)
            weighted_sum += sig.signal * w
            total_weight += w

        if total_weight == 0:
            return 0.0

        return round(weighted_sum / total_weight, 4)

    # ─────────────────────────────────────────────
    # RSI (Relative Strength Index)
    # ─────────────────────────────────────────────
    def _calculate_rsi(self, close: pd.Series) -> Optional[TechnicalSignal]:
        """
        RSI < 30 → Aşırı satım (alım fırsatı)
        RSI > 70 → Aşırı alım (satım fırsatı)
        """
        if len(close) < self.rsi_period + 1:
            return None

        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]

        if np.isnan(current_rsi):
            return None

        # Sinyal hesapla
        if current_rsi <= config.RSI_OVERSOLD:
            signal = 0.5 + (config.RSI_OVERSOLD - current_rsi) / (config.RSI_OVERSOLD * 2)
            signal = min(signal, 1.0)
            desc = f"RSI={current_rsi:.1f} → Aşırı satım bölgesi (ALIM sinyali)"
        elif current_rsi >= config.RSI_OVERBOUGHT:
            signal = -0.5 - (current_rsi - config.RSI_OVERBOUGHT) / ((100 - config.RSI_OVERBOUGHT) * 2)
            signal = max(signal, -1.0)
            desc = f"RSI={current_rsi:.1f} → Aşırı alım bölgesi (SATIM sinyali)"
        else:
            # Nötr bölge, hafif yönlendirme
            signal = (50 - current_rsi) / 100
            desc = f"RSI={current_rsi:.1f} → Nötr bölge"

        return TechnicalSignal("RSI", round(signal, 4), round(current_rsi, 2), desc)

    # ─────────────────────────────────────────────
    # MACD (Moving Average Convergence Divergence)
    # ─────────────────────────────────────────────
    def _calculate_macd(self, close: pd.Series) -> Optional[TechnicalSignal]:
        """
        MACD çizgisi sinyal çizgisini yukarı keserse → ALIM
        MACD çizgisi sinyal çizgisini aşağı keserse → SATIM
        """
        if len(close) < self.macd_slow + self.macd_signal:
            return None

        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line

        current_hist = histogram.iloc[-1]
        prev_hist = histogram.iloc[-2]

        if np.isnan(current_hist) or np.isnan(prev_hist):
            return None

        # Histogram yönü ve büyüklüğü
        # Normalize et (fiyata göre)
        price = close.iloc[-1]
        norm_hist = current_hist / price * 100 if price > 0 else 0

        if current_hist > 0 and prev_hist <= 0:
            signal = 0.8  # Güçlü alım (yukarı kesiş)
            desc = "MACD yukarı kesişim → Güçlü ALIM sinyali"
        elif current_hist < 0 and prev_hist >= 0:
            signal = -0.8  # Güçlü satım (aşağı kesiş)
            desc = "MACD aşağı kesişim → Güçlü SATIM sinyali"
        elif current_hist > 0:
            signal = min(norm_hist * 2, 0.6)
            desc = f"MACD pozitif bölge → Yükseliş devam ediyor"
        else:
            signal = max(norm_hist * 2, -0.6)
            desc = f"MACD negatif bölge → Düşüş devam ediyor"

        return TechnicalSignal("MACD", round(signal, 4), round(current_hist, 6), desc)

    # ─────────────────────────────────────────────
    # Bollinger Bands
    # ─────────────────────────────────────────────
    def _calculate_bollinger(self, close: pd.Series) -> Optional[TechnicalSignal]:
        """
        Fiyat alt banda yakınsa → Alım fırsatı
        Fiyat üst banda yakınsa → Satım fırsatı
        """
        if len(close) < self.bb_period:
            return None

        sma = close.rolling(window=self.bb_period).mean()
        std = close.rolling(window=self.bb_period).std()

        upper = sma + self.bb_std * std
        lower = sma - self.bb_std * std

        current_price = close.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        current_sma = sma.iloc[-1]

        if np.isnan(current_upper) or np.isnan(current_lower):
            return None

        band_width = current_upper - current_lower
        if band_width == 0:
            return None

        # Fiyatın bant içindeki pozisyonu (0=alt bant, 1=üst bant)
        position = (current_price - current_lower) / band_width

        if position <= 0.1:
            signal = 0.8
            desc = f"Fiyat alt Bollinger bandının altında → Güçlü ALIM"
        elif position <= 0.3:
            signal = 0.4
            desc = f"Fiyat alt Bollinger bandına yakın → ALIM sinyali"
        elif position >= 0.9:
            signal = -0.8
            desc = f"Fiyat üst Bollinger bandının üstünde → Güçlü SATIM"
        elif position >= 0.7:
            signal = -0.4
            desc = f"Fiyat üst Bollinger bandına yakın → SATIM sinyali"
        else:
            signal = (0.5 - position) * 0.4
            desc = f"Fiyat Bollinger bantları ortasında → Nötr"

        return TechnicalSignal("Bollinger Bands", round(signal, 4), round(position, 4), desc)

    # ─────────────────────────────────────────────
    # EMA Crossover
    # ─────────────────────────────────────────────
    def _calculate_ema_crossover(self, close: pd.Series) -> Optional[TechnicalSignal]:
        """
        Kısa EMA uzun EMA'yı yukarı keserse → ALIM (Golden Cross)
        Kısa EMA uzun EMA'yı aşağı keserse → SATIM (Death Cross)
        """
        if len(close) < self.ema_long + 2:
            return None

        ema_short = close.ewm(span=self.ema_short, adjust=False).mean()
        ema_long = close.ewm(span=self.ema_long, adjust=False).mean()

        current_diff = ema_short.iloc[-1] - ema_long.iloc[-1]
        prev_diff = ema_short.iloc[-2] - ema_long.iloc[-2]

        price = close.iloc[-1]
        norm_diff = current_diff / price * 100 if price > 0 else 0

        if current_diff > 0 and prev_diff <= 0:
            signal = 0.7
            desc = "EMA Golden Cross → ALIM sinyali"
        elif current_diff < 0 and prev_diff >= 0:
            signal = -0.7
            desc = "EMA Death Cross → SATIM sinyali"
        elif current_diff > 0:
            signal = min(norm_diff * 3, 0.5)
            desc = f"Kısa EMA uzun EMA üstünde → Yükseliş trendi"
        else:
            signal = max(norm_diff * 3, -0.5)
            desc = f"Kısa EMA uzun EMA altında → Düşüş trendi"

        return TechnicalSignal("EMA Crossover", round(signal, 4), round(norm_diff, 4), desc)

    # ─────────────────────────────────────────────
    # Hacim Analizi
    # ─────────────────────────────────────────────
    def _analyze_volume(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """
        Hacim ortalamanın üstündeyse ve fiyat yükseliyorsa → güçlü ALIM
        Hacim ortalamanın üstündeyse ve fiyat düşüyorsa → güçlü SATIM
        """
        if len(df) < 20:
            return None

        volume = df["volume"].astype(float)
        close = df["close"].astype(float)

        avg_volume = volume.rolling(20).mean().iloc[-1]
        current_volume = volume.iloc[-1]

        if np.isnan(avg_volume) or avg_volume == 0:
            return None

        volume_ratio = current_volume / avg_volume
        price_change = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]

        if volume_ratio > 1.5 and price_change > 0:
            signal = min(0.3 + volume_ratio * 0.1, 0.7)
            desc = f"Yüksek hacimle yükseliş (hacim {volume_ratio:.1f}x ortalama)"
        elif volume_ratio > 1.5 and price_change < 0:
            signal = max(-0.3 - volume_ratio * 0.1, -0.7)
            desc = f"Yüksek hacimle düşüş (hacim {volume_ratio:.1f}x ortalama)"
        else:
            signal = 0.0
            desc = f"Normal hacim (hacim {volume_ratio:.1f}x ortalama)"

        return TechnicalSignal("Hacim", round(signal, 4), round(volume_ratio, 2), desc)
