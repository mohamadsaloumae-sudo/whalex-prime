/**
 * wallet.js — WhaleX Prime
 * ══════════════════════════════════════
 * إدارة المحافظ — مستقل تماماً.
 * Hot Wallet + WalletConnect + CEX API
 * ══════════════════════════════════════
 */

const WALLET = {

  _currentChain: 'sol',
  _prices: {},

  load() {
    this._renderAssets();
    this._loadAddress(this._currentChain);
  },

  _renderAssets() {
    const P = STATE.prices;
    const el = document.getElementById('assets-list');
    if(!el) return;

    const prices = {
      BTC:  P.BTCUSDT?.price  || 0,
      SOL:  P.SOLUSDT?.price  || 0,
      ETH:  P.ETHUSDT?.price  || 0,
      BNB:  P.BNBUSDT?.price  || 0,
      USDT: 1,
      USDC: 1,
    };

    let total = 0;
    const rows = CONFIG.DEFAULT_ASSETS.map(a => {
      const usdVal = a.amount * (prices[a.symbol] || 1);
      total += usdVal;
      return `<div class="asset">
        <div class="a-ico" style="background:radial-gradient(${a.color},${a.color}99)">${a.symbol.slice(0,3)}</div>
        <div class="a-info">
          <div class="a-name">${a.name}</div>
          <div class="a-net">${a.network}</div>
        </div>
        <div class="a-right">
          <div class="a-val" style="color:${a.color}">${a.amount} ${a.symbol}</div>
          <div class="a-usd">${UI.fmtUSD(usdVal)}</div>
        </div>
      </div>`;
    });

    el.innerHTML = rows.join('');
    document.getElementById('wal-total').textContent = UI.fmtUSD(total);

    // تحديث الرئيسية
    document.getElementById('total-bal').textContent = total.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
  },

  async _loadAddress(chain) {
    const d = await API.getAddress(chain);
    if(d?.address) {
      document.getElementById('wal-addr').textContent = d.address;
      document.getElementById('dep-addr').textContent = d.address;
    }
  },

  selectChain(el, chain) {
    this._currentChain = chain;
    document.querySelectorAll('#chain-tabs .chip').forEach(c => c.classList.remove('on'));
    el.classList.add('on');
    this._loadAddress(chain);
  },

  copyAddress() {
    UI.copy(document.getElementById('wal-addr').textContent, '✓ تم نسخ العنوان');
  },

  async generate() {
    const chain = document.getElementById('wal-ch').value;
    UI.toast('جاري الإنشاء...');
    const d = await API.generateWallet(chain);
    if(d?.address) {
      document.getElementById('wal-res').style.display = 'block';
      document.getElementById('new-addr').textContent = d.address;
      document.getElementById('new-seed').textContent = d.seed_phrase;
      document.getElementById('wal-addr').textContent = d.address;
      UI.toast(`✓ محفظة ${chain.toUpperCase()} جاهزة`);
    } else {
      UI.toast('فشل الإنشاء');
    }
  },

  calcWithdraw() {
    const v = parseFloat(document.getElementById('wit-a')?.value)||0;
    document.getElementById('wit-g').textContent = '$'+(v*CONFIG.GAS_FEE_PERCENT).toFixed(2);
    document.getElementById('wit-r').textContent = (v - v*CONFIG.GAS_FEE_PERCENT).toFixed(2);
  },

  init() {
    // تحديث الأرصدة عند تحديث الأسعار
    BUS.on('ws:prices', (prices) => {
      STATE.prices = prices;
      if(STATE.currentScreen === 3) this._renderAssets();
      else this._updatePortCards(prices);
    });
  },

  _updatePortCards(P) {
    const f = v => v.toLocaleString('en',{maximumFractionDigits:0});
    if(P.BTCUSDT) {
      const v = 0.012 * P.BTCUSDT.price;
      document.getElementById('btc-u').textContent = '≈ $'+f(v);
      const up = P.BTCUSDT.change >= 0;
      const e = document.getElementById('btc-ch');
      if(e) { e.className=up?'up':'dn'; e.textContent=(up?'+':'')+P.BTCUSDT.change.toFixed(2)+'%'; }
    }
    if(P.SOLUSDT) {
      const v = 12.4 * P.SOLUSDT.price;
      document.getElementById('sol-u').textContent = '≈ $'+f(v);
      const up = P.SOLUSDT.change >= 0;
      const e = document.getElementById('sol-ch');
      if(e) { e.className=up?'up':'dn'; e.textContent=(up?'+':'')+P.SOLUSDT.change.toFixed(2)+'%'; }
    }
    if(P.ETHUSDT) {
      const v = 0.48 * P.ETHUSDT.price;
      document.getElementById('eth-u').textContent = '≈ $'+f(v);
      const up = P.ETHUSDT.change >= 0;
      const e = document.getElementById('eth-ch');
      if(e) { e.className=up?'up':'dn'; e.textContent=(up?'+':'')+P.ETHUSDT.change.toFixed(2)+'%'; }
    }
  },
};
