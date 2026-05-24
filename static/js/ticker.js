/**
 * ticker.js — WhaleX Prime
 * ══════════════════════════════════════
 * شريط الأسعار المتحرك — مستقل تماماً.
 * ══════════════════════════════════════
 */

const TICKER = {
  _af: null,

  build(prices) {
    if(!prices || !Object.keys(prices).length) return;

    const items = Object.entries(prices).slice(0,60).map(([sym, p]) => {
      const name = sym.replace('USDT','');
      const up   = p.change >= 0;
      const px   = p.price > 100
        ? p.price.toLocaleString('en',{maximumFractionDigits:2})
        : p.price.toFixed(4);

      return `<div class="ti" onclick="TRADE.loadChart('${name}USDT')">
        <span class="ts">${name}</span>
        <span class="tp" style="color:${up?'#00ff88':'#ff2255'}">$${px}</span>
        <span class="tc ${up?'up':'dn'}">${up?'+':''}${p.change.toFixed(2)}%</span>
      </div>`;
    });

    const html = [...items, ...items, ...items].join('');
    const c = document.getElementById('tk');
    if(!c) return;

    c.innerHTML = html;
    this._animate(c);
  },

  _animate(c) {
    if(this._af) cancelAnimationFrame(this._af);
    let x = 0;

    const step = () => {
      if(!c.parentElement) { this._af = null; return; }
      x -= 0.5;
      const w = c.scrollWidth / 3;
      if(Math.abs(x) >= w) x = 0;
      c.style.transform = `translateX(${x}px)`;
      this._af = requestAnimationFrame(step);
    };

    this._af = requestAnimationFrame(step);
  },

  init() {
    BUS.on('ws:prices', (prices) => {
      STATE.prices = prices;
      this.build(prices);
      WALLET._updatePortCards(prices);
    });
  },
};
