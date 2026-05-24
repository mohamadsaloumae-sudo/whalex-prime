/**
 * onboarding.js — WhaleX Prime
 * ══════════════════════════════════════
 * Onboarding — 4 خطوات — مرة واحدة فقط.
 * لإضافة خطوة: أضف في STEPS.
 * ══════════════════════════════════════
 */

const ONBOARDING = {

  _step: 0,
  _data: {},

  STEPS: ['welcome', 'profile', 'platform', 'type'],

  start() {
    document.getElementById('ob').style.display = 'flex';
    document.getElementById('shell').classList.remove('on');
    this._step = 0;
    this._data = {};
    this._render();
  },

  _render() {
    const s    = this.STEPS[this._step];
    const tot  = this.STEPS.length;
    const btn  = document.getElementById('ob-btn');

    // Progress bar
    document.getElementById('ob-lbl').textContent = `${this._step+1} / ${tot}`;
    let pg = '';
    for(let i=0; i<tot; i++) pg += `<div class="ob-seg${i<=this._step?' done':''}"></div>`;
    document.getElementById('ob-prog').innerHTML = pg;
    btn.textContent = this._step === tot-1 ? 'ابدأ الآن' : 'التالي';

    const renders = {
      welcome:  () => this._renderWelcome(),
      profile:  () => this._renderProfile(),
      platform: () => this._renderPlatform(),
      type:     () => this._renderType(),
    };

    document.getElementById('ob-body').innerHTML = (renders[s] || renders.welcome)();
    btn.disabled = !this._isStepValid(s);
  },

  _isStepValid(s) {
    if(s === 'welcome')  return true;
    if(s === 'profile')  return !!(this._data.name && this._data.email?.includes('@'));
    if(s === 'platform') return !!this._data.plat;
    if(s === 'type')     return !!(this._data.types?.length > 0);
    return true;
  },

  _checkValid() {
    document.getElementById('ob-btn').disabled = !this._isStepValid(this.STEPS[this._step]);
  },

  _renderWelcome() {
    return `
      <div class="ob-ico">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
          <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z" fill="url(#og)"/>
          <defs><linearGradient id="og" x1="2" y1="2" x2="22" y2="22"><stop stop-color="#00f5ff"/><stop offset="1" stop-color="#7c3aff"/></linearGradient></defs>
        </svg>
      </div>
      <div class="ob-title">مرحباً في WhaleX Prime 🐋</div>
      <div class="ob-sub">منظومة تداول ذكية مدعومة بالذكاء الاصطناعي<br>رادارات متعددة • إشارات حقيقية • Auto Trading</div>
      <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-top:8px">
        <div style="display:flex;gap:12px;padding:8px 0"><div style="font-size:24px">🎯</div><div><div style="font-weight:700;font-size:13px">رادار AI يحلل السوق 24/7</div><div style="font-size:11px;color:var(--text2)">Futures · Spot · Meme Coins</div></div></div>
        <div style="display:flex;gap:12px;padding:8px 0;border-top:1px solid var(--border)"><div style="font-size:24px">🤖</div><div><div style="font-weight:700;font-size:13px">Auto Trading بالذكاء الاصطناعي</div><div style="font-size:11px;color:var(--text2)">Pyramiding · Guardian · Kill Switch</div></div></div>
        <div style="display:flex;gap:12px;padding:8px 0;border-top:1px solid var(--border)"><div style="font-size:24px">🛡️</div><div><div style="font-weight:700;font-size:13px">Meme Scanner — 8 مراحل أمان</div><div style="font-size:11px;color:var(--text2)">Rug Pull · Backdoor · Honeypot</div></div></div>
      </div>`;
  },

  _renderProfile() {
    return `
      <div class="ob-ico"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>
      <div class="ob-title">إنشاء حسابك</div>
      <div class="ob-sub">بياناتك مشفرة ومحمية تماماً</div>
      <div class="fld"><div class="fl">الاسم الكامل *</div><input class="fi" id="ob-n" placeholder="محمد أحمد" value="${this._data.name||''}" oninput="ONBOARDING._data.name=this.value;ONBOARDING._checkValid()"></div>
      <div class="fld"><div class="fl">البريد الإلكتروني *</div><input class="fi" type="email" id="ob-e" placeholder="name@email.com" value="${this._data.email||''}" oninput="ONBOARDING._data.email=this.value;ONBOARDING._checkValid()"></div>
      <div class="fld"><div class="fl">رقم الهاتف (اختياري)</div><input class="fi" type="tel" id="ob-p" placeholder="+966..." value="${this._data.phone||''}" oninput="ONBOARDING._data.phone=this.value"></div>`;
  },

  _renderPlatform() {
    const all = [...CONFIG.PLATFORMS.dex, ...CONFIG.PLATFORMS.cex];
    const dex = CONFIG.PLATFORMS.dex.map(p => this._platCard(p)).join('');
    const cex = CONFIG.PLATFORMS.cex.map(p => this._platCard(p)).join('');
    return `
      <div class="ob-ico"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M16 12h.01"/></svg></div>
      <div class="ob-title">اختر منصة التداول</div>
      <div class="ob-sub">يمكنك تغييرها لاحقاً من الإعدادات</div>
      <div class="ob-sec" style="margin-top:12px">منصات لامركزية DEX</div>
      <div class="plat-grid">${dex}</div>
      <div class="ob-sec" style="margin-top:10px">منصات مركزية CEX</div>
      <div class="plat-grid">${cex}</div>`;
  },

  _platCard(p) {
    const sel = this._data.plat === p.v;
    return `<div class="plat-card${sel?' sel':''}" onclick="ONBOARDING._selectPlatform('${p.v}',this)">
      <img class="plat-logo" src="${p.logo}" onerror="this.style.display='none'" alt="${p.n}">
      <div class="plat-name">${p.n}</div>
      <div class="plat-sub">${p.s}</div>
    </div>`;
  },

  _renderType() {
    const types = [
      {v:'futures', i:'📈', n:'Futures',    s:'تداول بالرافعة المالية'},
      {v:'spot',    i:'💰', n:'Spot',       s:'شراء وبيع مباشر'},
      {v:'meme',    i:'🚀', n:'Meme Coins', s:'عملات الترند على DEX'},
    ];
    return `
      <div class="ob-ico"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/></svg></div>
      <div class="ob-title">نوع التداول</div>
      <div class="ob-sub">يمكنك اختيار أكثر من نوع — قابل للتغيير لاحقاً</div>
      ${types.map(t => {
        const sel = this._data.types?.includes(t.v);
        return `<div class="ob-opt${sel?' sel':''}" onclick="ONBOARDING._selectType('${t.v}',this)">
          <div style="font-size:26px;flex-shrink:0">${t.i}</div>
          <div style="flex:1;text-align:right">
            <div style="font-weight:800;font-size:14px">${t.n}</div>
            <div style="font-size:11px;color:var(--text2);margin-top:2px">${t.s}</div>
          </div>
          <div class="ob-chk">${sel?'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>':''}</div>
        </div>`;
      }).join('')}`;
  },

  _selectPlatform(v, el) {
    document.querySelectorAll('.plat-card').forEach(c => c.classList.remove('sel'));
    el.classList.add('sel');
    this._data.plat = v;
    this._checkValid();
  },

  _selectType(v, el) {
    if(!this._data.types) this._data.types = [];
    const i = this._data.types.indexOf(v);
    if(i === -1) {
      this._data.types.push(v);
      el.classList.add('sel');
      el.querySelector('.ob-chk').innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>';
    } else {
      this._data.types.splice(i,1);
      el.classList.remove('sel');
      el.querySelector('.ob-chk').innerHTML = '';
    }
    this._checkValid();
  },

  next() {
    if(this._step < this.STEPS.length - 1) { this._step++; this._render(); }
    else this._finish();
  },

  skip() { this._finish(); },

  _finish() {
    // حفظ البيانات
    STATE.save('setup',   this._data);
    STATE.save('profile', { name:this._data.name, email:this._data.email, phone:this._data.phone });
    localStorage.setItem('wx_ob', '1');

    // إخفاء الـ Onboarding وإظهار التطبيق
    document.getElementById('ob').style.display = 'none';
    document.getElementById('shell').classList.add('on');

    // بدء التطبيق
    APP.init();
  },
};
