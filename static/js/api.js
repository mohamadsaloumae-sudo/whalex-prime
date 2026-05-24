/**
 * api.js — WhaleX Prime
 * ══════════════════════════════════════
 * كل طلبات HTTP في مكان واحد.
 * لإضافة endpoint جديد: أضف method هنا.
 * ══════════════════════════════════════
 */

const API = {

  _headers() {
    const h = { 'Content-Type': 'application/json' };
    if(STATE.token) h.Authorization = 'Bearer ' + STATE.token;
    return h;
  },

  async _get(path) {
    try {
      const r = await fetch(CONFIG.API + path, { headers: this._headers() });
      if(!r.ok) return null;
      return r.json();
    } catch { return null; }
  },

  async _post(path, body) {
    try {
      const r = await fetch(CONFIG.API + path, {
        method: 'POST',
        headers: this._headers(),
        body: JSON.stringify(body),
      });
      if(!r.ok) return null;
      return r.json();
    } catch { return null; }
  },

  // ── Auth ─────────────────────────────
  async guestLogin(name, email) {
    return this._post('/api/auth/guest', { name, email });
  },

  // ── Signals ──────────────────────────
  async getFuturesSignals() { return this._get('/api/signals/futures'); },
  async getSpotSignals()    { return this._get('/api/signals/spot'); },
  async getMemeSignals()    { return this._get('/api/signals/meme'); },

  // ── Prices ───────────────────────────
  async getAllPrices() { return this._get('/api/prices/all'); },

  // ── Trade ────────────────────────────
  async executeTrade(data)  { return this._post('/api/trade/execute', data); },
  async forceStop(symbol)   { return this._post('/api/trade/force-stop', { symbol }); },
  async getTradeStats()     { return this._get('/api/trade/stats'); },

  // ── Wallet ───────────────────────────
  async getAddress(chain)   { return this._get(`/api/wallet/${chain}/address`); },
  async generateWallet(chain){ return this._post('/api/wallet/generate', { chain }); },

  // ── Exchange ─────────────────────────
  async connectExchange(data){ return this._post('/api/exchange/connect', data); },

  // ── Subscription ─────────────────────
  async upgrade(data)        { return this._post('/api/subscription/upgrade', data); },

  // ── AI ───────────────────────────────
  async chat(messages)       { return this._post('/api/ai/chat', { messages }); },
  async scanContract(data)   { return this._post('/api/ai/scan-contract', data); },

  // ── Referral ─────────────────────────
  async getReferralStats()   { return this._get('/api/referral/stats'); },

  // ── Admin ────────────────────────────
  async getAdminStats()      { return this._get('/api/admin/stats'); },
  async killSwitch()         { return this._post('/api/admin/kill-switch', { confirm: true }); },
};
