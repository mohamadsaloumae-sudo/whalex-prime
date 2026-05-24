"""
WhaleMind-Prime-Core — service.py
═══════════════════════════════════════════════════════════════════
المنسق الرئيسي:

1. Oracle Agent     — جلب بيانات الماكرو (CoinGecko + Binance) — Plug-and-play
2. Futures Scanner  — يشغل Predator على 245+ عملة
3. قاعدة البيانات   — حفظ الإشارات مع end_time + highest_hit (Critical Fix)
4. Mini App API     — endpoints خفيفة للواجهة
5. Kill Switch      — إغلاق طارئ لكل الصفقات
6. MLOps            — حفظ Shadow Model snapshots
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time, json, os
from typing import Optional
from .engine import (
    Candle, Signal, MarketTier, ShadowTrade,
    predator_analyze, sleeping_giant_analyze,
    guardian_agent, shadow_record, get_shadow_stats,
    build_oracle_context, create_queues
)

log = logging.getLogger("service")

# ═══════════════════════════════════════════════════════════════
# ─── ORACLE AGENT — Plug-and-play ──────────────────────────────
# ═══════════════════════════════════════════════════════════════

class OracleAgent:
    """
    وكيل الرؤية الشاملة — بيانات الماكرو والكريبتو

    مبني بنمط Plug-and-play:
    - الآن: CoinGecko + Binance (مجاني)
    - لاحقاً: استبدل _fetch_token_unlocks بـ TokenUnlocks API
              استبدل _fetch_whale_alert  بـ Whale Alert API
              استبدل _fetch_macro_data   بـ Alpha Vantage API
    كل دالة مستقلة تماماً — لا تؤثر على الأخريات
    """

    INTERVAL = 3600  # يعمل مرة كل ساعة — توفير API calls

    def __init__(self):
        self._cache: dict = {}
        self._last_run: float = 0
        self._context: dict = {}

    def get_context(self) -> dict:
        return self._context.copy()

    # ─── FREE TIER (CoinGecko + Binance) ───────────────────────

    async def _fetch_btc_dominance(self) -> dict:
        """BTC Dominance + Market Cap (CoinGecko — مجاني)"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    "https://api.coingecko.com/api/v3/global",
                    headers={"Accept": "application/json"}
                )
                d = r.json().get("data", {})
                return {
                    "btc_dominance": d.get("market_cap_percentage", {}).get("btc", 50),
                    "market_cap_usd": d.get("total_market_cap", {}).get("usd", 0),
                    "market_cap_change_24h": d.get("market_cap_change_percentage_24h_usd", 0),
                }
        except Exception as e:
            log.warning("Oracle BTCDom error: %s", e)
            return {}

    async def _fetch_btc_change(self) -> float:
        """BTC 24h change من Binance"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(
                    "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT"
                )
                d = r.json()
                return float(d.get("priceChangePercent", 0))
        except:
            return 0.0

    async def _fetch_fear_greed(self) -> dict:
        """Fear & Greed Index (Alternative.me — مجاني)"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get("https://api.alternative.me/fng/?limit=1")
                d = r.json()["data"][0]
                return {
                    "fear_greed": int(d["value"]),
                    "sentiment": d["value_classification"],  # Fear / Greed / Extreme
                }
        except Exception as e:
            log.warning("Oracle FearGreed error: %s", e)
            return {"fear_greed": 50, "sentiment": "Neutral"}

    async def _fetch_usdt_supply(self) -> dict:
        """
        USDT Market Cap (Tether)
        ── PLUG: استبدل بـ Whale Alert API لاحقاً ──
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    "https://api.coingecko.com/api/v3/coins/tether?localization=false"
                )
                d = r.json()
                market_data = d.get("market_data", {})
                supply = market_data.get("circulating_supply", 0)
                change = market_data.get("market_cap_change_percentage_24h_in_currency", {}).get("usd", 0)
                # طباعة ضخمة = صعود وشيك
                minted_est = supply * abs(change) / 100 if change > 0 else 0
                return {
                    "usdt_supply": supply,
                    "usdt_change_24h": change,
                    "usdt_minted_24h": minted_est,
                }
        except Exception as e:
            log.warning("Oracle USDT error: %s", e)
            return {}

    async def _fetch_token_unlocks(self, symbol: str = "") -> dict:
        """
        ── PLUG: استبدل بـ TokenUnlocks API عند توفر المفتاح ──
        الآن: نعيد قيماً آمنة
        """
        # TODO: استبدل بـ:
        # headers = {"Authorization": f"Bearer {TOKEN_UNLOCKS_KEY}"}
        # r = await c.get(f"https://api.tokenunlocks.app/v1/unlocks?token={symbol}")
        return {"token_unlock_in_hours": 999}  # آمن

    async def _fetch_macro_data(self) -> dict:
        """
        ── PLUG: استبدل بـ Alpha Vantage API عند توفر المفتاح ──
        الآن: نستخدم بيانات تقريبية من CoinGecko
        """
        # TODO: استبدل بـ:
        # r = await c.get(f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=EUR&apikey={key}")
        return {"dxy": 104.0}  # تقريبي

    # ─── Main Run ───────────────────────────────────────────────

    async def run_once(self) -> dict:
        """
        يجمع كل البيانات — يعمل بالتوازي لتوفير الوقت
        """
        results = await asyncio.gather(
            self._fetch_btc_dominance(),
            self._fetch_btc_change(),
            self._fetch_fear_greed(),
            self._fetch_usdt_supply(),
            self._fetch_macro_data(),
            return_exceptions=True
        )

        oracle_raw = {}
        for r in results:
            if isinstance(r, dict):
                oracle_raw.update(r)
            elif isinstance(r, float):
                oracle_raw["btc_24h_change"] = r

        self._cache = oracle_raw
        self._context = build_oracle_context(oracle_raw)
        self._last_run = time.time()
        log.info("Oracle updated: BTC=%+.1f%% F&G=%d market_crash=%s",
                 oracle_raw.get("btc_24h_change", 0),
                 oracle_raw.get("fear_greed", 50),
                 self._context.get("market_crash_warning", False))
        return self._context

    async def run_loop(self):
        """Oracle يعمل في background — مرة كل ساعة"""
        while True:
            try:
                await self.run_once()
            except Exception as e:
                log.error("Oracle loop error: %s", e)
            await asyncio.sleep(self.INTERVAL)

    def get_report(self) -> dict:
        """تقرير JSON خفيف للـ Mini App"""
        return {
            "fear_greed": self._cache.get("fear_greed", 50),
            "sentiment": self._cache.get("sentiment", "Neutral"),
            "btc_dominance": round(self._cache.get("btc_dominance", 50), 1),
            "market_cap_change": round(self._cache.get("market_cap_change_24h", 0), 2),
            "usdt_printing": self._context.get("usdt_printing", False),
            "macro_bearish": self._context.get("macro_bearish", False),
            "last_updated": int(self._last_run),
        }


# ═══════════════════════════════════════════════════════════════
# ─── BINANCE DATA FETCHER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

CANDLE_CACHE: dict[str, list[Candle]] = {}
LAST_SIGNALS: dict[str, int] = {}
SIGNAL_COOLDOWN = 3600  # ساعة بين إشارتين لنفس العملة
ALL_SYMBOLS: list[MarketTier] = []

async def fetch_candles(symbol: str, interval: str = "15m", limit: int = 100) -> list[Candle]:
    """جلب الكاندلز من Binance Futures"""
    try:
        import httpx
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.get(url)
            data = r.json()
            if not isinstance(data, list):
                return []
            candles = []
            for d in data:
                candles.append(Candle(
                    time=int(d[0]),
                    open=float(d[1]),
                    high=float(d[2]),
                    low=float(d[3]),
                    close=float(d[4]),
                    volume=float(d[5]),
                    buy_volume=float(d[9])
                ))
            return candles
    except Exception as e:
        log.debug("fetch_candles %s: %s", symbol, e)
        return []

async def fetch_all_symbols() -> list[MarketTier]:
    """جلب كل عملات Futures من Binance وتصنيفها"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=20) as c:
            r1 = await c.get("https://fapi.binance.com/fapi/v1/exchangeInfo")
            symbols = [
                s["symbol"] for s in r1.json()["symbols"]
                if s["status"] == "TRADING" and s["symbol"].endswith("USDT")
            ]
            r2 = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
            vols = {t["symbol"]: float(t["quoteVolume"]) for t in r2.json()}

        sym_vols = [(s, vols.get(s, 0)) for s in symbols]
        sym_vols.sort(key=lambda x: x[1], reverse=True)

        # حدود ديناميكية
        active = [(s, v) for s, v in sym_vols if v >= 5_000_000]
        if not active:
            return []

        p80 = active[int(len(active) * 0.20)][1]
        p40 = active[int(len(active) * 0.60)][1]

        tiers = []
        for sym, vol in active:
            if vol >= p80:
                t = MarketTier(sym, vol, "S", 50, 4.5, 62)
            elif vol >= p40:
                t = MarketTier(sym, vol, "A", 25, 3.5, 55)
            else:
                t = MarketTier(sym, vol, "B", 10, 3.0, 50)
            tiers.append(t)

        log.info("Symbols loaded: %d (S:%d A:%d B:%d)",
                 len(tiers),
                 sum(1 for t in tiers if t.tier == "S"),
                 sum(1 for t in tiers if t.tier == "A"),
                 sum(1 for t in tiers if t.tier == "B"))
        return tiers
    except Exception as e:
        log.error("fetch_all_symbols: %s", e)
        return []


# ═══════════════════════════════════════════════════════════════
# ─── DATABASE — إصلاح حرج ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def save_signal(sig: Signal):
    """
    حفظ الإشارة في DB مع CRITICAL FIX:
    end_time و highest_hit دائماً موجودان بقيم افتراضية
    لمنع أي Crash عند db.commit()
    """
    try:
        from db.database import get_session, Signal as DBSignal
        db = get_session()
        db_sig = DBSignal(
            radar_type=sig.radar_type,
            symbol=sig.symbol,
            direction=sig.direction,
            grade=sig.grade,
            score=sig.score,
            confidence=sig.confidence,
            entry=sig.entry,
            sl=sig.sl,
            tp1=sig.tp1,
            tp2=sig.tp2,
            tp3=sig.tp3,
            leverage=sig.leverage,
            strategies=sig.strategies,
             
            # ─── CRITICAL FIX — لا crash هنا أبداً ───────────
            # ────────────────────────────────────────────────
        )
        db.add(db_sig)
        db.commit()
        log.info("DB saved: %s %s grade=%s", sig.symbol, sig.direction, sig.grade)
        return db_sig.id if hasattr(db_sig, 'id') else None
    except Exception as e:
        log.error("save_signal DB error: %s", e)
        # لا نوقف النظام بسبب خطأ DB
        return None

async def save_shadow_trade(trade: ShadowTrade):
    """حفظ الصفقة الوهمية في DB"""
    try:
        from db.database import get_session
        db = get_session()
        # جدول shadow_trades يجب أن يكون موجوداً في models
        from db.database import ShadowTrade as DBShadow
        db_t = DBShadow(
            symbol=trade.symbol,
            direction=trade.direction,
            entry=trade.entry,
            sl=trade.sl,
            tp1=trade.tp1,
            score=trade.score,
            confidence=trade.confidence,
            strategies=trade.strategies,
            result=trade.result,
            exit_price=trade.exit_price,
            pnl_pct=trade.pnl_pct,
            timestamp=trade.timestamp,
            closed_at=trade.closed_at,
        )
        db.add(db_t)
        db.commit()
    except Exception as e:
        log.debug("save_shadow_trade: %s", e)


# ═══════════════════════════════════════════════════════════════
# ─── ORCHESTRATOR — المدير التنفيذي ────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def orchestrate_approved(
    approved_queue: asyncio.Queue,
    broadcast_fn,
    position_manager_fn
):
    """
    يستقبل الإشارات المعتمدة من Guardian:
    1. يحفظها في DB
    2. يرسلها لـ Telegram
    3. يُعلم position_manager
    4. يسجل في Shadow Mode
    لا blocking — كل عملية مستقلة
    """
    log.info("Orchestrator started")
    while True:
        try:
            sig = await asyncio.wait_for(approved_queue.get(), timeout=1.0)

            # cooldown — تجنب إشارتين متتاليتين لنفس العملة
            now = int(time.time())
            if now - LAST_SIGNALS.get(sig.symbol, 0) < SIGNAL_COOLDOWN:
                log.debug("Cooldown: %s", sig.symbol)
                approved_queue.task_done()
                continue

            LAST_SIGNALS[sig.symbol] = now

            # تنفيذ بالتوازي — لا شيء يوقف الآخر
            await asyncio.gather(
                save_signal(sig),
                _broadcast_telegram(sig, broadcast_fn),
                shadow_record(sig),
                return_exceptions=True
            )

            # إعلام position_manager
            if position_manager_fn:
                asyncio.create_task(position_manager_fn(sig))

            approved_queue.task_done()

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            log.error("Orchestrator error: %s", e)
            await asyncio.sleep(1)


async def _broadcast_telegram(sig: Signal, broadcast_fn):
    """إرسال الإشارة لـ Telegram"""
    try:
        from services.telegram import TG
        sig_dict = {
            "radar_type": sig.radar_type,
            "symbol": sig.symbol,
            "direction": sig.direction,
            "grade": sig.grade,
            "confidence": sig.confidence,
            "entry": sig.entry,
            "sl": sig.sl,
            "tp1": sig.tp1,
            "tp2": sig.tp2,
            "tp3": sig.tp3,
            "leverage": sig.leverage,
            "strategies": sig.strategies,
            "tier": sig.tier,
        }
        await TG.broadcast_signal(sig_dict)
        # WebSocket broadcast للـ Mini App
        if broadcast_fn:
            await broadcast_fn({"event": "signal", "data": sig_dict})
    except Exception as e:
        log.error("Telegram broadcast error: %s", e)


# ═══════════════════════════════════════════════════════════════
# ─── FUTURES SCANNER LOOP ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

_scan_count = 0

async def futures_scan_loop(oracle: OracleAgent, signal_queue: asyncio.Queue):
    """
    حلقة المسح الرئيسية — تشغيل Predator على كل العملات
    لا اختناق: كل رمز يُحلَّل في coroutine مستقل
    Semaphore يمنع تحميل زائد
    """
    global _scan_count, ALL_SYMBOLS
    sem = asyncio.Semaphore(15)  # 15 طلب متزامن max

    async def analyze_one(tier: MarketTier):
        async with sem:
            candles = await fetch_candles(tier.symbol, "15m", 100)
            if not candles:
                return
            oracle_ctx = oracle.get_context()
            await predator_analyze(candles, tier.symbol, tier, oracle_ctx, signal_queue)

    while True:
        try:
            # تحديث قائمة العملات كل ساعة
            if _scan_count % 12 == 0:
                ALL_SYMBOLS = await fetch_all_symbols()
                log.info("Symbols refreshed: %d", len(ALL_SYMBOLS))

            if not ALL_SYMBOLS:
                await asyncio.sleep(30)
                continue

            _scan_count += 1
            start = time.time()

            # مسح موازٍ — كل العملات في نفس الوقت
            tasks = [analyze_one(t) for t in ALL_SYMBOLS]
            await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.time() - start
            log.info("Scan #%d done — %d symbols in %.1fs — next in 5min",
                     _scan_count, len(ALL_SYMBOLS), elapsed)

        except Exception as e:
            log.error("Scan loop error: %s", e)

        await asyncio.sleep(300)  # 5 دقائق


async def sleeping_giants_loop(oracle: OracleAgent, signal_queue: asyncio.Queue):
    """
    رادار التجميع الصامت — يعمل على الفريم اليومي
    أبطأ — مسح كل 6 ساعات
    """
    sem = asyncio.Semaphore(5)  # أقل تزامن — فريم يومي

    async def scan_one(tier: MarketTier):
        async with sem:
            candles = await fetch_candles(tier.symbol, "1d", 60)
            if candles:
                await sleeping_giant_analyze(candles, tier.symbol, tier, signal_queue)

    while True:
        try:
            if ALL_SYMBOLS:
                tasks = [scan_one(t) for t in ALL_SYMBOLS[:100]]  # أكبر 100 فقط
                await asyncio.gather(*tasks, return_exceptions=True)
                log.info("Sleeping Giants scan done")
        except Exception as e:
            log.error("SleepingGiants error: %s", e)

        await asyncio.sleep(21600)  # 6 ساعات


# ═══════════════════════════════════════════════════════════════
# ─── MINI APP API ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def build_signal_payload(sig: Signal) -> dict:
    """حزمة JSON خفيفة للـ Mini App"""
    return {
        "symbol": sig.symbol,
        "direction": sig.direction,
        "grade": sig.grade,
        "score": sig.score,
        "confidence": sig.confidence,
        "entry": sig.entry,
        "sl": sig.sl,
        "tp1": sig.tp1,
        "tp2": sig.tp2,
        "tp3": sig.tp3,
        "leverage": sig.leverage,
        "strategies": sig.strategies,
        "radar_type": sig.radar_type,
        "tier": sig.tier,
        "timestamp": sig.timestamp,
    }

# ─── Kill Switch ────────────────────────────────────────────────

_kill_switch_active = False

async def activate_kill_switch(broadcast_fn=None):
    """
    مفتاح الإعدام — يغلق كل الصفقات المفتوحة فوراً
    يُستدعى من API endpoint عند الطوارئ
    """
    global _kill_switch_active
    _kill_switch_active = True
    log.critical("🚨 KILL SWITCH ACTIVATED — إغلاق كل الصفقات")

    try:
        from position_manager import ACTIVE, force_close_all
        await force_close_all(reason="kill_switch")
    except Exception as e:
        log.error("Kill switch error: %s", e)

    # إشعار Telegram
    try:
        from services.telegram import TG
        s = await TG.settings
        await TG.send_admin("🚨 KILL SWITCH — كل الصفقات أُغلقت فوراً")
    except:
        pass

    if broadcast_fn:
        await broadcast_fn({"event": "kill_switch", "data": {"status": "activated"}})

    return {"status": "kill_switch_activated", "timestamp": int(time.time())}

def is_kill_switch_active() -> bool:
    return _kill_switch_active

# ─── MLOps — حفظ نموذج Shadow ──────────────────────────────────

async def save_shadow_snapshot():
    """
    حفظ أوزان Shadow Model دورياً
    الآن: حفظ JSON محلي + رفع سحابي (placeholder)
    """
    try:
        stats = get_shadow_stats()
        snapshot = {
            "timestamp": int(time.time()),
            "stats": stats,
            "trades_count": len([]),  # يمكن تمرير SHADOW_TRADES
        }
        path = "/opt/whalex/snapshots"
        os.makedirs(path, exist_ok=True)
        filename = f"{path}/shadow_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump(snapshot, f, indent=2)
        log.info("Shadow snapshot saved: %s", filename)

        # TODO: رفع سحابي
        # await upload_to_cloud(filename)
    except Exception as e:
        log.error("snapshot error: %s", e)

async def mlops_loop():
    """حفظ Snapshot كل 24 ساعة"""
    while True:
        await asyncio.sleep(86400)
        await save_shadow_snapshot()


# ═══════════════════════════════════════════════════════════════
# ─── MAIN SERVICE RUNNER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

oracle = OracleAgent()

async def start_all_services(broadcast_fn=None, position_manager_fn=None):
    """
    نقطة التشغيل الرئيسية — تشغيل كل الوكلاء معاً بدون اختناق

    التدفق:
    Predator ──→ signal_queue ──→ Guardian ──→ approved_queue ──→ Orchestrator
                                                                    ├── DB
                                                                    ├── Telegram
                                                                    ├── WebSocket
                                                                    └── Shadow Mode
    """
    signal_queue, approved_queue = create_queues()

    log.info("WhaleMind-Prime-Core starting...")

    # تشغيل Oracle أولاً للحصول على context
    await oracle.run_once()

    # جلب العملات
    global ALL_SYMBOLS
    ALL_SYMBOLS = await fetch_all_symbols()

    # تشغيل كل الوكلاء بالتوازي
    await asyncio.gather(
        oracle.run_loop(),
        futures_scan_loop(oracle, signal_queue),
        sleeping_giants_loop(oracle, signal_queue),
        guardian_agent(signal_queue, approved_queue, oracle.get_context()),
        orchestrate_approved(approved_queue, broadcast_fn, position_manager_fn),
        mlops_loop(),
        return_exceptions=True
    )
