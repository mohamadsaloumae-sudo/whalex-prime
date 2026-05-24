"""
WhaleMind-Prime-Core — engine.py
═══════════════════════════════════════════════════════════════════
عقل النظام: ثلاثة وكلاء مستقلون يتواصلون عبر asyncio.Queue (Redis-ready)

الوكيل 1 — Predator Agent  : صائد السيولة اللحظي (CVD + Delta + FVG + Stop Hunts)
الوكيل 2 — Sleeping Giants : رادار التجميع الصامت (يومي/أسبوعي)
الوكيل 3 — Guardian Agent  : القاضي — المنع القاطع + تحديد الرافعة

معمارية بلا اختناق:
- كل وكيل يعمل في coroutine مستقل
- التواصل عبر asyncio.Queue (non-blocking)
- Guardian لا يوقف Predator — يقرأ من queue ويضيف للنتائج
- Shadow Mode يسجل صامتاً في background task منفصل
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time, json
from dataclasses import dataclass, field
from typing import Optional
import math

log = logging.getLogger("engine")

# ═══════════════════════════════════════════════════════════════
# ─── DATA STRUCTURES ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float = 0.0

@dataclass
class MarketTier:
    symbol: str
    volume_24h: float
    tier: str          # S | A | B
    max_leverage: float
    min_score: float
    min_confidence: float

@dataclass
class Signal:
    symbol: str
    direction: str        # LONG | SHORT
    grade: str            # S | A | B | C
    score: float
    confidence: float
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    leverage: float
    strategies: str
    radar_type: str = "futures"
    tier: str = "B"
    timestamp: int = field(default_factory=lambda: int(time.time()))
    # حقول إضافية لمنع DB crash
    end_time: Optional[int] = None
    highest_hit: Optional[float] = None
    fvg_zone: Optional[float] = None
    liquidation_signal: bool = False
    waiting_room: bool = False

@dataclass
class ShadowTrade:
    """صفقة وهمية للمتدرب الصامت"""
    symbol: str
    direction: str
    entry: float
    sl: float
    tp1: float
    strategies: str
    score: float
    confidence: float
    timestamp: int = field(default_factory=lambda: int(time.time()))
    # تُحدَّث لاحقاً
    result: Optional[str] = None    # WIN | LOSS | OPEN
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    closed_at: Optional[int] = None

# ═══════════════════════════════════════════════════════════════
# ─── INDICATORS ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def ema(data: list[float], period: int) -> list[float]:
    if len(data) < period:
        return [None] * len(data)
    result, k = [], 2 / (period + 1)
    e = sum(data[:period]) / period
    result = [None] * (period - 1) + [e]
    for i in range(period, len(data)):
        e = data[i] * k + e * (1 - k)
        result.append(e)
    return result

def rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)

def macd(closes: list[float]):
    if len(closes) < 26:
        return 0, 0, 0
    e12 = ema(closes, 12)
    e26 = ema(closes, 26)
    ml = [a - b for a, b in zip(e12[25:], e26[25:]) if a and b]
    if len(ml) < 9:
        return 0, 0, 0
    sl = ema(ml, 9)
    m, s = ml[-1], sl[-1] if sl[-1] else 0
    return m, s, m - s

def bollinger(closes: list[float], period: int = 20, std_mult: float = 2.0):
    if len(closes) < period:
        p = closes[-1]
        return p, p, p, 0
    sl = closes[-period:]
    m = sum(sl) / period
    variance = sum((x - m) ** 2 for x in sl) / period
    s = math.sqrt(variance)
    return m + std_mult * s, m, m - std_mult * s, s

def atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return candles[-1].close * 0.02
    trs = []
    for i in range(1, len(candles)):
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close)
        )
        trs.append(tr)
    return sum(trs[-period:]) / period

def stoch_rsi(closes: list[float], period: int = 14) -> tuple[float, float]:
    if len(closes) < period * 2:
        return 50.0, 50.0
    rsi_vals = []
    for i in range(period, len(closes)):
        rsi_vals.append(rsi(closes[:i + 1], period))
    if len(rsi_vals) < period:
        return 50.0, 50.0
    r = rsi_vals[-1]
    mn, mx = min(rsi_vals[-period:]), max(rsi_vals[-period:])
    if mx == mn:
        return 50.0, 50.0
    k = (r - mn) / (mx - mn) * 100
    d = k  # تبسيط — يمكن استخدام EMA(k,3)
    return k, d

def vwap(candles: list[Candle]) -> float:
    total_pv = sum(((c.high + c.low + c.close) / 3) * c.volume for c in candles)
    total_v = sum(c.volume for c in candles)
    return total_pv / total_v if total_v > 0 else candles[-1].close

# ═══════════════════════════════════════════════════════════════
# ─── LIE DETECTOR — CVD & DELTA ────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def cvd(candles: list[Candle]) -> float:
    """Cumulative Volume Delta — جهاز كشف الكذب"""
    total = 0.0
    for c in candles[-30:]:
        sell_vol = c.volume - c.buy_volume
        total += c.buy_volume - sell_vol
    return total

def delta_flow(candles: list[Candle]) -> float:
    """Delta آخر 5 شموع — يكشف من يسيطر فعلاً"""
    if len(candles) < 5:
        return 0.0
    recent = candles[-5:]
    delta = sum(c.buy_volume - (c.volume - c.buy_volume) for c in recent)
    return delta

def cvd_divergence(candles: list[Candle]) -> tuple[str, float]:
    """
    كاشف الكذب الرئيسي:
    سعر يصعد + CVD يهبط = بيع خفي (إشارة SHORT)
    سعر يهبط + CVD يصعد = شراء خفي (إشارة LONG)
    يعيد: (direction_hint, strength 0-3)
    """
    if len(candles) < 20:
        return "", 0.0

    # حساب CVD للنصف الأول والثاني
    mid = len(candles) // 2
    cvd_first = cvd(candles[:mid])
    cvd_last = cvd(candles[mid:])
    cvd_trend = cvd_last - cvd_first

    price_first = candles[mid].close
    price_last = candles[-1].close
    price_trend = price_last - price_first

    # تطبيع
    p_norm = (price_trend / price_first) * 100 if price_first > 0 else 0
    cvd_avg = sum(c.volume for c in candles[-20:]) / 20
    c_norm = cvd_trend / cvd_avg if cvd_avg > 0 else 0

    # تباين = كذب
    if p_norm > 0.3 and c_norm < -0.1:
        strength = min(3.0, abs(c_norm) * 2)
        return "SHORT", strength   # سعر يصعد + CVD ينزل = تصريف خفي

    if p_norm < -0.3 and c_norm > 0.1:
        strength = min(3.0, abs(c_norm) * 2)
        return "LONG", strength    # سعر ينزل + CVD يصعد = تجميع خفي

    return "", 0.0

# ═══════════════════════════════════════════════════════════════
# ─── ANTI-SPOOFING ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def obi(candles: list[Candle]) -> float:
    """Order Book Imbalance approximation من بيانات الكاندل"""
    if len(candles) < 5:
        return 0.0
    buy_pressure = sum(c.buy_volume for c in candles[-5:])
    sell_pressure = sum((c.volume - c.buy_volume) for c in candles[-5:])
    total = buy_pressure + sell_pressure
    return (buy_pressure - sell_pressure) / total if total > 0 else 0.0

def detect_spoofing(candles: list[Candle]) -> bool:
    """
    يكشف الجدران الوهمية:
    حجم كبير جداً في شمعة واحدة بدون حركة سعرية مناسبة = Spoofing
    """
    if len(candles) < 10:
        return False
    avg_vol = sum(c.volume for c in candles[-10:]) / 10
    last = candles[-1]
    price_move = abs(last.close - last.open) / last.open * 100
    # حجم أكبر من 3x المتوسط مع حركة سعرية أقل من 0.3% = مشبوه
    if last.volume > avg_vol * 3 and price_move < 0.3:
        return True
    return False

# ═══════════════════════════════════════════════════════════════
# ─── FVG — FAIR VALUE GAPS ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def find_fvg(candles: list[Candle]) -> list[dict]:
    """
    كشف فجوات القيمة العادلة (Imbalance) — مناطق المغناطيس
    FVG يحدث عندما: high[i-2] < low[i] أو low[i-2] > high[i]
    """
    fvgs = []
    for i in range(2, len(candles)):
        c0, c1, c2 = candles[i - 2], candles[i - 1], candles[i]
        # Bullish FVG
        if c0.high < c2.low:
            fvgs.append({
                "type": "bullish",
                "top": c2.low,
                "bottom": c0.high,
                "mid": (c2.low + c0.high) / 2,
                "index": i
            })
        # Bearish FVG
        elif c0.low > c2.high:
            fvgs.append({
                "type": "bearish",
                "top": c0.low,
                "bottom": c2.high,
                "mid": (c0.low + c2.high) / 2,
                "index": i
            })
    # فقط آخر 5 FVGs
    return fvgs[-5:] if fvgs else []

def price_near_fvg(price: float, fvgs: list[dict], tolerance: float = 0.005) -> Optional[dict]:
    """هل السعر قريب من FVG؟"""
    for fvg in reversed(fvgs):
        mid = fvg["mid"]
        if abs(price - mid) / mid < tolerance:
            return fvg
    return None

# ═══════════════════════════════════════════════════════════════
# ─── LIQUIDATION CASCADE DETECTOR ─────────────────────────────
# ═══════════════════════════════════════════════════════════════

def detect_liquidation_cascade(candles: list[Candle]) -> tuple[bool, str]:
    """
    يكشف شلالات التصفية:
    سقوط/صعود حر مع حجم انفجاري = تصفية قطيع
    الاستراتيجية: انتظر نهاية الشلال واركب الارتداد
    """
    if len(candles) < 5:
        return False, ""

    recent = candles[-5:]
    avg_vol = sum(c.volume for c in candles[-20:-5]) / 15 if len(candles) > 20 else 1

    # حجم الشموع الأخيرة
    recent_vol = sum(c.volume for c in recent)
    vol_ratio = recent_vol / (avg_vol * 5) if avg_vol > 0 else 0

    # حساب الحركة السعرية
    price_move = (recent[-1].close - recent[0].open) / recent[0].open * 100

    if vol_ratio > 2.5 and price_move < -3.0:
        # سقوط حر مع حجم ضخم = تصفية شورت → فرصة LONG
        return True, "LONG"
    if vol_ratio > 2.5 and price_move > 3.0:
        # صعود صاروخي مع حجم ضخم = تصفية لونق → فرصة SHORT
        return True, "SHORT"

    return False, ""

# ═══════════════════════════════════════════════════════════════
# ─── STOP HUNT DETECTOR ────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def detect_stop_hunt(candles: list[Candle]) -> tuple[bool, str]:
    """
    يكشف صيد الستوبات:
    كسر قمة/قاع مع فشل الإغلاق فوق/تحته = فخ
    """
    if len(candles) < 10:
        return False, ""

    recent = candles[-10:]
    highs = [c.high for c in recent[:-2]]
    lows = [c.low for c in recent[:-2]]

    last = recent[-1]
    prev_high = max(highs)
    prev_low = min(lows)

    # كسر قمة لكن أغلق تحتها = Bull Trap → SHORT
    if last.high > prev_high and last.close < prev_high:
        wick_ratio = (last.high - last.close) / (last.high - last.low) if (last.high - last.low) > 0 else 0
        if wick_ratio > 0.6:
            return True, "SHORT"

    # كسر قاع لكن أغلق فوقه = Bear Trap → LONG
    if last.low < prev_low and last.close > prev_low:
        wick_ratio = (last.close - last.low) / (last.high - last.low) if (last.high - last.low) > 0 else 0
        if wick_ratio > 0.6:
            return True, "LONG"

    return False, ""

# ═══════════════════════════════════════════════════════════════
# ─── ORDER BLOCK DETECTOR ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def find_order_blocks(candles: list[Candle]) -> list[dict]:
    """
    الشموع الابتلاعية ذات السيولة العالية = Order Blocks
    تعمل كمناطق دعم/مقاومة قوية
    """
    obs = []
    avg_vol = sum(c.volume for c in candles) / len(candles) if candles else 1

    for i in range(1, len(candles) - 1):
        c = candles[i]
        # شمعة ابتلاعية مع حجم فوق المتوسط × 1.5
        if c.volume > avg_vol * 1.5:
            body = abs(c.close - c.open)
            range_ = c.high - c.low
            if range_ > 0 and body / range_ > 0.6:  # جسم كبير
                obs.append({
                    "type": "bullish" if c.close > c.open else "bearish",
                    "top": max(c.open, c.close),
                    "bottom": min(c.open, c.close),
                    "mid": (c.high + c.low) / 2,
                    "index": i
                })
    return obs[-5:] if obs else []

# ═══════════════════════════════════════════════════════════════
# ─── SLEEPING GIANTS (DAILY RADAR) ─────────────────────────────
# ═══════════════════════════════════════════════════════════════

def sleeping_giant_score(candles: list[Candle]) -> float:
    """
    رادار التجميع الصامت — يبحث عن:
    1. تذبذب ضيق (سعر ميت)
    2. ضغط بولينجر (Volatility Squeeze)
    3. أعمدة شراء خفية (حجم شرائي خفي)
    4. امتصاص جدران البيع
    يعيد: score 0-10
    """
    if len(candles) < 20:
        return 0.0

    score = 0.0
    closes = [c.close for c in candles]

    # 1. تذبذب ضيق — نطاق السعر خلال 20 شمعة
    recent_high = max(c.high for c in candles[-20:])
    recent_low = min(c.low for c in candles[-20:])
    price_range_pct = (recent_high - recent_low) / recent_low * 100
    if price_range_pct < 5.0:
        score += 3.0   # تذبذب ضيق جداً
    elif price_range_pct < 8.0:
        score += 1.5

    # 2. ضغط بولينجر (Squeeze)
    bb_u, bb_m, bb_l, bb_std = bollinger(closes)
    bb_width = (bb_u - bb_l) / bb_m * 100 if bb_m > 0 else 0
    if bb_width < 3.0:
        score += 3.0   # ضغط شديد = انفجار وشيك
    elif bb_width < 5.0:
        score += 1.5

    # 3. حجم شرائي خفي — CVD إيجابي مع سعر ثابت
    cvd_val = cvd(candles)
    avg_vol = sum(c.volume for c in candles[-20:]) / 20
    if cvd_val > avg_vol * 2:
        score += 2.0   # تجميع خفي واضح

    # 4. امتصاص جدران البيع — حجم بيع كبير لكن السعر لا ينزل
    sell_candles = [c for c in candles[-10:] if c.close < c.open]
    if sell_candles:
        avg_sell_vol = sum(c.volume for c in sell_candles) / len(sell_candles)
        if avg_sell_vol > avg_vol and price_range_pct < 5.0:
            score += 2.0  # امتصاص = يد قوية تشتري كل البيع

    return min(10.0, score)

# ═══════════════════════════════════════════════════════════════
# ─── GUARDIAN AGENT — الفلاتر الصارمة ─────────────────────────
# ═══════════════════════════════════════════════════════════════

def guardian_veto(
    direction: str,
    rsi_v: float,
    bb_u: float,
    bb_l: float,
    bb_m: float,
    price: float,
    cvd_hint: str,
    oracle_context: dict
) -> tuple[bool, str]:
    """
    المنع القاطع (Veto):
    يعيد (vetoed: bool, reason: str)

    قواعد المنع:
    - LONG في القمة (RSI > 75 أو سعر فوق BB علوي) → VETO
    - SHORT في القاع (RSI < 25 أو سعر تحت BB سفلي) → VETO
    - CVD يعاكس الاتجاه بقوة → VETO
    - أخبار سلبية من Oracle (token unlock قريب) → VETO
    """
    # فلتر 1: المنع القاطع — قمم وقيعان
    if direction == "LONG":
        if rsi_v > 75:
            return True, "RSI تشبع شرائي مفرط — يُمنع LONG"
        if price > bb_u:
            return True, "السعر فوق بولينجر العلوي — يُمنع LONG"
    if direction == "SHORT":
        if rsi_v < 25:
            return True, "RSI تشبع بيعي مفرط — يُمنع SHORT"
        if price < bb_l:
            return True, "السعر تحت بولينجر السفلي — يُمنع SHORT"

    # فلتر 2: تعارض مع CVD Divergence
    if cvd_hint and cvd_hint != direction:
        return True, f"CVD يعاكس الاتجاه ({cvd_hint}) — احتمال تلاعب"

    # فلتر 3: بيانات Oracle (token unlock قريب خلال 24 ساعة)
    if oracle_context.get("token_unlock_warning") and direction == "LONG":
        return True, "⚠️ فك تجميد عملات خلال 24 ساعة — خطر الضغط البيعي"

    if oracle_context.get("macro_bearish") and direction == "LONG":
        return True, "⚠️ بيانات الفيدرالي سلبية — Oracle يوقف LONG"

    return False, ""

def guardian_leverage(
    tier: MarketTier,
    score: float,
    atr_val: float,
    price: float,
    direction: str,
    liquidation_mode: bool = False
) -> tuple[float, float, float, float, float]:
    """
    تحديد الرافعة المالية + SL/TP ديناميكية بناءً على ATR
    يعيد: (leverage, sl, tp1, tp2, tp3)
    """
    # رافعة بداية منخفضة (Pyramiding يرفعها لاحقاً)
    base_lev = 2.0

    # رفع حسب الدرجة والـ tier
    if score >= 8:
        lev = min(tier.max_leverage, base_lev * 4)  # 8x max
    elif score >= 6:
        lev = min(tier.max_leverage, base_lev * 2.5)  # 5x
    else:
        lev = base_lev  # 2x للإشارات الضعيفة

    # في حالة Liquidation Cascade — رافعة أقل للأمان
    if liquidation_mode:
        lev = min(lev, 5.0)

    # SL/TP ديناميكي بناءً على ATR
    atr_mult = atr_val / price

    if direction == "LONG":
        sl = price * (1 - atr_mult * 2.0)
        tp1 = price * (1 + atr_mult * 1.5)
        tp2 = price * (1 + atr_mult * 3.0)
        tp3 = price * (1 + atr_mult * 5.0)
    else:
        sl = price * (1 + atr_mult * 2.0)
        tp1 = price * (1 - atr_mult * 1.5)
        tp2 = price * (1 - atr_mult * 3.0)
        tp3 = price * (1 - atr_mult * 5.0)

    return round(lev, 1), round(sl, 6), round(tp1, 6), round(tp2, 6), round(tp3, 6)

def calc_grade(score: float, conf: float) -> str:
    if score >= 8.5 and conf >= 82:
        return "S"
    if score >= 6.5 and conf >= 70:
        return "A"
    if score >= 4.5 and conf >= 55:
        return "B"
    return "C"

# ═══════════════════════════════════════════════════════════════
# ─── WAITING ROOM — غرفة الانتظار ─────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def waiting_room(candles_fn, symbol: str, direction: str, wait_sec: int = 600) -> bool:
    """
    غرفة الانتظار الديناميكية:
    إذا رُصد تلاعب، ننتظر 5-15 دقيقة ونعيد الفحص
    يعيد True إذا التلاعب انتهى وآمن الدخول
    """
    log.info("Waiting Room: %s %s — انتظار %d ثانية", symbol, direction, wait_sec)
    await asyncio.sleep(wait_sec)

    try:
        fresh_candles = await candles_fn(symbol)
        if not fresh_candles:
            return False
        spoofing = detect_spoofing(fresh_candles)
        cvd_val = cvd(fresh_candles)
        # إذا انتهى التلاعب
        if not spoofing:
            log.info("Waiting Room: %s — التلاعب انتهى، دخول آمن", symbol)
            return True
    except Exception as e:
        log.error("Waiting Room error: %s", e)

    return False

# ═══════════════════════════════════════════════════════════════
# ─── PREDATOR AGENT — القلب ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def predator_analyze(
    candles: list[Candle],
    symbol: str,
    tier: MarketTier,
    oracle_context: dict,
    signal_queue: asyncio.Queue
) -> None:
    """
    وكيل الافتراس — يحلل ويضع النتيجة في signal_queue
    Guardian يقرأ من القائمة ويصدر القرار النهائي
    لا blocking هنا — كل شيء async
    """
    if len(candles) < 60:
        return

    closes = [c.close for c in candles]
    price = closes[-1]

    # ─ المؤشرات الأساسية ─
    rsi_v = rsi(closes)
    mv, ms, mh = macd(closes)
    bb_u, bb_m, bb_l, bb_std = bollinger(closes)
    atr_v = atr(candles)
    sk, sd = stoch_rsi(closes)
    vwap_v = vwap(candles)
    obi_v = obi(candles)

    # ─ أدوات كشف الكذب ─
    cvd_val = cvd(candles)
    delta_v = delta_flow(candles)
    cvd_hint, cvd_strength = cvd_divergence(candles)

    # ─ استراتيجيات متقدمة ─
    fvgs = find_fvg(candles)
    obs = find_order_blocks(candles)
    near_fvg = price_near_fvg(price, fvgs)
    liq_cascade, liq_dir = detect_liquidation_cascade(candles)
    stop_hunt, sh_dir = detect_stop_hunt(candles)
    spoofing = detect_spoofing(candles)

    # ═══ حساب Score ═══
    long_score = 0.0
    short_score = 0.0
    long_strats = []
    short_strats = []

    # 1. RSI
    if rsi_v < 35:
        long_score += 1.2
        long_strats.append("RSI Oversold")
    elif rsi_v > 65:
        short_score += 1.2
        short_strats.append("RSI Overbought")

    # 2. MACD
    if mh > 0 and mv > 0:
        long_score += 1.0
        long_strats.append("MACD Bullish")
    elif mh < 0 and mv < 0:
        short_score += 1.0
        short_strats.append("MACD Bearish")

    # 3. Bollinger
    if price < bb_l:
        long_score += 1.5
        long_strats.append("BB Lower Touch")
    elif price > bb_u:
        short_score += 1.5
        short_strats.append("BB Upper Touch")

    # 4. CVD Divergence — الأقوى
    if cvd_hint == "LONG":
        long_score += 1.5 + cvd_strength * 0.5
        long_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")
    elif cvd_hint == "SHORT":
        short_score += 1.5 + cvd_strength * 0.5
        short_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")

    # 5. Delta Flow
    if delta_v > 0:
        long_score += min(1.0, abs(delta_v) / 1000)
        long_strats.append("Positive Delta")
    else:
        short_score += min(1.0, abs(delta_v) / 1000)
        short_strats.append("Negative Delta")

    # 6. FVG — فجوات السيولة
    if near_fvg:
        if near_fvg["type"] == "bullish":
            long_score += 2.0
            long_strats.append("FVG Bullish Zone")
        else:
            short_score += 2.0
            short_strats.append("FVG Bearish Zone")

    # 7. Stop Hunt
    if stop_hunt:
        if sh_dir == "LONG":
            long_score += 2.5
            long_strats.append("🎯 Stop Hunt LONG")
        elif sh_dir == "SHORT":
            short_score += 2.5
            short_strats.append("🎯 Stop Hunt SHORT")

    # 8. Liquidation Cascade
    if liq_cascade:
        if liq_dir == "LONG":
            long_score += 3.0
            long_strats.append("💥 Liquidation Cascade → LONG")
        elif liq_dir == "SHORT":
            short_score += 3.0
            short_strats.append("💥 Liquidation Cascade → SHORT")

    # 9. OBI
    if obi_v > 0.3:
        long_score += 0.8
        long_strats.append("OBI Bullish")
    elif obi_v < -0.3:
        short_score += 0.8
        short_strats.append("OBI Bearish")

    # 10. VWAP
    if price > vwap_v and obi_v > 0:
        long_score += 0.7
        long_strats.append("VWAP Support")
    elif price < vwap_v and obi_v < 0:
        short_score += 0.7
        short_strats.append("VWAP Resistance")

    # 11. Stoch RSI
    if sk < 20 and sd < 20:
        long_score += 0.8
        long_strats.append("Stoch RSI Oversold")
    elif sk > 80 and sd > 80:
        short_score += 0.8
        short_strats.append("Stoch RSI Overbought")

    # ═══ اتخاذ القرار ═══
    direction, score, strats = None, 0.0, []
    if long_score >= tier.min_score and long_score > short_score:
        direction, score, strats = "LONG", long_score, long_strats
    elif short_score >= tier.min_score and short_score > long_score:
        direction, score, strats = "SHORT", short_score, short_strats

    if not direction:
        return

    # حساب الثقة
    strat_count = len(strats)
    conf = min(95.0, 40.0 + score * 5 + strat_count * 2)

    if conf < tier.min_confidence:
        return

    # ─ Guardian Veto ─
    vetoed, veto_reason = guardian_veto(
        direction, rsi_v, bb_u, bb_l, bb_m, price, cvd_hint, oracle_context
    )

    if vetoed:
        log.debug("Guardian VETO: %s %s — %s", symbol, direction, veto_reason)
        # إذا كان بسبب spoofing → غرفة انتظار
        if "تلاعب" in veto_reason or "CVD" in veto_reason:
            log.info("Waiting Room triggered for %s", symbol)
        return

    # ─ Spoofing check → Waiting Room ─
    if spoofing and not liq_cascade:
        log.info("Spoofing detected for %s — إدراج في غرفة الانتظار", symbol)
        return  # service.py يتعامل مع الانتظار

    # ─ رافعة ديناميكية ─
    lev, sl, tp1, tp2, tp3 = guardian_leverage(
        tier, score, atr_v, price, direction, liquidation_mode=liq_cascade
    )
    grade = calc_grade(score, conf)

    # FVG zone للـ position manager
    fvg_zone = near_fvg["mid"] if near_fvg else None

    sig = Signal(
        symbol=symbol,
        direction=direction,
        grade=grade,
        score=round(score, 2),
        confidence=round(conf, 1),
        entry=price,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        leverage=lev,
        strategies="\n".join(strats[:6]),
        tier=tier.tier,
        end_time=None,
        highest_hit=None,
        fvg_zone=fvg_zone,
        liquidation_signal=liq_cascade,
        waiting_room=spoofing
    )

    # ← إرسال للـ Guardian عبر Queue (non-blocking)
    await signal_queue.put(sig)
    log.info("Predator → Queue: %s %s score=%.1f conf=%.1f%% grade=%s lev=%.0fx",
             symbol, direction, score, conf, grade, lev)

# ═══════════════════════════════════════════════════════════════
# ─── SLEEPING GIANTS ANALYZER ──────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def sleeping_giant_analyze(
    candles_daily: list[Candle],
    symbol: str,
    tier: MarketTier,
    signal_queue: asyncio.Queue
) -> None:
    """
    رادار التجميع الصامت — يعمل على الفريم اليومي
    يبحث عن العملات النائمة التي على وشك الانفجار
    """
    if len(candles_daily) < 20:
        return

    sg_score = sleeping_giant_score(candles_daily)
    if sg_score < 6.0:  # حد أدنى للإشارة
        return

    closes = [c.close for c in candles_daily]
    price = closes[-1]
    rsi_v = rsi(closes)
    atr_v = atr(candles_daily)

    # شرط إضافي — RSI في منطقة محايدة (لا في تشبع)
    if rsi_v > 70 or rsi_v < 30:
        return

    direction = "LONG"  # Sleeping Giants دائماً LONG (تجميع)
    conf = min(90.0, 50.0 + sg_score * 4)

    lev, sl, tp1, tp2, tp3 = guardian_leverage(
        tier, sg_score, atr_v, price, direction
    )
    # رافعة منخفضة للعملات النائمة (Pyramiding يرفعها)
    lev = min(lev, 3.0)

    strats = ["🌙 Sleeping Giant", "Volatility Squeeze", "Silent Accumulation"]
    if sg_score >= 8:
        strats.append("⚡ Imminent Explosion")

    sig = Signal(
        symbol=symbol,
        direction=direction,
        grade=calc_grade(sg_score, conf),
        score=round(sg_score, 2),
        confidence=round(conf, 1),
        entry=price,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        leverage=lev,
        strategies="\n".join(strats),
        radar_type="spot",
        tier=tier.tier,
        end_time=None,
        highest_hit=None
    )

    await signal_queue.put(sig)
    log.info("SleepingGiant → Queue: %s score=%.1f conf=%.1f%%", symbol, sg_score, conf)

# ═══════════════════════════════════════════════════════════════
# ─── SHADOW MODE — المتدرب الصامت ──────────────────────────────
# ═══════════════════════════════════════════════════════════════

SHADOW_TRADES: list[ShadowTrade] = []

async def shadow_record(sig: Signal) -> ShadowTrade:
    """يسجل الصفقة الوهمية ورقياً بدون تنفيذ حقيقي"""
    trade = ShadowTrade(
        symbol=sig.symbol,
        direction=sig.direction,
        entry=sig.entry,
        sl=sig.sl,
        tp1=sig.tp1,
        strategies=sig.strategies,
        score=sig.score,
        confidence=sig.confidence,
    )
    SHADOW_TRADES.append(trade)
    log.debug("Shadow: صفقة وهمية مسجلة — %s %s @%.4f", sig.symbol, sig.direction, sig.entry)
    return trade

async def shadow_update(trade: ShadowTrade, current_price: float):
    """تحديث نتيجة الصفقة الوهمية"""
    if trade.result:
        return  # مغلقة بالفعل

    is_long = trade.direction == "LONG"

    if is_long:
        if current_price <= trade.sl:
            trade.result = "LOSS"
            trade.exit_price = current_price
            trade.pnl_pct = (current_price - trade.entry) / trade.entry * 100
            trade.closed_at = int(time.time())
        elif current_price >= trade.tp1:
            trade.result = "WIN"
            trade.exit_price = current_price
            trade.pnl_pct = (current_price - trade.entry) / trade.entry * 100
            trade.closed_at = int(time.time())
    else:
        if current_price >= trade.sl:
            trade.result = "LOSS"
            trade.exit_price = current_price
            trade.pnl_pct = (trade.entry - current_price) / trade.entry * 100
            trade.closed_at = int(time.time())
        elif current_price <= trade.tp1:
            trade.result = "WIN"
            trade.exit_price = current_price
            trade.pnl_pct = (trade.entry - current_price) / trade.entry * 100
            trade.closed_at = int(time.time())

def get_shadow_stats() -> dict:
    """إحصائيات المتدرب الصامت"""
    closed = [t for t in SHADOW_TRADES if t.result]
    if not closed:
        return {"total": 0, "win_rate": 0, "avg_pnl": 0}

    wins = sum(1 for t in closed if t.result == "WIN")
    avg_pnl = sum(t.pnl_pct or 0 for t in closed) / len(closed)

    return {
        "total": len(closed),
        "open": len([t for t in SHADOW_TRADES if not t.result]),
        "win_rate": round(wins / len(closed) * 100, 1),
        "avg_pnl": round(avg_pnl, 2),
        "wins": wins,
        "losses": len(closed) - wins,
    }

# ═══════════════════════════════════════════════════════════════
# ─── GUARDIAN AGENT — الحكم النهائي ────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def guardian_agent(
    signal_queue: asyncio.Queue,
    approved_queue: asyncio.Queue,
    oracle_context: dict
) -> None:
    """
    Guardian يعمل كـ background task مستقل:
    - يقرأ الإشارات من signal_queue
    - يطبق فلاتر إضافية
    - يضع الإشارات المعتمدة في approved_queue
    - لا يوقف Predator أبداً
    """
    log.info("Guardian Agent started")
    while True:
        try:
            # انتظر إشارة (timeout 1 ثانية لتجنب blocking)
            sig = await asyncio.wait_for(signal_queue.get(), timeout=1.0)

            # فحص إضافي من Oracle
            oracle_veto = (sig.grade == "C")
            if oracle_context.get("market_crash_warning"):
                oracle_veto = True
                log.warning("Guardian: Oracle يحذر من انهيار — %s رُفضت", sig.symbol)

            if not oracle_veto:
                await approved_queue.put(sig)
                log.info("Guardian ✅ اعتمد: %s %s grade=%s", sig.symbol, sig.direction, sig.grade)

            signal_queue.task_done()

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            log.error("Guardian error: %s", e)
            await asyncio.sleep(1)

# ═══════════════════════════════════════════════════════════════
# ─── ORACLE CONTEXT BUILDER ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def build_oracle_context(oracle_data: dict) -> dict:
    """
    يحول بيانات Oracle الخام إلى context يفهمه Guardian
    """
    ctx = {
        "token_unlock_warning": False,
        "macro_bearish": False,
        "market_crash_warning": False,
        "usdt_printing": False,
    }

    # فك التجميد خلال 24 ساعة
    if oracle_data.get("token_unlock_in_hours", 999) < 24:
        ctx["token_unlock_warning"] = True

    # DXY قوي = ضغط على الكريبتو
    dxy = oracle_data.get("dxy", 100)
    if dxy > 105:
        ctx["macro_bearish"] = True

    # Bitcoin يهبط بسرعة
    btc_change = oracle_data.get("btc_24h_change", 0)
    if btc_change < -8:
        ctx["market_crash_warning"] = True

    # طباعة USDT = صعود وشيك
    if oracle_data.get("usdt_minted_24h", 0) > 500_000_000:
        ctx["usdt_printing"] = True

    return ctx

# ═══════════════════════════════════════════════════════════════
# ─── QUEUE FACTORY ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def create_queues():
    """
    إنشاء Queues التواصل بين الوكلاء
    يمكن استبدالها بـ Redis Streams مستقبلاً
    """
    signal_queue = asyncio.Queue(maxsize=100)     # Predator → Guardian
    approved_queue = asyncio.Queue(maxsize=100)   # Guardian → Orchestrator
    return signal_queue, approved_queue
