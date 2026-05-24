/**
 * chat.js — WhaleX Prime
 * ══════════════════════════════════════
 * AI Chat — متخصص بالكريبتو فقط.
 * مستقل تماماً — لا يعتمد على وحدة أخرى.
 * ══════════════════════════════════════
 */

const CHAT = {

  // كلمات مفتاحية للتحقق من أن السؤال عن الكريبتو
  _keywords: ['سوق','عملة','تداول','كريبتو','bitcoin','ethereum','solana','rug','liquidation','cvd','futures','spot','مؤشر','rsi','macd','تحليل','إشارة','whale','حوت','binance','bybit','دخول','خروج','ربح','خسارة','رافعة','استراتيجية','فيوتشر','بيتكوين','fvg','delta','order','blockchain','defi','token','pump','dump','short','long','meme','dex','cex','swap','liquidity','contract','nft','altcoin','stablecoin','usdt','usdc','bnb','whalex','whalemind','whale','منصة','بوت','رادار','إشارة','اشتراك','محفظة','scanner','swap','تداول','كيف','يعمل','ما هو'],

  _isCrypto(text) {
    const l = text.toLowerCase();
    return this._keywords.some(k => l.includes(k));
  },

  init() {
    const area = document.getElementById('chat-area');
    if(area && !area.children.length) {
      area.innerHTML = this._buildMsg('ai',
        'مرحباً! أنا WhaleX AI 🤖\n\n' +
        'محلل مالي متخصص في الكريبتو فقط.\n\n' +
        'أساعدك في:\n' +
        '• تحليل السوق والمؤشرات\n' +
        '• شرح CVD وFVG وLiquidation Cascade\n' +
        '• فحص عقود Meme Coins\n' +
        '• إدارة المخاطر والرافعة المالية\n\n' +
        '⚠️ لا أجيب على أسئلة خارج نطاق الكريبتو.'
      );
      STATE.chatHistory = [];
    }
  },

  _buildMsg(role, text) {
    const tm = new Date().toLocaleTimeString('ar',{hour:'2-digit',minute:'2-digit'});
    const tx = text.replace(/\n/g,'<br>');
    if(role === 'ai') {
      return `<div class="msg ai">
        <div class="m-av ai"><svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" stroke-width="2"/></svg></div>
        <div><div class="m-bub">${tx}</div><div style="font-size:10px;color:var(--text3);margin-top:3px">${tm}</div></div>
      </div>`;
    }
    return `<div class="msg usr">
      <div class="m-av usr">أ</div>
      <div><div class="m-bub">${tx}</div><div style="font-size:10px;color:var(--text3);margin-top:3px;text-align:left">${tm}</div></div>
    </div>`;
  },

  async send() {
    const inp = document.getElementById('chat-inp');
    const text = inp?.value?.trim();
    if(!text) return;
    inp.value = '';

    const area = document.getElementById('chat-area');
    area.innerHTML += this._buildMsg('usr', text);
    STATE.chatHistory.push({role:'user', content:text});

    // فلتر الكريبتو
    if(!this._isCrypto(text)) {
      const r = 'أنا متخصص في الكريبتو والتداول فقط 🤖\nهل لديك سؤال عن السوق أو العملات الرقمية؟';
      STATE.chatHistory.push({role:'assistant', content:r});
      area.innerHTML += this._buildMsg('ai', r);
      area.scrollTop = area.scrollHeight;
      return;
    }

    // مؤشر الكتابة
    area.innerHTML += `<div class="msg ai" id="chat-typing">
      <div class="m-av ai"></div>
      <div class="m-bub"><div class="typing"><div class="td"></div><div class="td"></div><div class="td"></div></div></div>
    </div>`;
    area.scrollTop = area.scrollHeight;

    const d = await API.chat(STATE.chatHistory.slice(-10));
    const reply = d?.reply || 'حدث خطأ في الاتصال. حاول مرة أخرى.';

    document.getElementById('chat-typing')?.remove();
    STATE.chatHistory.push({role:'assistant', content:reply});
    area.innerHTML += this._buildMsg('ai', reply);
    area.scrollTop = area.scrollHeight;
  },

  sendQuestion(q) {
    const inp = document.getElementById('chat-inp');
    if(inp) inp.value = q;
    this.send();
  },

  askAbout(symbol, direction, grade) {
    ROUTER.go(5);
    this.sendQuestion(`حلل إشارة ${symbol} ${direction} درجة ${grade} وأعطني رأيك`);
  },
};
