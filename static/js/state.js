/**
 * state.js — WhaleX Prime
 * ══════════════════════════════════════
 * الحالة المشتركة بين كل الوحدات.
 * لا يوجد متغير عام خارج هذا الملف.
 * التواصل بين الوحدات عبر events فقط.
 * ══════════════════════════════════════
 */

const STATE = {

  // ── Auth ─────────────────────────────
  token:   localStorage.getItem('wx_tok')   || '',
  tier:    localStorage.getItem('wx_tier')  || 'free',
  profile: JSON.parse(localStorage.getItem('wx_profile') || '{}'),
  setup:   JSON.parse(localStorage.getItem('wx_setup')   || '{}'),

  // ── Trading ──────────────────────────
  mode:    localStorage.getItem('wx_mode')  || 'demo',  // demo | live
  currentScreen: 0,
  currentSigTab: 'futures',
  chartType: 'tv',  // tv | dex

  // ── Prices ───────────────────────────
  prices: {},

  // ── Auto Trading ─────────────────────
  autoActive: false,
  autoSymbol: '',

  // ── WebSocket ────────────────────────
  wsRetries: 0,

  // ── Chat ─────────────────────────────
  chatHistory: [],

  // ── Methods ──────────────────────────

  save(key, value) {
    this[key] = value;
    const persist = {
      token:'wx_tok', tier:'wx_tier',
      mode:'wx_mode', profile:'wx_profile', setup:'wx_setup'
    };
    if(persist[key]) localStorage.setItem(persist[key], typeof value === 'object' ? JSON.stringify(value) : value);
    BUS.emit('state:'+key, value);
  },

  get isPro() { return this.tier === 'pro'; },
  get isDemo() { return this.mode === 'demo'; },
};

/**
 * BUS — نظام الأحداث
 * وحدة A تنشر حدث → وحدة B تستمع
 * لا يوجد استدعاء مباشر بين الوحدات
 */
const BUS = {
  _listeners: {},

  on(event, cb) {
    if(!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(cb);
  },

  off(event, cb) {
    if(!this._listeners[event]) return;
    this._listeners[event] = this._listeners[event].filter(fn => fn !== cb);
  },

  emit(event, data) {
    (this._listeners[event] || []).forEach(cb => {
      try { cb(data); } catch(e) { console.error('BUS error:', event, e); }
    });
  },
};
