from __future__ import annotations
import asyncio, logging
from typing import Any, Dict, Optional
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
from core.config import get_settings

log = logging.getLogger("telegram")
TG_API = "https://api.telegram.org/bot{token}/{method}"

async def _call(method: str, payload: Dict[str, Any]) -> Optional[dict]:
    s = get_settings()
    if not s.telegram_bot_token or not HAS_HTTPX:
        return None
    url = TG_API.format(token=s.telegram_bot_token, method=method)
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json=payload)
            return r.json()
    except Exception as e:
        log.debug("TG error: %s", e)
        return None

async def send_message(chat_id: str, text: str, reply_markup=None) -> Optional[dict]:
    p: Dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        p["reply_markup"] = reply_markup
    return await _call("sendMessage", p)

async def set_webhook(url: str):
    return await _call("setWebhook", {"url": url, "allowed_updates": ["message"], "drop_pending_updates": True})

async def set_commands():
    return await _call("setMyCommands", {"commands": [
        {"command": "start",   "description": "فتح WhaleX Prime"},
        {"command": "status",  "description": "حالة الرادارات"},
        {"command": "signals", "description": "آخر الإشارات"},
        {"command": "demo",    "description": "حساب الديمو"},
        {"command": "help",    "description": "المساعدة"},
    ]})

def _kb():
    s = get_settings()
    u = s.telegram_mini_app_url or ""
    if not u:
        return {}
    return {"inline_keyboard": [[{"text": "فتح WhaleX Prime", "web_app": {"url": u}}]]}

def signal_msg(s: dict) -> str:
    radar = s.get("radar_type", "futures").upper()
    sym   = s.get("symbol", "")
    dir_  = s.get("direction", "")
    grade = s.get("grade", "B")
    conf  = s.get("confidence", 0)
    entry = s.get("entry", 0)
    sl    = s.get("sl", 0)
    tp1   = s.get("tp1", 0)
    tp2   = s.get("tp2", 0)
    tp3   = s.get("tp3", 0)
    lev   = s.get("leverage", 1)
    strats= s.get("strategies", "")
    e = "🟢" if "LONG" in dir_ else "🔴"
    grade_emoji = {"S": "💎", "A": "🥇", "B": "🥈", "C": "🥉"}.get(grade, "📊")

    return (
        f"⚡ <b>إشارة {radar} - {sym}</b>\n"
        f"{'-'*20}\n"
        f"{e} <b>{dir_}</b> | {grade_emoji} Grade: <b>{grade}</b>\n"
        f"📊 الثقة: <b>{conf:.0f}%</b>\n"
        f"{'-'*20}\n"
        f"🎯 الدخول: <code>{entry}</code>\n"
        f"🛡 SL: <code>{sl}</code>\n"
        f"🎪 TP1: <code>{tp1}</code>\n"
        f"🎪 TP2: <code>{tp2}</code>\n"
        f"🎪 TP3: <code>{tp3}</code>\n"
        f"⚡ الرافعة: <b>{lev}x</b>\n"
        f"{'-'*20}\n"
        f"📋 {strats[:100] if strats else ''}\n"
        f"<i>⚠️ ليست نصيحة مالية</i>"
    )

class TelegramService:
    def __init__(self): self._running = False

    async def setup(self):
        s = get_settings()
        if not s.telegram_bot_token:
            log.warning("TELEGRAM_BOT_TOKEN not set")
            return
        await set_commands()
        log.info("Telegram bot ready")
        if s.telegram_admin_chat_id:
            await send_message(s.telegram_admin_chat_id,
                "🟢 <b>WhaleX Prime online</b>\n"
                "Futures Radar ✅\nSpot Radar ✅\nMeme Radar ✅\nTelegram Bridge ✅",
                reply_markup=_kb())

    async def handle_update(self, update: dict):
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()
        name = msg.get("from", {}).get("first_name", "مستخدم")
        if not text or not chat_id:
            return
        if text.startswith("/start"):
            await send_message(chat_id,
                f"👋 <b>اهلاً {name}!</b>\n\n"
                "🐋 <b>WhaleX Prime</b>\n"
                "منصة تداول ذكية متكاملة\n\n"
                "• 3 رادارات: Futures / Spot / Meme\n"
                "• محفظة متعددة الشبكات\n"
                "• AI مساعد للتداول\n"
                "• Demo Account $10,000\n\n"
                "/signals - آخر الإشارات\n"
                "/status - حالة الرادارات\n"
                "/demo - حساب الديمو",
                reply_markup=_kb())
        elif text.startswith("/status"):
            await send_message(chat_id,
                "📊 <b>حالة WhaleX Prime</b>\n\n"
                "🔴 Futures Radar: <b>نشط</b>\n"
                "🟡 Spot Radar: <b>نشط</b>\n"
                "🟣 Meme Radar: <b>نشط</b>\n"
                "🤖 AI Assistant: <b>نشط</b>",
                reply_markup=_kb())
        elif text.startswith("/help"):
            await send_message(chat_id,
                "/start - رسالة الترحيب\n"
                "/signals - آخر الإشارات\n"
                "/status - حالة الرادارات\n"
                "/demo - إحصائيات الديمو",
                reply_markup=_kb())

    async def broadcast_signal(self, sig: dict):
        s = get_settings()
        radar = sig.get("radar_type", "futures")
        channel = {
            "futures": s.telegram_channel_futures,
            "spot":    s.telegram_channel_spot,
            "meme":    s.telegram_channel_meme,
        }.get(radar, "")
        if channel:
            await send_message(channel, signal_msg(sig), reply_markup=_kb())

TG = TelegramService()
