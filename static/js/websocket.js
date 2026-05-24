/**
 * websocket.js — WhaleX Prime
 * ══════════════════════════════════════
 * إدارة WebSocket بشكل مستقل.
 * ينشر الأحداث عبر BUS.
 * ══════════════════════════════════════
 */

const WS_CLIENT = {
  _ws: null,
  _pingInterval: null,
  _retries: 0,

  connect() {
    if(this._ws?.readyState === WebSocket.OPEN) return;

    this._ws = new WebSocket(CONFIG.WS_URL);

    this._ws.onopen = () => {
      this._retries = 0;
      this._startPing();
      BUS.emit('ws:connected', null);
      UI.toast('● متصل بالرادار', 1500);
    };

    this._ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        switch(msg.event) {
          case 'prices': BUS.emit('ws:prices', msg.data); break;
          case 'signal': BUS.emit('ws:signal', msg.data); break;
          case 'alert':
            // تنبيه من مدير الصفقات
            const alertMsg = msg.message || '';
            UI.toast('⚠️ ' + alertMsg.replace(/<[^>]*>/g,'').slice(0,60), 4000);
            BUS.emit('ws:alert', msg);
            break;
          case 'pong':   break;
          default:       BUS.emit('ws:'+msg.event, msg.data);
        }
      } catch(err) {
        console.error('WS parse error:', err);
      }
    };

    this._ws.onclose = () => {
      this._stopPing();
      BUS.emit('ws:disconnected', null);
      this._reconnect();
    };

    this._ws.onerror = () => this._ws.close();
  },

  send(event, data = {}) {
    if(this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify({ event, ...data }));
    }
  },

  _startPing() {
    this._pingInterval = setInterval(() => {
      this.send('ping');
    }, CONFIG.WS_PING_INTERVAL);
  },

  _stopPing() {
    if(this._pingInterval) {
      clearInterval(this._pingInterval);
      this._pingInterval = null;
    }
  },

  _reconnect() {
    this._retries++;
    const delay = Math.min(CONFIG.WS_BASE_RETRY_MS * this._retries, CONFIG.WS_MAX_RETRY_MS);
    setTimeout(() => this.connect(), delay);
  },

  disconnect() {
    this._stopPing();
    this._ws?.close();
  },
};
