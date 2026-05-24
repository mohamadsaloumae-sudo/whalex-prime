/**
 * signals.js — WhaleX Prime
 * ══════════════════════════════════════
 * إدارة الإشارات — مستقل تماماً.
 * يستمع لـ WS ويعرض الإشارات.
 * ══════════════════════════════════════
 */

const SIGNALS = {

  _renderCard(s) {
    const isL = s.direction === 'LONG';
    const gc  = UI.gradeClass(s.grade);
    const strats = (s.strategies||'').split('\n').filter(x=>x.trim()).slice(0,4);
    const data = encodeURIComponent(JSON.stringify({
      sl:s.sl, tp1:s.tp1, tp2:s.tp2, tp3:s.tp3,
      grade:s.grade, leverage:s.leverage, confidence:s.confidence
    }));

    return `<div class="sig ${isL?'long':'short'}">
      <div class="sig-top">
        <span class="sig-sym">${s.symbol}</span>
        <span class="pill ${isL?'pill-g':'pill-r'}">${s.direction}</span>
        <span class="grd ${gc}">${s.grade}</span>
        <span style="font-size:10px;color:var(--text3);margin-right:auto">${s.tier||''}</span>
        <span style="font-size:10px;color:var(--text3)">${new Date(s.created_at).toISOString().replace('T',' ').slice(0,16)} UTC</span>
        <span class="tag tag-ai" style="font-size:10px;padding:2px 6px">${s.leverage||1}x</span>
      </div>
      <div class="sig-lvls">
        <div class="lv en"><div class="lv-l">دخول</div><div class="lv-v">${UI.fmtPrice(s.entry)}</div></div>
        <div class="lv sl"><div class="lv-l">SL</div><div class="lv-v">${UI.fmtPrice(s.sl)}</div></div>
        <div class="lv t1"><div class="lv-l">TP1</div><div class="lv-v">${UI.fmtPrice(s.tp1)}</div></div>
        <div class="lv t2"><div class="lv-l">TP2</div><div class="lv-v">${UI.fmtPrice(s.tp2)}</div></div>
        <div class="lv t3"><div class="lv-l">TP3</div><div class="lv-v">${UI.fmtPrice(s.tp3)}</div></div>
      </div>
      <div class="conf-row">
        <div class="conf-bar"><div class="conf-fill" style="width:${s.confidence||0}%"></div></div>
        <span style="font-size:11px;font-weight:700;color:var(--neon);font-family:var(--mono)">${s.confidence||0}%</span>
      </div>
      ${strats.length ? `<div class="strats">${strats.map(t=>`<span class="strat">${t.trim()}</span>`).join('')}</div>` : ''}
      <div class="sig-btns">
        <button class="btn btn-ghost btn-sm" onclick="TRADE.openFromSignal('${s.symbol}','${data}')">📊 تداول</button>
        <button class="btn btn-ai btn-sm" onclick="CHAT.askAbout('${s.symbol}','${s.direction}','${s.grade}')">🤖 تحليل</button>
      </div>
    </div>`;
  },

  async load() {
    const tab = STATE.currentSigTab;
    const el  = document.getElementById('sig-list');
    if(!el) return;

    el.innerHTML = '<div class="empty"><div class="empty-ico">📡</div><div class="empty-t">تحميل...</div></div>';

    const loaders = {
      futures: () => API.getFuturesSignals(),
      spot:    () => API.getSpotSignals(),
      meme:    () => API.getMemeSignals(),
    };

    const d = await (loaders[tab] || loaders.futures)();

    if(d?.signals?.length) {
      el.innerHTML = d.signals.map(s => this._renderCard(s)).join('');
    } else {
      el.innerHTML = '<div class="empty"><div class="empty-ico">🔍</div><div class="empty-t">الرادار يحلل السوق</div><div class="empty-s">ستظهر الإشارات قريباً</div></div>';
    }
  },

  async loadHome() {
    const d = await API.getFuturesSignals();
    const el = document.getElementById('home-sigs');
    if(!el) return;
    if(d?.signals?.length) {
      el.innerHTML = d.signals.slice(0,2).map(s => this._renderCard(s)).join('');
    }
  },

  setTab(tab, el) {
    STATE.save('currentSigTab', tab);
    document.querySelectorAll('#sc2 .tab').forEach(e => e.classList.remove('on'));
    el.classList.add('on');
    this.load();
  },

  onNewSignal(s) {
    UI.toast(`📡 ${s.symbol} ${s.direction} ${s.grade}`);
    if(STATE.currentScreen === 2) this.load();
    const h = document.getElementById('home-sigs');
    if(h) {
      if(h.querySelector('.empty')) h.innerHTML = '';
      h.insertAdjacentHTML('afterbegin', this._renderCard(s));
    }
  },

  init() {
    // الاستماع لإشارات WS
    BUS.on('ws:signal', (sig) => this.onNewSignal(sig));
  },
};
