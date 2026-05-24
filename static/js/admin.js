/**
 * admin.js — WhaleX Prime
 * ══════════════════════════════════════
 * Admin Panel — مستقل تماماً.
 * لإضافة إحصائية جديدة: أضف في _render.
 * ══════════════════════════════════════
 */

const ADMIN = {

  show() {
    UI.openModal('mo-adm-login');
    setTimeout(() => document.getElementById('adm-pw')?.focus(), 300);
  },

  checkPassword() {
    const pw = document.getElementById('adm-pw')?.value;
    if(pw === CONFIG.ADMIN_PASSWORD) {
      UI.closeModal('mo-adm-login');
      this.open();
    } else {
      UI.toast('كلمة مرور خاطئة');
    }
  },

  open() {
    document.getElementById('adm').classList.add('on');
    this.load();
  },

  close() {
    document.getElementById('adm').classList.remove('on');
  },

  async load() {
    const d = await API.getAdminStats();
    if(!d) return;

    document.getElementById('adm-u').textContent = d.total_users   || '--';
    document.getElementById('adm-p').textContent = d.pro_users     || '--';
    document.getElementById('adm-r').textContent = '$'+(d.revenue||0).toLocaleString();
    document.getElementById('adm-s').textContent = d.signals_today || '--';

    document.getElementById('adm-radar').innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <div style="width:8px;height:8px;border-radius:50%;background:var(--green)"></div>
        <span>Futures Radar: <b style="color:var(--green)">${d.scan_count||0}</b> دورة</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <div style="width:8px;height:8px;border-radius:50%;background:var(--neon)"></div>
        <span>رموز مراقبة: <b style="color:var(--neon)">${d.symbols||256}</b></span>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:8px;height:8px;border-radius:50%;background:var(--ai)"></div>
        <span>إحالات موزعة: <b style="color:var(--ai)">${d.total_referrals||0}</b></span>
      </div>`;
  },

  async killSwitch() {
    if(!confirm('⚠️ تأكيد تفعيل Kill Switch؟\nسيُغلق كل الصفقات فوراً!')) return;
    const d = await API.killSwitch();
    UI.toast(d?.status==='activated' ? '🚨 Kill Switch مفعّل — كل الصفقات أُغلقت' : 'فشل التفعيل');
  },
};
