"""
🛡️ Risk Yönetimi - Pozisyona Ekleme + Akıllı Rotasyon Destekli
"""
import json
import logging
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import config

logger = logging.getLogger("RiskManager")

@dataclass
class Position:
    symbol: str
    entry_price: float
    quantity: float
    entry_time: str
    invested_usdt: float = 0.0
    highest_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    buy_count: int = 1

    def __post_init__(self):
        if self.highest_price == 0:
            self.highest_price = self.entry_price
        if self.stop_loss_price == 0:
            self.stop_loss_price = self.entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
        if self.take_profit_price == 0:
            self.take_profit_price = self.entry_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
        if self.invested_usdt == 0:
            self.invested_usdt = self.entry_price * self.quantity

@dataclass
class DailyStats:
    date: str = ""
    trades_count: int = 0
    total_pnl: float = 0.0
    wins: int = 0
    losses: int = 0
    total_invested: float = 0.0
    def __post_init__(self):
        if not self.date:
            self.date = date.today().isoformat()

class RiskManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.daily_stats = DailyStats()
        self.trade_history: List[dict] = []
        self._load_state()

    def can_open_position(self, symbol: str, amount_usdt: float) -> Tuple[bool, str]:
        self._check_daily_reset()

        # Aynı coin: ekleme yapılabilir mi?
        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos.buy_count >= config.MAX_BUYS_PER_COIN:
                return False, f"⚠️ {symbol} max ekleme sayısına ulaştı ({pos.buy_count}/{config.MAX_BUYS_PER_COIN})"
            return True, "✅ Mevcut pozisyona ekleme yapılacak"

        # Yeni coin: yer var mı?
        if len(self.positions) >= config.MAX_OPEN_POSITIONS:
            # Akıllı rotasyon açıksa "yer yok" deme, bot halleder
            if config.SMART_ROTATION:
                return True, "🔄 Akıllı rotasyon: en kötü coin satılacak"
            return False, f"⚠️ Max {config.MAX_OPEN_POSITIONS} coin limitine ulaşıldı"

        # Günlük limitler
        if self.daily_stats.trades_count >= config.MAX_DAILY_TRADES:
            return False, f"⚠️ Günlük {config.MAX_DAILY_TRADES} işlem limitine ulaşıldı"

        if self.daily_stats.total_invested > 0:
            loss_pct = (self.daily_stats.total_pnl / self.daily_stats.total_invested) * 100
            if loss_pct < -config.MAX_DAILY_LOSS_PERCENT:
                return False, f"🛑 Günlük zarar limiti aşıldı ({loss_pct:.1f}%)"

        return True, "✅ Pozisyon açılabilir"

    def needs_rotation(self, symbol: str) -> bool:
        """Slot dolu ama yeni coin gelmek istiyor → rotasyon gerekli mi?"""
        return (symbol not in self.positions and
                len(self.positions) >= config.MAX_OPEN_POSITIONS and
                config.SMART_ROTATION)

    def find_worst_position(self, exchange) -> Optional[str]:
        """En kötü performanslı açık pozisyonu bul"""
        worst_sym = None
        worst_pnl = float('inf')

        for sym, pos in self.positions.items():
            price = exchange.get_current_price(sym)
            if price:
                pnl_pct = ((price / pos.entry_price) - 1) * 100
                if pnl_pct < worst_pnl:
                    worst_pnl = pnl_pct
                    worst_sym = sym

        return worst_sym

    def register_buy(self, symbol: str, price: float, quantity: float, amount_usdt: float = 0):
        if symbol in self.positions:
            old = self.positions[symbol]
            total_qty = old.quantity + quantity
            avg_price = (old.entry_price * old.quantity + price * quantity) / total_qty
            old.entry_price = avg_price
            old.quantity = total_qty
            old.highest_price = max(old.highest_price, price)
            old.stop_loss_price = avg_price * (1 - config.STOP_LOSS_PERCENT / 100)
            old.take_profit_price = avg_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
            old.invested_usdt += amount_usdt or (price * quantity)
            old.buy_count += 1
            logger.info(f"📥 EKLEME: {symbol} @ {price:.4f} | Yeni ort: {avg_price:.4f} | Toplam: {total_qty:.6f}")
        else:
            pos = Position(
                symbol=symbol, entry_price=price, quantity=quantity,
                entry_time=datetime.now().isoformat(),
                invested_usdt=amount_usdt or (price * quantity),
            )
            self.positions[symbol] = pos
            logger.info(f"📥 ALIM: {symbol} @ {price:.4f} x {quantity:.6f} | SL: {pos.stop_loss_price:.4f} | TP: {pos.take_profit_price:.4f}")

        self.daily_stats.trades_count += 1
        self.daily_stats.total_invested += amount_usdt or (price * quantity)
        self._save_state()

    def register_sell(self, symbol: str, price: float, reason: str = ""):
        if symbol not in self.positions:
            return 0.0, 0.0

        pos = self.positions[symbol]
        pnl = (price - pos.entry_price) * pos.quantity
        pnl_pct = ((price / pos.entry_price) - 1) * 100

        self.daily_stats.trades_count += 1
        self.daily_stats.total_pnl += pnl
        if pnl > 0:
            self.daily_stats.wins += 1
        else:
            self.daily_stats.losses += 1

        self.trade_history.append({
            "symbol": symbol, "entry_price": pos.entry_price,
            "exit_price": price, "quantity": pos.quantity,
            "invested": pos.invested_usdt,
            "pnl": round(pnl, 4), "pnl_percent": round(pnl_pct, 2),
            "reason": reason, "entry_time": pos.entry_time,
            "exit_time": datetime.now().isoformat(),
        })

        logger.info(f"{'💰' if pnl > 0 else '📉'} SATIM: {symbol} @ {price:.4f} | K/Z: {pnl:+.4f}$ ({pnl_pct:+.2f}%) | Sebep: {reason}")
        del self.positions[symbol]
        self._save_state()
        return pnl, pnl_pct

    def check_position(self, symbol: str, current_price: float) -> Optional[str]:
        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]

        if current_price > pos.highest_price:
            pos.highest_price = current_price
            if config.USE_TRAILING_STOP:
                new_sl = current_price * (1 - config.TRAILING_STOP_PERCENT / 100)
                if new_sl > pos.stop_loss_price:
                    pos.stop_loss_price = new_sl

        if current_price <= pos.stop_loss_price:
            return "STOP_LOSS"
        if current_price >= pos.take_profit_price:
            return "TAKE_PROFIT"
        return None

    def get_status_report(self) -> dict:
        self._check_daily_reset()
        return {
            "open_positions": len(self.positions),
            "max_positions": config.MAX_OPEN_POSITIONS,
            "daily_trades": self.daily_stats.trades_count,
            "max_daily_trades": config.MAX_DAILY_TRADES,
            "daily_pnl": round(self.daily_stats.total_pnl, 4),
            "daily_wins": self.daily_stats.wins,
            "daily_losses": self.daily_stats.losses,
            "win_rate": round(self.daily_stats.wins / max(1, self.daily_stats.wins + self.daily_stats.losses) * 100, 1),
            "total_trades_history": len(self.trade_history),
        }

    def _check_daily_reset(self):
        today = date.today().isoformat()
        if self.daily_stats.date != today:
            logger.info(f"📅 Yeni gün: {today}")
            self.daily_stats = DailyStats(date=today)

    def _save_state(self):
        try:
            state = {
                "positions": {k: asdict(v) for k, v in self.positions.items()},
                "daily_stats": asdict(self.daily_stats),
                "trade_history": self.trade_history[-100:],
            }
            Path(config.TRADES_LOG_FILE).write_text(json.dumps(state, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}")

    def _load_state(self):
        try:
            path = Path(config.TRADES_LOG_FILE)
            if path.exists():
                state = json.loads(path.read_text())
                for sym, data in state.get("positions", {}).items():
                    self.positions[sym] = Position(**data)
                ds = state.get("daily_stats", {})
                self.daily_stats = DailyStats(**ds) if ds else DailyStats()
                self.trade_history = state.get("trade_history", [])
                logger.info(f"📂 Durum yüklendi: {len(self.positions)} pozisyon, {len(self.trade_history)} geçmiş")
        except Exception as e:
            logger.warning(f"Durum yükleme hatası: {e}")
