/**
 * ui.js — WhaleX Prime
 * ══════════════════════════════════════
 * مكونات UI المشتركة بين كل الوحدات.
 * ══════════════════════════════════════
 */

const UI = {

  // ── Toast ─────────────────────────────
  toast(msg, dur = 2500) {
    const t = document.getElementById('toast');
    if(!t) return;
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), dur);
  },

  // ── Modal ─────────────────────────────
  openModal(id)  { document.getElementById(id)?.classList.add('open'); },
  closeModal(id) { document.getElementById(id)?.classList.remove('open'); },

  initModals() {
    document.querySelectorAll('.mo').forEach(m => {
      m.addEventListener('click', e => {
        if(e.target === m) m.classList.remove('open');
      });
    });
  },

  // ── Copy ──────────────────────────────
  async copy(text, msg = '✓ تم النسخ') {
    try {
      await navigator.clipboard.writeText(text);
      this.toast(msg);
    } catch {
      this.toast('فشل النسخ');
    }
  },

  // ── Format Numbers ────────────────────
  fmtPrice(v) {
    const n = Number(v);
    if(isNaN(n)) return '--';
    return n > 100
      ? n.toLocaleString('en', {minimumFractionDigits:2, maximumFractionDigits:2})
      : n.toFixed(4);
  },

  fmtUSD(v) {
    return '$' + Number(v).toLocaleString('en', {minimumFractionDigits:2, maximumFractionDigits:2});
  },

  fmtCompact(n) {
    if(n >= 1e9) return (n/1e9).toFixed(1) + 'B';
    if(n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if(n >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return n.toFixed(0);
  },

  // ── Render Platform Logo ──────────────
  renderPlatLogo(plat, size = 36) {
    const all = [...CONFIG.PLATFORMS.dex, ...CONFIG.PLATFORMS.cex];
    const p = all.find(x => x.v === plat);
    if(!p) return `<div style="width:${size}px;height:${size}px;border-radius:8px;background:var(--card)"></div>`;
    return `<img src="${p.logo}" alt="${p.n}" style="width:${size}px;height:${size}px;border-radius:8px;object-fit:contain" onerror="this.style.display='none'">`;
  },

  // ── Render Chain Icon ─────────────────
  renderChainIcon(chainId, size = 38) {
    const c = CONFIG.CHAINS.find(x => x.id === chainId);
    if(!c) return '';
    return `<div style="width:${size}px;height:${size}px;border-radius:50%;background:radial-gradient(${c.color},${c.color}99);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:11px;color:#fff;font-family:var(--mono)">${c.icon}</div>`;
  },

  // ── Signal Grade Badge ────────────────
  gradeClass(grade) {
    return {S:'gS', A:'gA', B:'gB', C:'gC'}[grade] || 'gC';
  },

  // ── Loading State ─────────────────────
  setLoading(el, isLoading, text = '') {
    if(!el) return;
    if(isLoading) {
      el.disabled = true;
      el._originalText = el.textContent;
      el.innerHTML = '<div style="display:flex;align-items:center;gap:6px"><div class="typing"><div class="td"></div><div class="td"></div><div class="td"></div></div></div>';
    } else {
      el.disabled = false;
      el.textContent = text || el._originalText || '';
    }
  },
};
