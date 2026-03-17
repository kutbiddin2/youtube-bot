"""
🤖 BINANCE AI TRADING BOT
Yüzde bazlı | Güvene göre dinamik | Akıllı rotasyon | Telegram bildirimli
"""
import sys, time, json, signal as sig_mod, logging, argparse
from datetime import datetime
from pathlib import Path
import config
from modules.binance_client import BinanceClient
from modules.strategy_engine import StrategyEngine, Action
from modules.risk_manager import RiskManager

# ── Loglama ──
def setup_logging():
    fmt = logging.Formatter("%(asctime)s │ %(name)-18s │ %(message)s", datefmt="%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    fh = logging.FileHandler("bot.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(fh)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("Bot")

# ── Telegram ──
def send_tg(message: str):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        logger.debug(f"Telegram hatası: {e}")

def reason_tr(reason):
    return {
        "STOP_LOSS": "🛡️ Zarar kes devreye girdi",
        "TAKE_PROFIT": "🎯 Kâr hedefine ulaştı!",
        "SINYAL_SATIM": "📊 Satış sinyali geldi",
        "TRAILING_STOP": "📉 Zirvedeki fiyattan düştü",
        "ROTASYON": "🔄 Daha iyi fırsat için yer açıldı",
    }.get(reason, reason)


def calc_amount(max_for_coin, confidence):
    """
    Güvene göre alım miktarı (1000$ bakiye, %10 limit = max 100$ ise):
    %70+ güven  → 70$
    %60-70      → 40$
    %50-60      → 20$
    %40-50      → 10$
    %30-40      → 5$
    """
    if confidence >= 0.70:
        pct = 0.70
    elif confidence >= 0.60:
        pct = 0.40
    elif confidence >= 0.50:
        pct = 0.20
    elif confidence >= 0.40:
        pct = 0.10
    else:
        pct = 0.05
    return round(max(5.0, max_for_coin * pct), 2)


class TradingBot:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.running = True
        self.cycle_count = 0

        logger.info("=" * 55)
        logger.info("🤖 BINANCE AI TRADING BOT")
        logger.info("=" * 55)
        if dry_run:
            logger.info("🧪 DRY-RUN modu")
        if config.USE_TESTNET:
            logger.info("🧪 TESTNET modu")

        self.exchange = BinanceClient()
        self.strategy = StrategyEngine()
        self.risk = RiskManager()

        # Bakiye
        self.balance = self.exchange.get_account_balance("USDT")
        logger.info(f"💰 Bakiye: {self.balance:.2f}$")

        # Yüzde bazlı coin limiti
        self.max_per_coin = round(self.balance * config.COIN_MAX_PERCENT / 100, 2)
        logger.info(f"💵 Coin başı max: {self.max_per_coin:.0f}$ (bakiyenin %{config.COIN_MAX_PERCENT}'u)")
        logger.info(f"📊 {len(config.TRADING_PAIRS)} coin takipte")
        logger.info(f"🔄 Akıllı rotasyon: {'AÇIK' if config.SMART_ROTATION else 'KAPALI'}")
        logger.info("=" * 55)

        sig_mod.signal(sig_mod.SIGINT, lambda s, f: setattr(self, 'running', False))

    # ══════════════════════════════════════
    # ANA DÖNGÜ
    # ══════════════════════════════════════
    def run(self):
        send_tg(
            f"🤖 <b>Bot başlatıldı!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Bakiye: <b>{self.balance:.2f}</b>$\n"
            f"💵 Coin limiti: <b>{self.max_per_coin:.0f}</b>$ (%{config.COIN_MAX_PERCENT})\n"
            f"📊 {len(config.TRADING_PAIRS)} coin takipte\n"
            f"🛡️ SL: %{config.STOP_LOSS_PERCENT} | TP: %{config.TAKE_PROFIT_PERCENT}\n"
            f"🔄 Rotasyon: {'Açık' if config.SMART_ROTATION else 'Kapalı'}\n"
            f"📱 {'🧪 Testnet' if config.USE_TESTNET else '💰 GERÇEK'}"
        )

        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"\n{'─'*50}")
                logger.info(f"🔄 Döngü #{self.cycle_count} - {datetime.now().strftime('%H:%M:%S')}")

                self.balance = self.exchange.get_account_balance("USDT")
                # Coin limitini bakiyeye göre güncelle
                self.max_per_coin = round(self.balance * config.COIN_MAX_PERCENT / 100, 2)

                self._scan_all()
                self._show_full_status()

                logger.info(f"⏳ {config.SCAN_INTERVAL_SECONDS}sn bekleniyor...")
                time.sleep(config.SCAN_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Hata: {e}", exc_info=True)
                time.sleep(30)

        self._shutdown()

    # ══════════════════════════════════════
    # TARAMA
    # ══════════════════════════════════════
    def _scan_all(self):
        for symbol in config.TRADING_PAIRS:
            try:
                self._process(symbol)
            except Exception as e:
                logger.error(f"❌ {symbol}: {e}")

    def _process(self, symbol):
        price = self.exchange.get_current_price(symbol)
        if not price:
            return

        exit_reason = self.risk.check_position(symbol, price)
        if exit_reason:
            self._do_sell(symbol, price, exit_reason)
            return

        df = self.exchange.get_klines(symbol)
        if df.empty or len(df) < 30:
            return

        signal = self.strategy.evaluate(symbol, df)
        for r in signal.reasons:
            logger.info(f"  {symbol} │ {r}")

        if signal.action == Action.BUY and signal.confidence >= config.MIN_SIGNAL_CONFIDENCE:
            self._do_buy(symbol, price, signal)

    # ══════════════════════════════════════
    # ALIM
    # ══════════════════════════════════════
    def _do_buy(self, symbol, price, signal):
        # Güvene göre miktar
        amount = calc_amount(self.max_per_coin, signal.confidence)

        # Bu coinde zaten ne kadar var?
        if symbol in self.risk.positions:
            already = self.risk.positions[symbol].invested_usdt
            remaining = self.max_per_coin - already
            if remaining < 5:
                logger.info(f"  {symbol} │ ⚠️ Coin limiti dolu ({already:.0f}/{self.max_per_coin:.0f}$)")
                return
            amount = min(amount, remaining)

        can, reason = self.risk.can_open_position(symbol, amount)
        if not can:
            logger.info(f"  {symbol} │ {reason}")
            return

        # Akıllı rotasyon
        if self.risk.needs_rotation(symbol):
            worst = self.risk.find_worst_position(self.exchange)
            if worst:
                wp = self.exchange.get_current_price(worst)
                if wp:
                    logger.info(f"  🔄 ROTASYON: {worst} satılıp {symbol} alınacak")
                    self._do_sell(worst, wp, "ROTASYON")
                else:
                    return
            else:
                return

        coin = symbol.replace("USDT", "")
        is_adding = symbol in self.risk.positions

        logger.info(f"  {symbol} │ 💵 Güven %{signal.confidence*100:.0f} → {amount:.0f}$ alınacak")

        if self.dry_run:
            qty = amount / price
            self.risk.register_buy(symbol, price, qty, amount)
            pos = self.risk.positions.get(symbol)
            self._send_buy_tg(coin, price, amount, signal, pos, is_adding, dry=True)
            return

        order = self.exchange.place_buy_order(symbol, amount)
        if not order:
            return

        self.risk.register_buy(symbol, order["price"], order["quantity"], amount)
        self.balance = self.exchange.get_account_balance("USDT")
        pos = self.risk.positions.get(symbol)
        self._send_buy_tg(coin, order["price"], amount, signal, pos, is_adding, dry=False)

    def _send_buy_tg(self, coin, price, amount, signal, pos, is_adding, dry):
        """Alım Telegram mesajı — detaylı"""
        tag = " (test)" if dry else ""
        reasons = [r for r in signal.reasons if any(k in r for k in ["RSI","MACD","Bollinger","EMA","Hacim","🧠"])]

        msg = f"{'📥 EKLEME' if is_adding else '🆕 YENİ ALIM'}{tag}\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"🪙 <b>{coin}</b> — {price:.4f}$\n"
        msg += f"💵 Bu alım: <b>{amount:.0f}$</b>\n"
        msg += f"🎯 Güven: <b>%{signal.confidence*100:.0f}</b>\n"

        if pos:
            # Maliyet vs güncel değer
            current_val = price * pos.quantity
            msg += f"━━━━━━━━━━━━━━━━━━\n"
            msg += f"📊 <b>Pozisyon detayı:</b>\n"
            msg += f"  💰 Maliyet (toplam harcanan): <b>{pos.invested_usdt:.2f}$</b>\n"
            msg += f"  💲 Güncel değeri: <b>{current_val:.2f}$</b>\n"
            msg += f"  📈 Ort. giriş: {pos.entry_price:.4f}$\n"
            msg += f"  🛡️ Zarar kes: {pos.stop_loss_price:.4f}$\n"
            msg += f"  🎯 Kâr al: {pos.take_profit_price:.4f}$\n"
            msg += f"  📦 Alım sayısı: {pos.buy_count}x\n"

        if reasons:
            msg += f"━━━━━━━━━━━━━━━━━━\n📋 <b>Neden aldı?</b>\n"
            for r in reasons[:5]:
                msg += f"  {r}\n"

        msg += f"━━━━━━━━━━━━━━━━━━\n💰 Bakiye: <b>{self.balance:.2f}</b>$"
        send_tg(msg)

    # ══════════════════════════════════════
    # SATIM
    # ══════════════════════════════════════
    def _do_sell(self, symbol, price, reason):
        if symbol not in self.risk.positions:
            return

        pos = self.risk.positions[symbol]
        coin = symbol.replace("USDT", "")
        invested = pos.invested_usdt
        current_val = price * pos.quantity

        if self.dry_run:
            pnl, pnl_pct = self.risk.register_sell(symbol, price, reason)
            self._send_sell_tg(coin, pos.entry_price, price, invested, current_val, pnl, pnl_pct, reason, dry=True)
            return

        order = self.exchange.place_sell_order(symbol, pos.quantity)
        if not order:
            return

        sell_price = order["price"]
        current_val = sell_price * pos.quantity
        pnl, pnl_pct = self.risk.register_sell(symbol, sell_price, reason)
        self.balance = self.exchange.get_account_balance("USDT")
        self._send_sell_tg(coin, pos.entry_price, sell_price, invested, current_val, pnl, pnl_pct, reason, dry=False)

    def _send_sell_tg(self, coin, entry, exit_p, invested, current_val, pnl, pnl_pct, reason, dry):
        """Satım Telegram mesajı — maliyet vs satış değeri detaylı"""
        tag = " (test)" if dry else ""
        status = self.risk.get_status_report()
        emoji = "💰 KÂRLI" if pnl >= 0 else "📉 ZARARLI"

        msg = f"{emoji} SATIM{tag}\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"🪙 <b>{coin}</b>\n"
        msg += f"💲 Giriş: {entry:.4f}$ → Çıkış: {exit_p:.4f}$\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Maliyet (harcanan): <b>{invested:.2f}$</b>\n"
        msg += f"💲 Satış değeri: <b>{current_val:.2f}$</b>\n"
        msg += f"📊 <b>Net K/Z: {pnl_pct:+.2f}% ({pnl:+.2f}$)</b>\n"
        msg += f"📋 Sebep: {reason_tr(reason)}\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Bakiye: <b>{self.balance:.2f}</b>$\n"
        msg += f"📈 Açık: {status['open_positions']} coin\n"
        msg += f"📊 Bugün: ✅{status['daily_wins']} ❌{status['daily_losses']}\n"
        msg += f"💹 Günlük K/Z: <b>{status['daily_pnl']:+.2f}</b>$"
        send_tg(msg)

    # ══════════════════════════════════════
    # DURUM RAPORU (Terminal + Telegram her döngüde)
    # ══════════════════════════════════════
    def _show_full_status(self):
        usdt = self.balance
        positions_value = 0.0
        total_invested = 0.0
        pos_lines_log = []
        pos_lines_tg = []

        for sym, pos in self.risk.positions.items():
            price = self.exchange.get_current_price(sym)
            if price:
                val = price * pos.quantity
                positions_value += val
                total_invested += pos.invested_usdt
                pnl_pct = ((price / pos.entry_price) - 1) * 100
                pnl_usdt = val - pos.invested_usdt
                coin = sym.replace("USDT", "")
                emoji = "🟢" if pnl_pct >= 0 else "🔴"

                pos_lines_log.append(
                    f"  {sym}: giriş={pos.entry_price:.4f} şimdi={price:.4f} "
                    f"({pnl_pct:+.2f}%) maliyet={pos.invested_usdt:.0f}$ değer={val:.0f}$"
                )
                pos_lines_tg.append(
                    f"{emoji} <b>{coin}</b>: {pos.entry_price:.4f} → {price:.4f}\n"
                    f"    <b>{pnl_pct:+.2f}%</b> | Maliyet: {pos.invested_usdt:.0f}$ → Değer: {val:.0f}$ ({pnl_usdt:+.1f}$)"
                )

        total = usdt + positions_value
        total_pnl = positions_value - total_invested if total_invested > 0 else 0
        status = self.risk.get_status_report()

        # Terminal
        logger.info(f"💰 {usdt:.2f}$ serbest + {positions_value:.2f}$ pozisyon = {total:.2f}$ toplam")
        for line in pos_lines_log:
            logger.info(line)

        # Telegram
        msg = f"📊 <b>DURUM</b> #{self.cycle_count}\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"💵 Serbest: <b>{usdt:.2f}</b>$\n"
        msg += f"📊 Pozisyonlarda: <b>{positions_value:.2f}</b>$\n"
        msg += f"🏦 Toplam: <b>{total:.2f}</b>$\n"

        if total_invested > 0:
            msg += f"📈 Pozisyon K/Z: <b>{total_pnl:+.2f}</b>$\n"

        msg += f"💹 Günlük K/Z: <b>{status['daily_pnl']:+.2f}</b>$\n"
        msg += f"🔄 İşlem: {status['daily_trades']} | ✅{status['daily_wins']} ❌{status['daily_losses']}\n"
        msg += f"💵 Coin limiti: {self.max_per_coin:.0f}$ (%{config.COIN_MAX_PERCENT})"

        if pos_lines_tg:
            msg += f"\n━━━━━━━━━━━━━━━━━━\n📋 <b>Pozisyonlar ({len(self.risk.positions)}/{config.MAX_OPEN_POSITIONS}):</b>\n"
            msg += "\n".join(pos_lines_tg)
        else:
            msg += "\n\n⏳ Açık pozisyon yok, fırsat aranıyor..."
        send_tg(msg)

    # ══════════════════════════════════════
    # KAPANIŞ
    # ══════════════════════════════════════
    def _shutdown(self):
        logger.info("🛑 Bot kapatılıyor...")
        status = self.risk.get_status_report()
        send_tg(
            f"🛑 <b>Bot kapatıldı</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Son bakiye: <b>{self.balance:.2f}</b>$\n"
            f"📈 Açık pozisyon: {status['open_positions']}\n"
            f"💹 Günlük K/Z: <b>{status['daily_pnl']:+.2f}</b>$\n"
            f"📊 {status['daily_wins']}W / {status['daily_losses']}L"
        )
        logger.info("👋 Güle güle!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Tüm pozisyonları sıfırla")
    args = parser.parse_args()
    setup_logging()

    if args.reset:
        p = Path(config.TRADES_LOG_FILE)
        if p.exists():
            p.unlink()
            print("🗑️ Tüm pozisyonlar ve geçmiş silindi. Temiz başlangıç!")
        else:
            print("Zaten temiz.")
        return

    if args.status:
        rm = RiskManager()
        print(json.dumps(rm.get_status_report(), indent=2, ensure_ascii=False))
        return

    TradingBot(dry_run=args.dry_run).run()

if __name__ == "__main__":
    main()
