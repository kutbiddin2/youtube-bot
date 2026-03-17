"""
🧠 Duygu Analizi Modülü
========================
Haber başlıklarından piyasa duyarlılığı analizi.
- Gemini API varsa: Google Gemini ile analiz
- Claude API varsa: Anthropic Claude ile analiz
- Yoksa: Anahtar kelime tabanlı basit analiz (ücretsiz)
"""

import re
import json
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import config

logger = logging.getLogger("SentimentAnalyzer")


@dataclass
class SentimentResult:
    """Duygu analizi sonucu"""
    score: float         # -1.0 (çok olumsuz) ... +1.0 (çok olumlu)
    confidence: float    # 0.0 - 1.0 güvenilirlik
    source: str          # Kaynak (gemini, claude, keywords)
    summary: str         # Türkçe özet
    headlines: List[str] # Analiz edilen başlıklar


# ─────────────────────────────────────────────
# Anahtar Kelime Sözlüğü (AI olmadan da çalışır)
# ─────────────────────────────────────────────

BULLISH_KEYWORDS = {
    "rally": 2, "surge": 2, "soar": 2, "breakout": 2,
    "all-time high": 2, "ath": 2, "moon": 2, "pump": 2,
    "bull run": 2, "massive gain": 2, "skyrocket": 2,
    "bullish": 1, "buy": 1, "gain": 1, "rise": 1,
    "up": 1, "growth": 1, "recover": 1, "support": 1,
    "accumulate": 1, "adoption": 1, "upgrade": 1,
    "partnership": 1, "approval": 1, "institutional": 1,
    "etf": 1, "positive": 1, "optimistic": 1,
    "halving": 1, "demand": 1,
}

BEARISH_KEYWORDS = {
    "crash": 2, "plunge": 2, "collapse": 2, "dump": 2,
    "liquidation": 2, "hack": 2, "scam": 2, "fraud": 2,
    "ban": 2, "shut down": 2, "ponzi": 2,
    "bearish": 1, "sell": 1, "drop": 1, "fall": 1,
    "decline": 1, "down": 1, "loss": 1, "fear": 1,
    "risk": 1, "regulation": 1, "lawsuit": 1,
    "investigation": 1, "warning": 1, "bubble": 1,
    "resistance": 1, "correction": 1, "uncertainty": 1,
}


class SentimentAnalyzer:
    """Haber ve sosyal medya duygu analizi"""

    def __init__(self):
        self.provider = config.AI_PROVIDER.lower()
        self._cache = {}
        self._cache_ttl = 300  # 5 dakika cache
        self._last_api_call = 0  # Son API çağrısı zamanı
        self._api_min_interval = 8  # API çağrıları arası minimum 8 saniye (429 hatası önlemi)

        if self.provider == "gemini" and config.GEMINI_API_KEY and config.GEMINI_API_KEY != "BURAYA_GEMINI_API_KEY":
            logger.info("🧠 Duygu analizi: Google Gemini aktif")
        elif self.provider == "claude" and config.CLAUDE_API_KEY:
            logger.info("🧠 Duygu analizi: Anthropic Claude aktif")
        else:
            logger.info("🧠 Duygu analizi: Anahtar kelime modu (ücretsiz)")
            self.provider = "none"

    def analyze(self, symbol: str) -> SentimentResult:
        """Belirli bir coin için duygu analizi yap."""
        cache_key = f"{symbol}_{int(time.time() // self._cache_ttl)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        coin = symbol.replace("USDT", "").replace("BUSD", "")
        headlines = self._fetch_headlines(coin)

        if not headlines:
            result = SentimentResult(
                score=0.0, confidence=0.1, source="none",
                summary=f"{coin} için güncel haber bulunamadı → Nötr",
                headlines=[]
            )
            self._cache[cache_key] = result
            return result

        if self.provider == "gemini":
            # Gemini API limitine takılmamak için bekleme
            elapsed = time.time() - self._last_api_call
            if elapsed < self._api_min_interval:
                time.sleep(self._api_min_interval - elapsed)
            self._last_api_call = time.time()
            result = self._analyze_with_gemini(coin, headlines)
        elif self.provider == "claude":
            result = self._analyze_with_claude(coin, headlines)
        else:
            result = self._analyze_with_keywords(coin, headlines)

        self._cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # Haber Toplama
    # ─────────────────────────────────────────────
    def _fetch_headlines(self, coin: str) -> List[str]:
        """Ücretsiz haber kaynaklarından başlık topla"""
        headlines = []
        if not HAS_REQUESTS:
            return headlines

        try:
            url = f"https://cryptopanic.com/api/free/v1/posts/?currencies={coin}&kind=news"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for post in data.get("results", [])[:15]:
                    headlines.append(post.get("title", ""))
        except Exception as e:
            logger.debug(f"CryptoPanic hatası: {e}")

        try:
            coin_ids = {
                "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
                "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
                "DOGE": "dogecoin", "DOT": "polkadot", "AVAX": "avalanche-2",
            }
            coin_id = coin_ids.get(coin, coin.lower())
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                desc = data.get("description", {}).get("en", "")
                if desc:
                    headlines.append(desc[:200])
        except Exception as e:
            logger.debug(f"CoinGecko hatası: {e}")

        return [h for h in headlines if h.strip()]

    # ─────────────────────────────────────────────
    # 🟦 Google Gemini ile Analiz
    # ─────────────────────────────────────────────
    def _analyze_with_gemini(self, coin: str, headlines: List[str]) -> SentimentResult:
        """Google Gemini API ile duygu analizi"""
        if not HAS_REQUESTS:
            return self._analyze_with_keywords(coin, headlines)

        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/"
                f"models/gemini-2.0-flash:generateContent"
                f"?key={config.GEMINI_API_KEY}"
            )

            prompt = f"""Asagidaki {coin} kripto para haber basliklarini analiz et.

Basliklar:
{chr(10).join(f'- {h}' for h in headlines[:10])}

SADECE gecerli JSON dondur (baska hicbir sey yazma):
{{"score": <-1.0 ile 1.0 arasi float, -1=cok olumsuz, 1=cok olumlu>, "confidence": <0.0-1.0 arasi guvenilirlik>, "summary": "<tek cumle Turkce ozet>"}}"""

            resp = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 200,
                }
            }, timeout=20)

            if resp.status_code == 200:
                content = resp.json()
                text = content["candidates"][0]["content"]["parts"][0]["text"]
                text = text.strip().strip("```json").strip("```").strip()
                data = json.loads(text)

                return SentimentResult(
                    score=max(-1, min(1, float(data.get("score", 0)))),
                    confidence=max(0, min(1, float(data.get("confidence", 0.5)))),
                    source="gemini",
                    summary=data.get("summary", f"{coin} Gemini analizi tamamlandi"),
                    headlines=headlines[:5]
                )
            else:
                logger.warning(f"Gemini API hatasi: {resp.status_code}")

        except Exception as e:
            logger.warning(f"Gemini analiz hatasi: {e}")

        return self._analyze_with_keywords(coin, headlines)

    # ─────────────────────────────────────────────
    # 🟠 Claude ile Analiz
    # ─────────────────────────────────────────────
    def _analyze_with_claude(self, coin: str, headlines: List[str]) -> SentimentResult:
        """Anthropic Claude API ile duygu analizi"""
        if not HAS_REQUESTS:
            return self._analyze_with_keywords(coin, headlines)

        try:
            prompt = f"""Asagidaki {coin} kripto para haber basliklarini analiz et.

Basliklar:
{chr(10).join(f'- {h}' for h in headlines[:10])}

SADECE gecerli JSON dondur:
{{"score": <-1.0 ile 1.0 arasi>, "confidence": <0.0-1.0>, "summary": "<Turkce ozet>"}}"""

            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=20,
            )

            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"]
                text = text.strip().strip("```json").strip("```").strip()
                data = json.loads(text)

                return SentimentResult(
                    score=max(-1, min(1, float(data.get("score", 0)))),
                    confidence=max(0, min(1, float(data.get("confidence", 0.5)))),
                    source="claude",
                    summary=data.get("summary", f"{coin} Claude analizi tamamlandi"),
                    headlines=headlines[:5]
                )
            else:
                logger.warning(f"Claude API hatasi: {resp.status_code}")

        except Exception as e:
            logger.warning(f"Claude analiz hatasi: {e}")

        return self._analyze_with_keywords(coin, headlines)

    # ─────────────────────────────────────────────
    # 🟢 Anahtar Kelime Analizi (Ücretsiz, AI gerektirmez)
    # ─────────────────────────────────────────────
    def _analyze_with_keywords(self, coin: str, headlines: List[str]) -> SentimentResult:
        """Basit anahtar kelime tabanlı duygu analizi"""
        bull_score = 0
        bear_score = 0
        total_keywords = 0

        for headline in headlines:
            text = headline.lower()
            for keyword, weight in BULLISH_KEYWORDS.items():
                if keyword in text:
                    bull_score += weight
                    total_keywords += 1
            for keyword, weight in BEARISH_KEYWORDS.items():
                if keyword in text:
                    bear_score += weight
                    total_keywords += 1

        if total_keywords == 0:
            return SentimentResult(
                score=0.0, confidence=0.2, source="keywords",
                summary=f"{coin}: Belirgin duygu sinyali yok → Notr",
                headlines=headlines[:5]
            )

        total = bull_score + bear_score
        score = (bull_score - bear_score) / total if total > 0 else 0.0
        confidence = min(total_keywords / 10, 0.8)

        if score > 0.3:
            summary = f"{coin}: Olumlu haber akisi (boga sinyali)"
        elif score < -0.3:
            summary = f"{coin}: Olumsuz haber akisi (ayi sinyali)"
        else:
            summary = f"{coin}: Karisik haber akisi → Notr"

        return SentimentResult(
            score=round(score, 4), confidence=round(confidence, 4),
            source="keywords", summary=summary, headlines=headlines[:5]
        )
