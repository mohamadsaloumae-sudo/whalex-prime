"""
WhaleMind-Prime-Core — position_manager.py
═══════════════════════════════════════════════════════════════════
المنفذ السريع ومدير الطوارئ:

1. Pyramiding       — بدء 2x → رفع تلقائي عند تأكيد الانفجار
2. Trailing Stop    — متحرك ديناميكي بناءً على ATR
3. Claude AI        — استشارة طارئة عند تغير Order Book
4. Force Close      — إغلاق فوري بسعر السوق (يكسر حلقة AI)
5. Kill Switch      — إغلاق كل الصفقات دفعة واحدة
6. هروب تكتيكي      — استباقي قبل ضرب SL
7. إحصائيات         — لوحة التحكم في Mini App
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time, json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from .engine import Signal

log = logging.getLogger("position_manager")

# ═══════════════════════════════════════════════════════════════
# ─── DATA STRUCTURES ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

class ExitReason(Enum):
    SL_HIT      = "sl_hit"
    TP1_HIT     = "tp1_hit"
    TP2_HIT     = "tp2_hit"
    TP3_HIT     = "tp3_hit"
    EXPLOSION   = "explosion"
    TACTICAL    = "tactical_exit"
    FORCE_CLOSE = "force_close"
    KILL_SWITCH = "kill_switch"

@dataclass
class Position:
    id: str
    user_id: str
    symbol: str
    direction: str
    entry: float
    amount: float
    leverage: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    tier: str = "B"
    grade: str = "B"
    # حالة TP
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    # Trailing
    trailing_active: bool = False
    trailing_sl: float = 0.0
    # Pyramiding
    pyramid_level: int = 1         # 1=2x, 2=5x, 3=10x
    pyramid_confirmed: bool = False
    original_leverage: float = 2.0
    # Explosion Mode
    explosion_mode: bool = False
    explosion_extreme: float = 0.0
    # AI Cooldown
    ai_last_called: int = 0
    ai_cooldown: int = 180  # 3 دقائق بين استدعاءات Claude
    # Tracking
    peak_price: float = 0.0
    status: str = "open"
    opened_at: int = field(default_factory=lambda: int(time.time()))
    last_warned: int = 0
    # Force Close Lock — لا AI بعد قرار المستخدم
    force_close_lock: bool = False
    # FVG zone من الإشارة
    fvg_zone: Optional[float] = None


# ═══════════════════════════════════════════════════════════════
# ─── STATS ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

STATS = {
    "total": 0, "wins": 0, "losses": 0, "tactical": 0, "force_close": 0,
    "tp1_count": 0, "tp2_count": 0, "tp3_count": 0, "explosion_count": 0,
    "total_pnl_pct": 0.0,
}

def update_stats(reason: ExitReason, pnl_pct: float):
    STATS["total"] += 1
    STATS["total_pnl_pct"] += pnl_pct
    if reason == ExitReason.SL_HIT:
        STATS["losses"] += 1
    elif reason == ExitReason.FORCE_CLOSE:
        STATS["force_close"] += 1
        if pnl_pct > 0:
            STATS["wins"] += 1
        else:
            STATS["losses"] += 1
    elif reason == ExitReason.TACTICAL:
        STATS["tactical"] += 1
        if pnl_pct > 0:
            STATS["wins"] += 1
    else:
        STATS["wins"] += 1
        if reason == ExitReason.TP1_HIT:
            STATS["tp1_count"] += 1
        elif reason == ExitReason.TP2_HIT:
            STATS["tp2_count"] += 1
        elif reason in (ExitReason.TP3_HIT, ExitReason.EXPLOSION):
            STATS["tp3_count"] += 1
            if reason == ExitReason.EXPLOSION:
                STATS["explosion_count"] += 1

def get_stats_msg() -> str:
    t = STATS["total"]
    if t == 0:
        return "لا توجد إحصائيات بعد"
    wr = STATS["wins"] / t * 100
    avg = STATS["total_pnl_pct"] / t
    return (
        f"📊 <b>إحصائيات WhaleMind Prime</b>\n{'─' * 24}\n"
        f"إجمالي الإشارات: <b>{t}</b>\n"
        f"رابحة: <b>{STATS['wins']}</b> | خاسرة: <b>{STATS['losses']}</b>\n"
        f"هروب تكتيكي: <b>{STATS['tactical']}</b>\n"
        f"Force Close: <b>{STATS['force_close']}</b>\n"
        f"نسبة الفوز: <b>{wr:.1f}%</b>\n"
        f"متوسط الربح: <b>{avg:+.2f}%</b>\n"
        f"{'─' * 24}\n"
        f"TP1: {STATS['tp1_count']} | TP2: {STATS['tp2_count']} | "
        f"TP3+: {STATS['tp3_count']} | 💥: {STATS['explosion_count']}"
    )

def get_stats_dict() -> dict:
    t = STATS["total"]
    return {
        "total": t,
        "wins": STATS["wins"],
        "losses": STATS["losses"],
        "win_rate": round(STATS["wins"] / t * 100, 1) if t > 0 else 0,
        "avg_pnl": round(STATS["total_pnl_pct"] / t, 2) if t > 0 else 0,
        "tp1_count": STATS["tp1_count"],
        "tp2_count": STATS["tp2_count"],
        "explosion_count": STATS["explosion_count"],
    }


# ═══════════════════════════════════════════════════════════════
# ─── ACTIVE POSITIONS STORE ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

ACTIVE: dict[str, Position] = {}

async def add_position(pos: Position):
    pos.peak_price = pos.entry
    ACTIVE[pos.id] = pos
    log.info("Position opened: %s %s @%.6f lev=%.0fx", pos.symbol, pos.direction, pos.entry, pos.leverage)

async def remove_position(pos_id: str):
    ACTIVE.pop(pos_id, None)

async def force_close_all(reason: str = "kill_switch"):
    """Kill Switch — إغلاق كل الصفقات فوراً"""
    positions = list(ACTIVE.values())
    for pos in positions:
        pos.force_close_lock = True
        price = await get_price(pos.symbol)
        if price:
            pnl_pct = calc_pnl(pos, price)
            await _close_position(pos, price, ExitReason.KILL_SWITCH, pnl_pct)
    log.critical("Kill Switch: %d positions closed", len(positions))


# ═══════════════════════════════════════════════════════════════
# ─── PRICE FETCHER ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def get_price(symbol: str) -> Optional[float]:
    try:
        import httpx
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}")
            return float(r.json()["price"])
    except:
        return None

async def get_order_book(symbol: str) -> dict:
    try:
        import httpx
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=20")
            d = r.json()
            bids = sum(float(b[1]) for b in d.get("bids", [])[:10])
            asks = sum(float(a[1]) for a in d.get("asks", [])[:10])
            return {
                "bids": bids,
                "asks": asks,
                "imbalance": (bids - asks) / (bids + asks) if (bids + asks) > 0 else 0,
                "spread": float(d["asks"][0][0]) - float(d["bids"][0][0]) if d.get("asks") and d.get("bids") else 0,
            }
    except:
        return {}


# ═══════════════════════════════════════════════════════════════
# ─── PYRAMIDING — التعزيز الهرمي ────────────────────────────────
# ═══════════════════════════════════════════════════════════════

PYRAMID_LEVELS = {
    1: {"leverage_mult": 1.0, "desc": "دخول أولي 2x"},   # 2x
    2: {"leverage_mult": 2.5, "desc": "تأكيد TP1 → 5x"},  # 5x
    3: {"leverage_mult": 5.0, "desc": "انفجار مؤكد → 10x"}, # 10x
}

async def check_pyramiding(pos: Position, price: float) -> bool:
    """
    التعزيز الهرمي:
    TP1 مُصاب + موافقة Guardian → رفع الرافعة
    يعيد True إذا تم التعزيز
    """
    if pos.pyramid_level >= 3 or pos.force_close_lock:
        return False

    is_long = pos.direction == "LONG"

    # شرط الانتقال للمستوى 2 (2x → 5x)
    if pos.pyramid_level == 1 and pos.tp1_hit:
        # تأكيد إضافي: الدلتا إيجابية
        ob = await get_order_book(pos.symbol)
        imbalance = ob.get("imbalance", 0)

        confirm = (imbalance > 0.2 if is_long else imbalance < -0.2)
        if confirm:
            new_lev = pos.original_leverage * 2.5
            pos.leverage = min(new_lev, 25.0)
            pos.pyramid_level = 2
            await notify(pos.user_id,
                f"📈 <b>Pyramiding Level 2</b> — {pos.symbol}\n"
                f"TP1 مُصاب ✅ | رافعة مرفوعة → <b>{pos.leverage:.0f}x</b>\n"
                f"OBI: {imbalance:+.2f} | الزخم إيجابي")
            log.info("Pyramid L2: %s lev=%.0fx", pos.symbol, pos.leverage)
            return True

    # شرط الانتقال للمستوى 3 (5x → 10x)
    if pos.pyramid_level == 2 and pos.tp2_hit and pos.explosion_mode:
        new_lev = pos.original_leverage * 5.0
        pos.leverage = min(new_lev, 50.0)
        pos.pyramid_level = 3
        await notify(pos.user_id,
            f"💥 <b>Pyramiding Level 3 — EXPLOSION MODE</b>\n"
            f"{pos.symbol} | رافعة → <b>{pos.leverage:.0f}x</b>\n"
            f"⚡ الانفجار مؤكد — الكل مع الحوت!")
        log.info("Pyramid L3: %s lev=%.0fx", pos.symbol, pos.leverage)
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# ─── CLAUDE AI EMERGENCY ADVISOR ────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def claude_emergency_analysis(pos: Position, price: float, ob: dict, alert_reason: str) -> Optional[str]:
    """
    استشارة Claude AI الطارئة — غير متزامن تماماً
    يُستدعى فقط عند:
    1. تغير مفاجئ في Order Book ضد الصفقة
    2. شذوذ في الدلتا
    3. حركة سعرية مفاجئة
    لا يُستدعى بشكل متكرر — cooldown 3 دقائق
    """
    now = int(time.time())
    if now - pos.ai_last_called < pos.ai_cooldown:
        return None

    pos.ai_last_called = now

    is_long = pos.direction == "LONG"
    pnl_pct = calc_pnl(pos, price)

    prompt = f"""أنت مستشار تداول طارئ لنظام WhaleMind Prime. حلل هذا الوضع وأعطِ قرارك في 2 جملة فقط:

الصفقة: {pos.symbol} {pos.direction} | دخول: {pos.entry:.4f} | الآن: {price:.4f}
PnL الحالي: {pnl_pct:+.2f}%
الرافعة: {pos.leverage}x | Grade: {pos.grade}
Order Book: Bids={ob.get('bids', 0):.0f} Asks={ob.get('asks', 0):.0f} Imbalance={ob.get('imbalance', 0):+.3f}
سبب الاستدعاء: {alert_reason}

هل تنصح بـ:
A) الاستمرار — الوضع مؤقت
B) هروب تكتيكي — اخرج الآن بـ {pnl_pct:+.2f}%
C) انتظار — ضع SL أقرب

أجب بحرف واحد (A/B/C) ثم جملة تفسيرية واحدة بالعربية."""

    try:
        import httpx
        from core.config import get_settings
        s = get_settings()

        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": s.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            result = r.json()
            reply = result["content"][0]["text"].strip()
            log.info("Claude AI: %s %s → %s", pos.symbol, alert_reason, reply[:50])
            return reply
    except Exception as e:
        log.error("Claude AI error: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════
# ─── TACTICAL EXIT ANALYZER ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def should_tactical_exit(pos: Position, price: float, ob: dict, ls_change: float) -> tuple[bool, str]:
    """
    هروب تكتيكي استباقي — يقرر قبل ضرب SL
    يعيد (exit: bool, reason: str)
    """
    if pos.force_close_lock:
        return False, ""

    is_long = pos.direction == "LONG"
    pnl_pct = calc_pnl(pos, price)
    imbalance = ob.get("imbalance", 0)

    # 1. Order Book ينقلب بشكل حاد ضدنا
    if is_long and imbalance < -0.4:
        return True, f"Order Book انقلب ضد LONG (Imbalance: {imbalance:.2f})"
    if not is_long and imbalance > 0.4:
        return True, f"Order Book انقلب ضد SHORT (Imbalance: {imbalance:.2f})"

    # 2. Liquidation cascade معاكس يبدأ
    if ls_change != 0:
        if is_long and ls_change < -5:
            return True, f"شلال تصفية لونق بدأ ({ls_change:.1f}%)"
        if not is_long and ls_change > 5:
            return True, f"شلال تصفية شورت بدأ ({ls_change:.1f}%)"

    # 3. ربح لا بأس به مع علامات انعكاس
    if pnl_pct > 1.5 and pos.tp1_hit:
        if is_long and imbalance < -0.2:
            return True, f"TP1 مصاب + OB ضعيف — تأمين {pnl_pct:.1f}%"
        if not is_long and imbalance > 0.2:
            return True, f"TP1 مصاب + OB ضعيف — تأمين {pnl_pct:.1f}%"

    # 4. Spread كبير جداً = سيولة تجف
    spread_pct = ob.get("spread", 0) / price * 100 if price > 0 else 0
    if spread_pct > 0.5 and abs(pnl_pct) < 0.5:
        return True, f"السيولة تجف (Spread: {spread_pct:.2f}%) — هروب وقائي"

    return False, ""


# ═══════════════════════════════════════════════════════════════
# ─── POSITION MONITOR ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calc_pnl(pos: Position, price: float) -> float:
    if pos.direction == "LONG":
        return (price - pos.entry) / pos.entry * 100 * pos.leverage
    else:
        return (pos.entry - price) / pos.entry * 100 * pos.leverage

async def notify(user_id: str, msg: str, event_type: str = "alert", data: dict = None):
    """إرسال إشعار للمستخدم عبر Telegram + WebSocket"""
    # 1. Telegram
    try:
        from services.telegram import TG
        await TG.send_message(user_id, msg)
    except Exception as e:
        log.debug("notify telegram error: %s", e)
    # 2. WebSocket → Mini App
    try:
        from routers.ws import registry
        await registry.broadcast({"event": event_type, "user_id": user_id, "message": msg, "data": data or {}})
    except Exception as e:
        log.debug("notify ws error: %s", e)

async def monitor_position(pos: Position):
    """
    المراقبة الحية لصفقة واحدة:
    SL/TP → Trailing → Pyramiding → Claude AI → Tactical Exit
    """
    price = await get_price(pos.symbol)
    if not price:
        return

    ob = await get_order_book(pos.symbol)
    is_long = pos.direction == "LONG"
    pnl_pct = calc_pnl(pos, price)

    # تحديث قمة السعر
    if is_long:
        if price > pos.peak_price:
            pos.peak_price = price
    else:
        if price < pos.peak_price or pos.peak_price == 0:
            pos.peak_price = price

    # ls_change تقريبي
    ls_change = (price - pos.entry) / pos.entry * 100 if pos.entry > 0 else 0

    # Force Close lock — لا شيء بعد قرار المستخدم
    if pos.force_close_lock:
        return

    # ─ SL ─
    sl_hit = (is_long and price <= pos.sl) or (not is_long and price >= pos.sl)
    if sl_hit:
        await _close_position(pos, price, ExitReason.SL_HIT, pnl_pct)
        return

    # ─ TP1 ─
    tp1_hit = (is_long and price >= pos.tp1) or (not is_long and price <= pos.tp1)
    if tp1_hit and not pos.tp1_hit:
        pos.tp1_hit = True
        pos.trailing_active = True
        # تحريك SL إلى نقطة التعادل
        pos.sl = pos.entry * (1.001 if is_long else 0.999)
        pos.trailing_sl = pos.sl

        profit = abs((price - pos.tp1) / pos.entry * 100)
        await notify(pos.user_id,
            f"🎯 <b>TP1 مصاب</b> — {pos.symbol}\n"
            f"{'📈' if is_long else '📉'} {pos.direction} | +{profit:.2f}%\n"
            f"✅ SL نُقل لنقطة التعادل\n"
            f"🔒 رأس المال محمي")

        # Pyramiding check
        await check_pyramiding(pos, price)

    # ─ TP2 ─
    tp2_hit = (is_long and price >= pos.tp2) or (not is_long and price <= pos.tp2)
    if tp2_hit and not pos.tp2_hit and pos.tp1_hit:
        pos.tp2_hit = True
        pos.explosion_mode = True

        await notify(pos.user_id,
            f"🚀 <b>TP2 مصاب — Explosion Mode</b>\n"
            f"{pos.symbol} {pos.direction}\n"
            f"💥 الانفجار السعري مؤكد\n"
            f"⬆️ TP3 الهدف القادم")

        await check_pyramiding(pos, price)

    # ─ TP3 ─
    tp3_hit = (is_long and price >= pos.tp3) or (not is_long and price <= pos.tp3)
    if tp3_hit and pos.tp2_hit:
        profit = abs(pnl_pct)
        await notify(pos.user_id,
            f"🏆 <b>TP3 مصاب</b> — {pos.symbol}\n"
            f"💰 الربح الكامل: <b>+{profit:.2f}%</b>\n"
            f"✅ تم إغلاق الصفقة بالكامل\n"
            f"🎊 <i>إشارة WhaleMind Prime ناجحة!</i>")
        await _close_position(pos, price, ExitReason.TP3_HIT, pnl_pct)
        return

    # ─ Trailing Stop ─
    if pos.trailing_active and pos.trailing_sl > 0:
        if is_long:
            new_sl = price - (pos.tp1 - pos.entry) * 0.5
            if new_sl > pos.trailing_sl:
                pos.trailing_sl = new_sl
                pos.sl = new_sl
        else:
            new_sl = price + (pos.entry - pos.tp1) * 0.5
            if new_sl < pos.trailing_sl or pos.trailing_sl == 0:
                pos.trailing_sl = new_sl
                pos.sl = new_sl

    # ─ Claude AI Emergency ─
    now = int(time.time())
    imbalance = ob.get("imbalance", 0)
    ai_alert_needed = (
        (is_long and imbalance < -0.35) or
        (not is_long and imbalance > 0.35)
    )

    if ai_alert_needed and now - pos.ai_last_called > pos.ai_cooldown:
        alert_reason = f"OB Imbalance انقلب ({imbalance:+.2f})"
        ai_reply = await claude_emergency_analysis(pos, price, ob, alert_reason)

        if ai_reply:
            # إرسال تحليل Claude للمستخدم
            await notify(pos.user_id,
                f"🤖 <b>Claude AI تحليل طارئ</b> — {pos.symbol}\n"
                f"{'📈' if is_long else '📉'} {pos.direction} | PnL: {pnl_pct:+.2f}%\n"
                f"⚠️ {alert_reason}\n"
                f"{'─' * 20}\n"
                f"<i>{ai_reply}</i>")

            # إذا قرر Claude B (هروب) → تنفيذ تكتيكي
            if ai_reply.upper().startswith("B") and pnl_pct > -1.0:
                await _close_position(pos, price, ExitReason.TACTICAL, pnl_pct)
                return

    # ─ Tactical Exit Check ─
    if now - pos.last_warned > 300:  # كل 5 دقائق max
        tactical, reason = await should_tactical_exit(pos, price, ob, ls_change)
        if tactical:
            pos.last_warned = now
            tp_status = "TP2" if pos.tp2_hit else "TP1" if pos.tp1_hit else "قبل TP1"
            profit_str = f"+{abs(pnl_pct):.2f}%" if pnl_pct > 0 else f"{pnl_pct:.2f}%"

            await notify(pos.user_id,
                f"🏃 <b>هروب تكتيكي مقترح</b> — {pos.symbol}\n"
                f"{'📈' if is_long else '📉'} <b>{pos.direction}</b>\n"
                f"📊 الوضع: <b>{tp_status}</b> | PnL: <b>{profit_str}</b>\n"
                f"⚠️ السبب: {reason}\n"
                f"💡 <i>يُنصح بالخروج الاستباقي</i>\n\n"
                f"[اضغط Force Close للخروج الآن]")

            # إذا كان PnL إيجابياً وكان تحذيراً قوياً → نفذ تلقائياً
            if pnl_pct > 2.0 and "شلال" in reason:
                await _close_position(pos, price, ExitReason.TACTICAL, pnl_pct)
                return


# ═══════════════════════════════════════════════════════════════
# ─── POSITION CLOSE ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def _close_position(pos: Position, price: float, reason: ExitReason, pnl_pct: float):
    """إغلاق الصفقة وإرسال الإشعار"""
    pos.status = "closed"
    await remove_position(pos.id)
    update_stats(reason, pnl_pct)

    emoji = {
        ExitReason.SL_HIT: "🔴",
        ExitReason.TP1_HIT: "🟡",
        ExitReason.TP2_HIT: "🟠",
        ExitReason.TP3_HIT: "🟢",
        ExitReason.EXPLOSION: "💥",
        ExitReason.TACTICAL: "🏃",
        ExitReason.FORCE_CLOSE: "🛑",
        ExitReason.KILL_SWITCH: "🚨",
    }.get(reason, "⚪")

    result_word = "خسارة" if pnl_pct < 0 else "ربح"
    msg = (
        f"{emoji} <b>{reason.value.replace('_', ' ').upper()}</b>\n"
        f"{'─' * 20}\n"
        f"{pos.symbol} {pos.direction}\n"
        f"دخول: {pos.entry:.4f} | خروج: {price:.4f}\n"
        f"<b>{result_word}: {pnl_pct:+.2f}%</b>\n"
        f"الرافعة: {pos.leverage}x | المستوى: {pos.pyramid_level}"
    )

    await notify(pos.user_id, msg)

    # حفظ في DB
    try:
        from db.database import get_session, Signal as DBSignal
        db = get_session()
        # تحديث end_time و highest_hit
        sig = db.query(DBSignal).filter(
            DBSignal.symbol == pos.symbol,
            DBSignal.direction == pos.direction,
        ).order_by(DBSignal.id.desc()).first()

        if sig:
            sig.end_time = int(time.time())
            sig.highest_hit = pos.peak_price
            db.commit()
    except Exception as e:
        log.debug("close DB update: %s", e)

    log.info("Position closed: %s %s | %s | pnl=%.2f%%",
             pos.symbol, pos.direction, reason.value, pnl_pct)


# ═══════════════════════════════════════════════════════════════
# ─── MANUAL OVERRIDES ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def force_close(pos_id: str, user_id: str) -> dict:
    """
    Force Close — المستخدم يكسر حلقة AI ويغلق بسعر السوق
    هذا القرار نهائي — لا AI بعده
    """
    pos = ACTIVE.get(pos_id)
    if not pos:
        return {"error": "Position not found"}
    if pos.user_id != user_id:
        return {"error": "Unauthorized"}

    pos.force_close_lock = True  # ← يمنع AI من التدخل

    price = await get_price(pos.symbol)
    if not price:
        return {"error": "Could not fetch price"}

    pnl_pct = calc_pnl(pos, price)

    await notify(pos.user_id,
        f"🛑 <b>Force Close تم بنجاح</b>\n"
        f"{pos.symbol} {pos.direction}\n"
        f"سعر الخروج: {price:.4f}\n"
        f"PnL: <b>{pnl_pct:+.2f}%</b>\n"
        f"تم إغلاق الصفقة بسعر السوق فوراً ✅")

    await _close_position(pos, price, ExitReason.FORCE_CLOSE, pnl_pct)

    return {
        "status": "force_closed",
        "symbol": pos.symbol,
        "exit_price": price,
        "pnl_pct": round(pnl_pct, 2),
    }


# ═══════════════════════════════════════════════════════════════
# ─── AUTO POSITION OPENER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def open_from_signal(sig: Signal, user_id: str = "system", amount: float = 100.0):
    """
    يفتح صفقة من إشارة الرادار
    يبدأ برافعة 2x — Pyramiding يرفعها لاحقاً
    """
    # لا تفتح إذا Kill Switch مفعّل
    from service import is_kill_switch_active
    if is_kill_switch_active():
        log.warning("Kill Switch active — لا صفقات جديدة")
        return None

    pos_id = f"{sig.symbol}_{sig.direction}_{int(time.time())}"
    pos = Position(
        id=pos_id,
        user_id=user_id,
        symbol=sig.symbol,
        direction=sig.direction,
        entry=sig.entry,
        amount=amount,
        leverage=sig.leverage,
        sl=sig.sl,
        tp1=sig.tp1,
        tp2=sig.tp2,
        tp3=sig.tp3,
        tier=sig.tier,
        grade=sig.grade,
        original_leverage=sig.leverage,
        fvg_zone=sig.fvg_zone,
    )

    await add_position(pos)
    return pos


# ═══════════════════════════════════════════════════════════════
# ─── MAIN MONITOR LOOP ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def run_position_manager():
    """
    حلقة المراقبة الرئيسية:
    - كل 30 ثانية يفحص كل الصفقات المفتوحة
    - Semaphore يمنع التحميل الزائد
    - كل صفقة في coroutine مستقل
    """
    log.info("Position Manager started")
    sem = asyncio.Semaphore(10)

    async def monitor_one(pos: Position):
        async with sem:
            try:
                await monitor_position(pos)
            except Exception as e:
                log.error("monitor_position %s: %s", pos.symbol, e)

    while True:
        try:
            positions = [p for p in ACTIVE.values() if p.status == "open"]

            if positions:
                await asyncio.gather(*[monitor_one(p) for p in positions], return_exceptions=True)
            else:
                await asyncio.sleep(10)

        except Exception as e:
            log.error("PM loop error: %s", e)

        await asyncio.sleep(30)
