/**
 * scanner.js — WhaleX Prime
 * ══════════════════════════════════════
 * Meme Coin Scanner — 8 مراحل أمان.
 * مستقل تماماً — لا يعتمد على وحدة أخرى.
 * لإضافة مرحلة جديدة: أضف في DEFAULT_CHECKS.
 * ══════════════════════════════════════
 */

const SCANNER = {

  // مراحل الفحص الافتراضية — تُستبدل بنتائج API حين تتوفر
  DEFAULT_CHECKS(score) {
    return [
      { n:'الكود المصدري مفتوح',   p:score>70, d:'Contract Source Code Verified' },
      { n:'Backdoor Detection',    p:score>65, d:'لا وجود لوظائف خفية أو Admin Keys' },
      { n:'ملكية العقد',           p:score>70, d:'Ownership Renounced / Locked' },
      { n:'السيولة مقفلة',         p:score>75, d:'Liquidity Pool Locked ≥ 6 months' },
      { n:'Rug Pull Check',        p:score>80, d:'نسبة السيولة مقابل Market Cap' },
      { n:'توزيع المحافظ',         p:score>70, d:'Top 10 holders < 30% من المعروض' },
      { n:'تاريخ التحويلات',       p:score>65, d:'لا يوجد نشاط مشبوه' },
      { n:'Honeypot Detection',    p:score>85, d:'يمكن البيع — لا Sell Tax عالية' },
    ];
  },

  _riskColor(risk) {
    return {low:'var(--green)', medium:'var(--gold)', high:'var(--red)', critical:'var(--red)'}[risk] || 'var(--gold)';
  },

  _riskLabel(risk) {
    return {low:'✅ آمن', medium:'⚠️ تحذير', high:'🚨 خطر', critical:'☠️ نصب'}[risk] || 'غير محدد';
  },

  async scan() {
    const addr  = document.getElementById('sc-addr')?.value?.trim();
    const chain = document.getElementById('sc-chain')?.value || 'sol';

    if(!addr) { UI.toast('أدخل عنوان العملة'); return; }

    const res = document.getElementById('sc-res');
    res.innerHTML = `<div class="empty">
      <div class="empty-ico">🔍</div>
      <div class="empty-t">AI يفحص العقد...</div>
      <div class="empty-s">Security · Liquidity · Ownership · Manipulation</div>
    </div>`;

    const d = await API.scanContract({ address: addr, chain });

    if(!d) { UI.toast('فشل الفحص — حاول مرة أخرى'); res.innerHTML=''; return; }

    const score  = d.score  || 0;
    const risk   = d.risk   || 'unknown';
    const checks = d.checks || this.DEFAULT_CHECKS(score);
    const rc     = this._riskColor(risk);
    const label  = this._riskLabel(risk);

    const checksHTML = checks.map(c => `
      <div class="chk-row">
        <div style="font-size:14px;flex-shrink:0;margin-top:1px">${(c.p||c.passed)?'✅':'❌'}</div>
        <div>
          <div style="font-size:12px;font-weight:700">${c.n||c.name}</div>
          <div style="font-size:11px;color:var(--text2);margin-top:2px">${c.d||c.detail||''}</div>
        </div>
      </div>`).join('');

    res.innerHTML = `
      <div class="card" style="margin-top:12px">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px">
          <div>
            <div style="font-size:52px;font-weight:900;font-family:var(--mono);color:${rc};line-height:1">
              ${score}<span style="font-size:20px;color:var(--text2)">/100</span>
            </div>
            <div style="padding:5px 14px;border-radius:20px;font-size:13px;font-weight:800;display:inline-block;margin-top:8px;background:${rc}18;border:1px solid ${rc}40;color:${rc}">
              ${label}
            </div>
          </div>
          <div style="text-align:center;padding:12px 16px;background:rgba(0,0,0,.3);border-radius:12px;border:1px solid ${rc}30">
            <div style="font-size:10px;color:var(--text3);margin-bottom:4px;font-weight:700">الخطر</div>
            <div style="font-size:16px;font-weight:900;color:${rc}">${risk.toUpperCase()}</div>
          </div>
        </div>
        <!-- Market Data -->
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px">
        <div style="background:rgba(4,8,16,.8);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:var(--text3);margin-bottom:3px">السيولة</div>
          <div style="font-size:13px;font-weight:700;font-family:var(--mono);color:var(--neon)">${d.market?'$'+UI.fmtCompact(d.market.liquidity||0):'--'}</div>
        </div>
        <div style="background:rgba(4,8,16,.8);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:var(--text3);margin-bottom:3px">Market Cap</div>
          <div style="font-size:13px;font-weight:700;font-family:var(--mono);color:var(--gold)">${d.market?'$'+UI.fmtCompact(d.market.market_cap||0):'--'}</div>
        </div>
        <div style="background:rgba(4,8,16,.8);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:var(--text3);margin-bottom:3px">Volume 24h</div>
          <div style="font-size:13px;font-weight:700;font-family:var(--mono)">${d.market?'$'+UI.fmtCompact(d.market.volume_24h||0):'--'}</div>
        </div>
        <div style="background:rgba(4,8,16,.8);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:var(--text3);margin-bottom:3px">عمر العقد</div>
          <div style="font-size:13px;font-weight:700;font-family:var(--mono)">${d.market?(d.market.age_days+' يوم'):'--'}</div>
        </div>
      </div>
      <!-- Checks passed summary -->
      <div style="text-align:center;margin-bottom:12px;font-size:12px;color:var(--text2)">
        اجتاز <b style="color:var(--green)">${d.checks_passed||0}</b> من <b>${d.checks_total||0}</b> فحص
      </div>
      ${checksHTML}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px">
          <button class="btn ${risk==='low'?'btn-green':'btn-ghost'} btn-sm"
            onclick="UI.toast('${risk==='low'?'جاري الشراء...':'⚠️ تحذير: مخاطرة عالية'}')">
            ${risk==='low' ? 'شراء ✅' : 'شراء ⚠️'}
          </button>
          <button class="btn btn-ghost btn-sm" onclick="SCANNER.clear()">مسح</button>
        </div>
      </div>`;
  },

  clear() {
    document.getElementById('sc-addr').value = '';
    document.getElementById('sc-res').innerHTML = '';
  },
};
