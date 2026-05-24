/**
 * trade.js — WhaleX Prime
 * ══════════════════════════════════════
 * إدارة التداول — مستقل تماماً.
 * TradingView + DexScreener + Orders
 * ══════════════════════════════════════
 */

const TRADE = {

  _sym: 'BTCUSDT',

  onEnter() {
    if(document.getElementById('tv-frame').src === 'about:blank') {
      this.loadChart('BTCUSDT');
    }
  },

  loadChart(sym) {
    sym = (sym||'BTCUSDT').replace('/','').toUpperCase();
    if(!sym.endsWith('USDT')) sym += 'USDT';
    this._sym = sym;
    document.getElementById('sym-inp').value = sym;

    if(STATE.chartType === 'tv') {
      this._loadTradingView(sym);
    } else {
      this._loadDexScreener(sym);
    }
  },

  _loadTradingView(sym) {
    document.getElementById('tv-frame').src =
      `https://s.tradingview.com/widgetembed/?symbol=BINANCE%3A${sym}.P&interval=15&theme=dark&style=1&locale=ar&toolbar_bg=%23020408&hide_side_toolbar=1&allow_symbol_change=0`;
  },

  async _loadDexScreener(sym) {
    const token = sym.replace('USDT','').toLowerCase();
    document.getElementById('dex-frame').src =
      `https://dexscreener.com/solana/${token}?embed=1&theme=dark&chart=1&trades=0&tabs=0&info=0&chartLeftToolbar=0&chartTheme=dark&chartStyle=1`;
    await this._loadDexInfo(token);
  },

  async _loadDexInfo(token) {
    try {
      const r = await fetch(`https://api.dexscreener.com/latest/dex/search?q=${token}`);
      const d = await r.json();
      const pair = d.pairs?.[0];
      if(!pair) return;
      document.getElementById('dex-price').textContent = '$' + (parseFloat(pair.priceUsd)||0).toFixed(6);
      document.getElementById('dex-liq').textContent   = '$' + UI.fmtCompact(pair.liquidity?.usd||0);
      document.getElementById('dex-mcap').textContent  = '$' + UI.fmtCompact(pair.fdv||0);
      document.getElementById('dex-vol').textContent   = '$' + UI.fmtCompact(pair.volume?.h24||0);
      const age = pair.pairCreatedAt ? Math.floor((Date.now()-pair.pairCreatedAt)/86400000)+'d' : '--';
      document.getElementById('dex-age').textContent   = age;
    } catch {}
  },

  setChartType(type, el) {
    if(type === 'dex') {
      const sym = this._sym.replace('USDT','');
      const url = `https://dexscreener.com/solana?q=${sym}`;
      if(window.Telegram?.WebApp?.openLink) {
        window.Telegram.WebApp.openLink(url, {try_instant_view: true});
      } else {
        window.open(url, '_blank');
      }
      return;
    }
    STATE.save('chartType', type);
    document.querySelectorAll('#sc1 .chart-chip').forEach(c => c.classList.remove('on'));
    el.classList.add('on');
    document.getElementById('tv-box').style.display  = type === 'tv'  ? 'block' : 'none';
    document.getElementById('dex-box').style.display = type === 'dex' ? 'block' : 'none';
    document.getElementById('dex-info').style.display= type === 'dex' ? 'flex'  : 'none';
    this.loadChart(this._sym);
  },

  openFromSignal(sym, enc) {
    ROUTER.go(1);
    this.loadChart(sym);
    setTimeout(() => {
      try {
        const s = JSON.parse(decodeURIComponent(enc));
        const p = document.getElementById('sig-panel');
        if(!p) return;
        p.style.display = 'block';
        p.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
            <span class="sig-sym">${sym}</span>
            <span class="grd ${UI.gradeClass(s.grade)}">${s.grade}</span>
            <span style="font-size:10px;color:var(--text3);margin-right:auto">${s.leverage||1}x</span>
            <span style="font-size:11px;color:var(--neon);font-family:var(--mono);font-weight:700">${s.confidence||0}%</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;font-size:11px">
            <div style="background:rgba(4,8,16,.8);border-radius:6px;padding:6px;text-align:center"><div style="color:var(--text3);margin-bottom:2px">SL</div><div style="color:var(--red);font-family:var(--mono);font-weight:700">${UI.fmtPrice(s.sl)}</div></div>
            <div style="background:rgba(4,8,16,.8);border-radius:6px;padding:6px;text-align:center"><div style="color:var(--text3);margin-bottom:2px">TP1</div><div style="color:#ffd166;font-family:var(--mono);font-weight:700">${UI.fmtPrice(s.tp1)}</div></div>
            <div style="background:rgba(4,8,16,.8);border-radius:6px;padding:6px;text-align:center"><div style="color:var(--text3);margin-bottom:2px">TP2</div><div style="color:#ff9f43;font-family:var(--mono);font-weight:700">${UI.fmtPrice(s.tp2)}</div></div>
            <div style="background:rgba(4,8,16,.8);border-radius:6px;padding:6px;text-align:center"><div style="color:var(--text3);margin-bottom:2px">TP3</div><div style="color:var(--green);font-family:var(--mono);font-weight:700">${UI.fmtPrice(s.tp3)}</div></div>
          </div>`;
      } catch {}
    }, 300);
  },

  setTab(t, el) {
    document.querySelectorAll('#sc1 .tabs .tab').forEach(e => e.classList.remove('on'));
    el.classList.add('on');
    document.getElementById('tt-m').style.display = t==='m' ? 'block' : 'none';
    document.getElementById('tt-a').style.display = t==='a' ? 'block' : 'none';
  },

  updateLeverage(el) {
    const v = parseInt(el.value), mx = parseInt(el.max)||100;
    document.getElementById('lev-txt').textContent = v+'x';
    const p = (v-1)/(mx-1)*100;
    el.style.background = `linear-gradient(90deg,var(--neon) ${p}%,var(--border2) ${p}%)`;
  },

  checkGas() {
    const a = parseFloat(document.getElementById('tr-amt')?.value)||0;
    document.getElementById('gas-warn').style.display = (a > 0 && 1240 < a*(1+CONFIG.GAS_FEE_PERCENT)) ? 'block' : 'none';
  },

  async execute(dir) {
    if(document.getElementById('gas-warn').style.display !== 'none') {
      UI.toast('⚠️ رصيد Gas غير كافٍ'); return;
    }
    const amt = parseFloat(document.getElementById('tr-amt')?.value)||100;
    const lev = parseInt(document.getElementById('lev-sl')?.value)||10;
    UI.toast('جاري الإرسال...');
    const d = await API.executeTrade({
      symbol: this._sym, direction: dir,
      amount: amt, leverage: lev,
      account_type: STATE.mode,
    });
    UI.toast(d?.status==='executed' ? `✓ ${dir} ${this._sym}` : 'تم إرسال الأمر');
    if(d?.status==='executed') PROFILE.loadStats();
  },

  async startAuto() {
    if(!STATE.isPro) { PROFILE.upgrade(); return; }
    STATE.autoActive = true;
    STATE.autoSymbol = this._sym;
    document.getElementById('fstop').style.display = 'flex';
    document.getElementById('auto-badge').style.display = 'flex';
    document.getElementById('auto-sym-lbl').textContent = this._sym;
    UI.toast('🤖 Auto Trading مفعّل — '+this._sym);
    BUS.emit('trade:auto:start', { symbol: this._sym });
  },

  async forceStop() {
    STATE.autoActive = false;
    STATE.autoSymbol = '';
    document.getElementById('fstop').style.display = 'none';
    document.getElementById('auto-badge').style.display = 'none';
    UI.toast('⏹ Auto Trading أُوقف فوراً');
    await API.forceStop(STATE.autoSymbol);
    BUS.emit('trade:auto:stop', null);
  },
};
