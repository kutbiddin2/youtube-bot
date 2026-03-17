"""
🎯 Strateji Motoru - Akıllı Rotasyonlu
"""
import logging
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import config
from modules.technical_analysis import TechnicalAnalyzer, TechnicalSignal
from modules.sentiment_analyzer import SentimentAnalyzer, SentimentResult

logger = logging.getLogger("StrategyEngine")

class Action(Enum):
    BUY = "AL"
    SELL = "SAT"
    HOLD = "BEKLE"

@dataclass
class TradeSignal:
    action: Action
    symbol: str
    confidence: float
    technical_score: float
    sentiment_score: float
    combined_score: float
    reasons: List[str]

class StrategyEngine:
    def __init__(self):
        self.technical = TechnicalAnalyzer()
        self.sentiment = SentimentAnalyzer()
        self.sentiment_weight = config.SENTIMENT_WEIGHT
        self.technical_weight = 1.0 - config.SENTIMENT_WEIGHT

    def evaluate(self, symbol: str, df) -> TradeSignal:
        reasons = []

        # 1. Teknik Analiz
        tech_signals = self.technical.analyze(df)
        tech_score = self.technical.get_combined_score(tech_signals)
        for sig in tech_signals:
            reasons.append(f"📊 {sig.description}")

        # 2. Duygu Analizi (sadece güçlü sinyalde çağır)
        sent_score = 0.0
        sent_confidence = 0.2
        if abs(tech_score) > 0.10:
            sentiment = self.sentiment.analyze(symbol)
            sent_score = sentiment.score
            sent_confidence = sentiment.confidence
            if abs(sent_score) > 0.1:
                reasons.append(f"🧠 {sentiment.summary}")

        # 3. Birleştir
        combined = tech_score * self.technical_weight + sent_score * self.sentiment_weight

        # 4. Güvenilirlik
        if tech_score * sent_score > 0:
            agreement_bonus = 0.15
            reasons.append("✅ Teknik ve duygu uyumlu")
        elif abs(sent_score) < 0.1:
            agreement_bonus = 0.05
        else:
            agreement_bonus = -0.05
            reasons.append("⚠️ Teknik ve duygu çelişiyor")

        if tech_signals:
            dirs = [1 if s.signal > 0 else -1 for s in tech_signals if abs(s.signal) > 0.1]
            consistency = abs(sum(dirs)) / len(dirs) if dirs else 0
        else:
            consistency = 0

        confidence = min(1.0, max(0.0,
            0.40 + consistency * 0.35 + sent_confidence * 0.15 + agreement_bonus
        ))

        # 5. Karar
        action = self._decide(combined, confidence)

        if action == Action.BUY:
            reasons.append(f"🟢 AL (skor: {combined:+.3f}, güven: %{confidence*100:.0f})")
        elif action == Action.SELL:
            reasons.append(f"🔴 SAT (skor: {combined:+.3f}, güven: %{confidence*100:.0f})")
        else:
            reasons.append(f"⚪ BEKLE (skor: {combined:+.3f}, güven: %{confidence*100:.0f})")

        return TradeSignal(action, symbol, round(confidence, 4),
                          round(tech_score, 4), round(sent_score, 4),
                          round(combined, 4), reasons)

    def _decide(self, score, confidence):
        if confidence < config.MIN_SIGNAL_CONFIDENCE:
            return Action.HOLD
        if score > 0.08:
            return Action.BUY
        elif score < -0.08:
            return Action.SELL
        return Action.HOLD
