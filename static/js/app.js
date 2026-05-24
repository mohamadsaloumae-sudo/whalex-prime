/**
 * app.js — WhaleX Prime
 * ══════════════════════════════════════
 * نقطة البداية — يهيئ كل الوحدات.
 * ══════════════════════════════════════
 */

const APP = {

  async init() {
    // 1. تهيئة الـ UI
    UI.initModals();
    ROUTER.init();

    // 2. Auth
    if(!STATE.token) await this._guestLogin();

    // 3. تهيئة الوحدات
    TICKER.init();
    SIGNALS.init();
    WALLET.init();

    // 4. اتصال WebSocket
    WS_CLIENT.connect();

    // 5. تحديث الـ UI
    PROFILE.updateUI();
    PROFILE.loadStats();

    // 6. رابط الإحالة
    const rc = STATE.token?.slice(-8) || 'W'+Math.random().toString(36).slice(2,6).toUpperCase();
    document.getElementById('ref-link').textContent = CONFIG.REFERRAL_BASE_URL + rc;

    // 7. الانتقال للشاشة الرئيسية
    ROUTER.go(0);

    // 8. تحديث Demo/Live
    this._updateMode();

    // 9. وضع التداول
    document.getElementById('lev-sl')?.dispatchEvent(new Event('input'));
  },

  async _guestLogin() {
    try {
      const d = await API.guestLogin(STATE.profile.name||'', STATE.profile.email||'');
      if(d?.access_token) {
        STATE.save('token', d.access_token);
        STATE.save('tier',  d.tier || 'free');
      }
    } catch {}
  },

  setMode(m) {
    STATE.save('mode', m);
    this._updateMode();
    UI.toast(m==='demo' ? 'وضع Demo — تداول تجريبي' : '🔴 وضع Live — صفقات حقيقية!');
  },

  _updateMode() {
    const m = STATE.mode;
    document.getElementById('mt-d').className = 'mode-btn' + (m==='demo' ? ' on' : '');
    document.getElementById('mt-l').className = 'mode-btn' + (m==='live' ? ' live-on' : '');
    document.getElementById('mode-tag').textContent = m==='demo' ? 'Demo' : '🔴 Live';
  },
};

// ══════════════════════════════════════
// STARTUP — نقطة الدخول الوحيدة
// ══════════════════════════════════════
// مسح البيانات القديمة عند كل تحديث
const APP_VERSION = '2.0';
if(localStorage.getItem('wx_version') !== APP_VERSION) {
  localStorage.clear();
  localStorage.setItem('wx_version', APP_VERSION);
}
if(localStorage.getItem('wx_ob')) {
  // المستخدم سبق وسجّل — ابدأ التطبيق مباشرة
  document.getElementById('ob').style.display = 'none';
  document.getElementById('shell').classList.add('on');
  APP.init();
} else {
  // مستخدم جديد — ابدأ الـ Onboarding
  ONBOARDING.start();
}
