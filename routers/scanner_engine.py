"""
scanner_engine.py — WhaleX Prime
═══════════════════════════════════════════════════════════════════
فاحص عقود Meme Coins الشامل — 25 نقطة فحص
مصادر البيانات:
  - GoPlus Security API  → العقد + السيولة + المحافظ (ETH/BSC/ARB/BASE)
  - Birdeye API          → Solana (أسعار + holders)
  - DexScreener API      → السيولة + Volume + عمر العقد
  - UNCX / Team Finance  → التحقق من قفل السيولة
═══════════════════════════════════════════════════════════════════
المعايير المعتمدة (2026):
  - السيولة مقفولة: 6 أشهر حد أدنى، 12 شهر مثالي، 100% نسبة
  - LP Tokens محروقة: أعلى درجة أمان
  - Top 10 holders: أقل من 30% آمن
  - Creator balance: أقل من 5% آمن
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time
from typing import Optional
import httpx

log = logging.getLogger("scanner_engine")

# ══════════════════════════════════════════════════
# CHAIN CONFIG
# ══════════════════════════════════════════════════
GOPLUS_CHAINS = {
    "eth":  "1",
    "bsc":  "56",
    "arb":  "42161",
    "base": "8453",
    "poly": "137",
    "avax": "43114",
}

LOCK_PLATFORMS = [
    "uncx",
    "team.finance",
    "pinksale",
    "mudra",
    "dxsale",
]

# ══════════════════════════════════════════════════
# SOURCE 1: GoPlus Security API
# ══════════════════════════════════════════════════
async def fetch_goplus(address: str, chain: str) -> dict:
    chain_id = GOPLUS_CHAINS.get(chain, "1")
    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, params={"contract_addresses": address})
            data = r.json()
            token = data.get("result", {}).get(address.lower(), {})
            if not token:
                return {}

            # تحليل LP holders للتحقق من القفل
            lp_holders = token.get("lp_holders", [])
            lp_locked_pct = 0.0
            lp_burned_pct  = 0.0
            lock_duration_days = 0
            is_burned = False

            for h in lp_holders:
                pct = float(h.get("percent", 0) or 0) * 100
                tag = str(h.get("tag", "")).lower()
                is_locked = h.get("is_locked", 0) == 1
                # محروقة
                if "dead" in tag or "burn" in tag or h.get("address","").lower() in (
                    "0x000000000000000000000000000000000000dead",
                    "0x0000000000000000000000000000000000000000",
                ):
                    lp_burned_pct += pct
                    is_burned = True
                # مقفولة
                elif is_locked or any(p in tag for p in LOCK_PLATFORMS):
                    lp_locked_pct += pct
                    # نحاول نقدر مدة القفل
                    lock_end = h.get("locked_detail", {}).get("end_time", 0)
                    if lock_end:
                        days_left = (int(lock_end) - int(time.time())) / 86400
                        lock_duration_days = max(lock_duration_days, int(days_left))

            # تحليل holders
            holders_list = token.get("holders", [])
            top10_pct = sum(float(h.get("percent", 0) or 0) for h in holders_list[:10]) * 100
            creator_pct = float(token.get("creator_percent", 0) or 0) * 100

            return {
                # العقد
                "is_open_source":           token.get("is_open_source", "0") == "1",
                "is_proxy":                 token.get("is_proxy", "0") == "1",
                "is_honeypot":              token.get("is_honeypot", "0") == "1",
                "honeypot_with_same_creator": token.get("honeypot_with_same_creator", "0") == "1",
                "buy_tax":                  float(token.get("buy_tax", 0) or 0) * 100,
                "sell_tax":                 float(token.get("sell_tax", 0) or 0) * 100,
                "cannot_buy":               token.get("cannot_buy", "0") == "1",
                "cannot_sell_all":          token.get("cannot_sell_all", "0") == "1",
                "slippage_modifiable":      token.get("slippage_modifiable", "0") == "1",
                "personal_slippage_modifiable": token.get("personal_slippage_modifiable","0") == "1",
                "trading_cooldown":         token.get("trading_cooldown", "0") == "1",
                "transfer_pausable":        token.get("transfer_pausable", "0") == "1",
                "is_blacklisted":           token.get("is_blacklisted", "0") == "1",
                "is_whitelisted":           token.get("is_whitelisted", "0") == "1",
                "is_anti_whale":            token.get("is_anti_whale", "0") == "1",
                "anti_whale_modifiable":    token.get("anti_whale_modifiable", "0") == "1",
                "hidden_owner":             token.get("hidden_owner", "0") == "1",
                "can_take_back_ownership":  token.get("can_take_back_ownership", "0") == "1",
                "owner_change_balance":     token.get("owner_change_balance", "0") == "1",
                "selfdestruct":             token.get("selfdestruct", "0") == "1",
                "external_call":            token.get("external_call", "0") == "1",
                "is_mintable":              token.get("is_mintable", "0") == "1",
                # الملكية
                "owner_address":            token.get("owner_address", ""),
                "creator_address":          token.get("creator_address", ""),
                "creator_pct":              creator_pct,
                # المحافظ
                "holder_count":             int(token.get("holder_count", 0) or 0),
                "top10_pct":                top10_pct,
                # السيولة
                "lp_holder_count":          int(token.get("lp_holder_count", 0) or 0),
                "lp_locked_pct":            lp_locked_pct,
                "lp_burned_pct":            lp_burned_pct,
                "lp_is_burned":             is_burned,
                "lp_lock_duration_days":    lock_duration_days,
                "total_lp_secured":         lp_locked_pct + lp_burned_pct,
                # DEX
                "dex_info":                 token.get("dex", []),
            }
    except Exception as e:
        log.error("GoPlus fetch error: %s", e)
        return {}

# ══════════════════════════════════════════════════
# SOURCE 2: DexScreener API
# ══════════════════════════════════════════════════
async def fetch_dexscreener(address: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}")
            pairs = r.json().get("pairs", [])
            if not pairs:
                return {}
            # أفضل pair حسب السيولة
            pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
            buys  = pair.get("txns", {}).get("h24", {}).get("buys", 0)
            sells = pair.get("txns", {}).get("h24", {}).get("sells", 0)
            txns  = buys + sells
            # نسبة البيع/شراء
            buy_sell_ratio = buys / sells if sells > 0 else 99
            # اكتشاف Wash Trading: إذا كانت نسبة الشراء أكثر من 80% فيه تلاعب محتمل
            wash_trading_suspicious = buy_sell_ratio > 4.0 or buy_sell_ratio < 0.25
            # عمر العقد
            created_at = pair.get("pairCreatedAt", 0)
            age_days   = int((time.time() * 1000 - created_at) / 86400000) if created_at else 0
            return {
                "price_usd":              float(pair.get("priceUsd", 0) or 0),
                "price_change_h1":        float(pair.get("priceChange", {}).get("h1", 0) or 0),
                "price_change_h24":       float(pair.get("priceChange", {}).get("h24", 0) or 0),
                "liquidity_usd":          float(pair.get("liquidity", {}).get("usd", 0) or 0),
                "market_cap":             float(pair.get("fdv", 0) or 0),
                "volume_h24":             float(pair.get("volume", {}).get("h24", 0) or 0),
                "volume_h1":              float(pair.get("volume", {}).get("h1", 0) or 0),
                "txns_buys_h24":          buys,
                "txns_sells_h24":         sells,
                "txns_total_h24":         txns,
                "buy_sell_ratio":         round(buy_sell_ratio, 2),
                "wash_trading_suspicious":wash_trading_suspicious,
                "dex_name":               pair.get("dexId", ""),
                "chain_id":               pair.get("chainId", ""),
                "pair_address":           pair.get("pairAddress", ""),
                "age_days":               age_days,
                "age_hours":              int((time.time() * 1000 - created_at) / 3600000) if created_at else 0,
            }
    except Exception as e:
        log.error("DexScreener fetch error: %s", e)
        return {}

# ══════════════════════════════════════════════════
# SOURCE 3: Birdeye API (Solana)
# ══════════════════════════════════════════════════
async def fetch_birdeye(address: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"https://public-api.birdeye.so/defi/token_overview?address={address}",
                headers={"X-API-KEY": "public", "x-chain": "solana"}
            )
            d = r.json().get("data", {})
            if not d:
                return {}
            return {
                "price":           d.get("price", 0),
                "liquidity":       d.get("liquidity", 0),
                "market_cap":      d.get("mc", 0),
                "volume_24h":      d.get("v24hUSD", 0),
                "volume_1h":       d.get("v1hUSD", 0),
                "holders":         d.get("holder", 0),
                "price_change_24h":d.get("priceChange24hPercent", 0),
                "unique_wallets_24h": d.get("uniqueWallet24h", 0),
                "trade_24h":       d.get("trade24h", 0),
            }
    except Exception as e:
        log.error("Birdeye fetch error: %s", e)
        return {}

# ══════════════════════════════════════════════════
# SCORING ENGINE — 25 نقطة فحص
# ══════════════════════════════════════════════════
def run_checks(gp: dict, dex: dict, bird: dict, chain: str) -> tuple[int, str, list]:
    """
    يفحص 25 نقطة ويعيد (score, risk, checks_list)
    """
    score = 100
    checks = []

    def add(name: str, passed: bool, detail: str, penalty: int = 0, critical: bool = False):
        nonlocal score
        if not passed:
            score -= penalty
        checks.append({
            "name":     name,
            "passed":   passed,
            "detail":   detail,
            "penalty":  penalty if not passed else 0,
            "critical": critical,
        })

    # ── المجموعة 1: العقد الذكي ──────────────────────────

    # 1. Honeypot
    is_hp = gp.get("is_honeypot", False) or gp.get("cannot_sell_all", False)
    add("Honeypot Detection",
        not is_hp,
        "✅ يمكن البيع بحرية" if not is_hp else "🚨 HONEYPOT — لا يمكن البيع أبداً!",
        penalty=60, critical=True)

    # 2. Sell Tax
    sell_tax = gp.get("sell_tax", 0)
    tax_ok = sell_tax <= 5
    add("Sell Tax",
        tax_ok,
        f"رسوم البيع: {sell_tax:.1f}%" + (" ✅" if tax_ok else f" 🚨 {'خطر' if sell_tax > 15 else '⚠️ عالية'}"),
        penalty=30 if sell_tax > 15 else 15)

    # 3. Buy Tax
    buy_tax = gp.get("buy_tax", 0)
    add("Buy Tax",
        buy_tax <= 5,
        f"رسوم الشراء: {buy_tax:.1f}%" + (" ✅" if buy_tax <= 5 else " ⚠️ عالية"),
        penalty=10)

    # 4. Código المصدري
    is_open = gp.get("is_open_source", False)
    add("الكود المصدري",
        is_open,
        "✅ مفتوح ومتحقق" if is_open else "⚠️ كود مغلق — لا يمكن التحقق منه",
        penalty=20)

    # 5. Hidden Mint Function
    is_mintable = gp.get("is_mintable", False)
    add("Hidden Mint Function",
        not is_mintable,
        "✅ لا توجد صلاحية طباعة" if not is_mintable else "🚨 يمكن طباعة عملات جديدة!",
        penalty=40, critical=True)

    # 6. Hidden Owner / Backdoor
    hidden = gp.get("hidden_owner", False) or gp.get("can_take_back_ownership", False)
    add("Hidden Owner / Backdoor",
        not hidden,
        "✅ الملكية ظاهرة وآمنة" if not hidden else "🚨 مالك مخفي أو يمكن استرداد الملكية!",
        penalty=35, critical=True)

    # 7. Proxy Contract
    is_proxy = gp.get("is_proxy", False)
    add("Proxy Contract",
        not is_proxy,
        "✅ عقد مباشر" if not is_proxy else "⚠️ Proxy Contract — قابل للتعديل",
        penalty=20)

    # 8. Slippage Modifiable (SetFee Attack)
    slip_mod = gp.get("slippage_modifiable", False) or gp.get("personal_slippage_modifiable", False)
    add("SetFee / Slippage Attack",
        not slip_mod,
        "✅ الضريبة ثابتة" if not slip_mod else "🚨 يمكن رفع الضريبة لأي نسبة!",
        penalty=35, critical=True)

    # 9. Blacklist Function
    blacklist = gp.get("is_blacklisted", False)
    add("Blacklist Function",
        not blacklist,
        "✅ لا توجد قائمة حظر" if not blacklist else "⚠️ يمكن حظر محافظ من البيع",
        penalty=15)

    # 10. Transfer Pausable
    pausable = gp.get("transfer_pausable", False)
    add("Transfer Pausable",
        not pausable,
        "✅ التحويل حر" if not pausable else "🚨 يمكن تجميد كل التحويلات!",
        penalty=30, critical=True)

    # 11. Trading Cooldown
    cooldown = gp.get("trading_cooldown", False)
    add("Trading Cooldown",
        not cooldown,
        "✅ لا يوجد تأخير قسري" if not cooldown else "⚠️ تأخير قسري بين الصفقات",
        penalty=10)

    # 12. Self Destruct
    selfd = gp.get("selfdestruct", False)
    add("Self Destruct Function",
        not selfd,
        "✅ آمن" if not selfd else "🚨 العقد يمكن تدميره!",
        penalty=40, critical=True)

    # ── المجموعة 2: السيولة ──────────────────────────────

    # 13. قفل السيولة — المعيار الأهم
    liquidity_usd = dex.get("liquidity_usd", bird.get("liquidity", 0))
    lp_burned = gp.get("lp_is_burned", False)
    total_secured = gp.get("total_lp_secured", 0)
    lock_days = gp.get("lp_lock_duration_days", 0)

    if lp_burned:
        lp_status = "✅ LP Tokens محروقة نهائياً — أعلى درجة أمان"
        lp_ok = True
        lp_penalty = 0
    elif total_secured >= 95 and lock_days >= 180:
        lp_status = f"✅ مقفولة {total_secured:.0f}% لمدة {lock_days} يوم"
        lp_ok = True
        lp_penalty = 0
    elif total_secured >= 80 and lock_days >= 90:
        lp_status = f"⚠️ مقفولة {total_secured:.0f}% لمدة {lock_days} يوم — مقبول"
        lp_ok = True
        lp_penalty = 5
    elif total_secured >= 50 and lock_days >= 30:
        lp_status = f"⚠️ مقفولة {total_secured:.0f}% — نسبة أو مدة غير كافية"
        lp_ok = False
        lp_penalty = 20
    elif total_secured < 10:
        lp_status = f"🚨 السيولة غير مقفولة — خطر Rug Pull فوري!"
        lp_ok = False
        lp_penalty = 45
    else:
        lp_status = f"⚠️ مقفولة جزئياً {total_secured:.0f}% لمدة {lock_days} يوم فقط"
        lp_ok = False
        lp_penalty = 25

    add("قفل السيولة (LP Lock)", lp_ok, lp_status, penalty=lp_penalty, critical=not lp_ok and total_secured < 10)

    # 14. مدة القفل تفصيلياً
    if not lp_burned and total_secured > 10:
        lock_ok = lock_days >= 180
        if lock_days >= 365:
            lock_detail = f"✅ {lock_days} يوم — ممتاز"
        elif lock_days >= 180:
            lock_detail = f"✅ {lock_days} يوم — كافٍ"
        elif lock_days >= 90:
            lock_detail = f"⚠️ {lock_days} يوم — أقل من المعيار (6 أشهر)"
        else:
            lock_detail = f"🚨 {lock_days} يوم — خطر! القفل قصير جداً"
        add("مدة قفل السيولة", lock_ok, lock_detail, penalty=15 if not lock_ok else 0)

    # 15. حجم السيولة
    liq_ok = liquidity_usd >= 50000
    add("حجم السيولة",
        liq_ok,
        f"${liquidity_usd:,.0f}" + (" ✅" if liquidity_usd >= 100000 else " ⚠️ منخفضة" if liquidity_usd >= 10000 else " 🚨 خطر"),
        penalty=20 if liquidity_usd < 10000 else 10 if liquidity_usd < 50000 else 0)

    # ── المجموعة 3: توزيع المحافظ ───────────────────────

    # 16. Top 10 Holders
    top10 = gp.get("top10_pct", 0)
    top10_ok = top10 < 30
    add("Top 10 Holders",
        top10_ok,
        f"يمتلكون {top10:.1f}%" + (" ✅" if top10 < 30 else " ⚠️ تركز مرتفع" if top10 < 50 else " 🚨 خطر تركز شديد"),
        penalty=25 if top10 > 60 else 15 if top10 > 40 else 8)

    # 17. Creator / Developer Balance
    creator_pct = gp.get("creator_pct", 0)
    creator_ok = creator_pct < 5
    add("رصيد المطور",
        creator_ok,
        f"المطور يمتلك {creator_pct:.1f}%" + (" ✅" if creator_ok else " 🚨 خطر Dump!"),
        penalty=30 if creator_pct > 20 else 15 if creator_pct > 10 else 8)

    # 18. عدد المحافظ (Holders)
    holders = gp.get("holder_count", bird.get("holders", 0))
    holders_ok = holders >= 100
    add("عدد المحافظ",
        holders_ok,
        f"{holders:,} محفظة" + (" ✅" if holders >= 500 else " ⚠️ قليل" if holders >= 100 else " 🚨 مشبوه جداً"),
        penalty=10 if holders < 50 else 5 if holders < 100 else 0)

    # ── المجموعة 4: التلاعب بالسوق ──────────────────────

    # 19. Wash Trading Detection
    wash = dex.get("wash_trading_suspicious", False)
    buy_sell = dex.get("buy_sell_ratio", 1)
    add("Wash Trading Detection",
        not wash,
        f"نسبة الشراء/البيع: {buy_sell:.1f}x" + (" ✅ طبيعي" if not wash else " ⚠️ نسبة مشبوهة — volume وهمي محتمل"),
        penalty=15)

    # 20. حجم التداول 24h
    vol24 = dex.get("volume_h24", bird.get("volume_24h", 0))
    vol_ok = vol24 >= 10000
    add("حجم التداول 24h",
        vol_ok,
        f"${vol24:,.0f}" + (" ✅" if vol24 >= 50000 else " ⚠️ منخفض" if vol24 >= 5000 else " 🚨 ميت تقريباً"),
        penalty=10 if vol24 < 5000 else 0)

    # 21. عمر العقد
    age_days = dex.get("age_days", 0)
    age_ok = age_days >= 7
    if age_days >= 90:
        age_detail = f"✅ {age_days} يوم — مستقر"
    elif age_days >= 30:
        age_detail = f"✅ {age_days} يوم"
    elif age_days >= 7:
        age_detail = f"⚠️ {age_days} يوم — جديد"
    elif age_days >= 1:
        age_detail = f"⚠️ {age_days} يوم — جديد جداً"
    else:
        age_hours = dex.get("age_hours", 0)
        age_detail = f"🚨 {age_hours} ساعة — أقل من يوم!"
    add("عمر العقد", age_ok, age_detail, penalty=10 if not age_ok else 0)

    # 22. تغيير السعر المتطرف (Pump & Dump)
    price_change_24h = dex.get("price_change_h24", bird.get("price_change_24h", 0))
    extreme_pump = abs(price_change_24h) > 200
    add("Pump & Dump Detection",
        not extreme_pump,
        f"تغيير 24h: {price_change_24h:+.1f}%" + (" ✅ طبيعي" if not extreme_pump else " 🚨 تحرك متطرف — مشبوه!"),
        penalty=15)

    # 23. Anti-Whale Modifiable
    anti_whale_mod = gp.get("anti_whale_modifiable", False)
    add("Anti-Whale Modifiable",
        not anti_whale_mod,
        "✅ حد المعاملات ثابت" if not anti_whale_mod else "⚠️ يمكن تعديل حد المعاملات",
        penalty=10)

    # 24. External Call Risk
    ext_call = gp.get("external_call", False)
    add("External Call Risk",
        not ext_call,
        "✅ لا يوجد استدعاء خارجي" if not ext_call else "⚠️ العقد يستدعي عقوداً خارجية",
        penalty=10)

    # 25. Honeypot من نفس المطور (تاريخ المطور)
    hp_same_creator = gp.get("honeypot_with_same_creator", False)
    add("تاريخ المطور",
        not hp_same_creator,
        "✅ لا يوجد سجل احتيال" if not hp_same_creator else "🚨 المطور لديه عقود Honeypot سابقة!",
        penalty=40, critical=True)

    # ── الحساب النهائي ────────────────────────────────────
    score = max(0, min(100, score))

    # تحديد مستوى الخطر
    has_critical = any(c["critical"] and not c["passed"] for c in checks)

    if has_critical or score < 30:
        risk = "critical"
    elif score < 50:
        risk = "high"
    elif score < 70:
        risk = "medium"
    else:
        risk = "low"

    return score, risk, checks

# ══════════════════════════════════════════════════
# RECOMMENDATION ENGINE
# ══════════════════════════════════════════════════
def get_recommendation(score: int, risk: str, checks: list) -> str:
    critical_fails = [c for c in checks if c["critical"] and not c["passed"]]

    if critical_fails:
        names = ", ".join(c["name"] for c in critical_fails[:2])
        return f"🚨 مشكلة حرجة: {names}. لا تشتري تحت أي ظرف."

    if risk == "critical":
        return "☠️ احتمال نصب كبير جداً. اهرب من هذه العملة."
    if risk == "high":
        return "⚠️ مخاطرة عالية جداً. إذا دخلت، ضع مبلغاً لا تخسره وراقب باستمرار."
    if risk == "medium":
        return "🟡 تحقق جيداً من الفريق والمشروع. ادخل بحذر ومبالغ صغيرة."
    return "✅ يبدو آمناً نسبياً. لكن لا يوجد 100% أمان في Meme Coins. ادخل بوعي."

# ══════════════════════════════════════════════════
# MAIN SCAN FUNCTION
# ══════════════════════════════════════════════════
async def full_scan(address: str, chain: str) -> dict:
    """
    الفحص الشامل الكامل — 25 نقطة
    يشغل كل المصادر بالتوازي لأسرع نتيجة
    """
    address = address.strip()
    chain   = chain.lower().strip()

    # تشغيل كل المصادر بالتوازي
    tasks = [fetch_dexscreener(address)]

    if chain == "sol":
        tasks.append(fetch_birdeye(address))
        gp_data = {}
    else:
        tasks.append(fetch_goplus(address, chain))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    dex_data  = results[0] if not isinstance(results[0], Exception) else {}
    data2     = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else {}

    if chain == "sol":
        bird_data = data2
        gp_data   = {}
    else:
        bird_data = {}
        gp_data   = data2

    # تشغيل محرك الفحص
    score, risk, checks = run_checks(gp_data, dex_data, bird_data, chain)
    recommendation = get_recommendation(score, risk, checks)

    verdict_map = {
        "low":      "✅ آمن للتداول",
        "medium":   "⚠️ تحذير — تحقق قبل الدخول",
        "high":     "🚨 خطر عالٍ — مخاطرة كبيرة",
        "critical": "☠️ نصب محتمل — ابتعد فوراً",
    }

    return {
        "score":          score,
        "risk":           risk,
        "verdict":        verdict_map.get(risk, "غير محدد"),
        "checks":         checks,
        "recommendation": recommendation,
        "checks_passed":  sum(1 for c in checks if c["passed"]),
        "checks_total":   len(checks),
        "market": {
            "price":        dex_data.get("price_usd", bird_data.get("price", 0)),
            "liquidity":    dex_data.get("liquidity_usd", bird_data.get("liquidity", 0)),
            "market_cap":   dex_data.get("market_cap", bird_data.get("market_cap", 0)),
            "volume_24h":   dex_data.get("volume_h24", bird_data.get("volume_24h", 0)),
            "holders":      gp_data.get("holder_count", bird_data.get("holders", 0)),
            "age_days":     dex_data.get("age_days", 0),
            "dex":          dex_data.get("dex_name", ""),
            "chain":        chain,
        },
        "security": {
            "honeypot":       gp_data.get("is_honeypot", False),
            "sell_tax":       gp_data.get("sell_tax", 0),
            "buy_tax":        gp_data.get("buy_tax", 0),
            "open_source":    gp_data.get("is_open_source", False),
            "hidden_owner":   gp_data.get("hidden_owner", False),
            "lp_burned":      gp_data.get("lp_is_burned", False),
            "lp_locked_pct":  gp_data.get("total_lp_secured", 0),
            "lock_days":      gp_data.get("lp_lock_duration_days", 0),
            "top10_pct":      gp_data.get("top10_pct", 0),
            "creator_pct":    gp_data.get("creator_pct", 0),
        },
    }
