/**
 * config.js — WhaleX Prime
 * ══════════════════════════════════════
 * كل الإعدادات في مكان واحد.
 * أي تعديل يتم هنا فقط.
 * ══════════════════════════════════════
 */

const CONFIG = Object.freeze({

  // ── API & WebSocket ──────────────────
  API:    'https://api.whalemindhybridai.online',
  WS_URL: 'wss://ws.whalemindhybridai.online/ws/live',

  // ── Admin ────────────────────────────
  ADMIN_PASSWORD: 'whalex2026admin',

  // ── WebSocket ────────────────────────
  WS_PING_INTERVAL: 25000,   // ms
  WS_MAX_RETRY_MS:  30000,   // ms
  WS_BASE_RETRY_MS: 3000,    // ms

  // ── Signals ──────────────────────────
  SIGNALS_LIMIT: 10,

  // ── Gas Protection ───────────────────
  GAS_FEE_PERCENT: 0.01,     // 1%
  MIN_GAS_BALANCE: 5,        // USDT

  // ── Referral ─────────────────────────
  REFERRAL_BASE_URL: 'whalexapp.io/ref/',

  // ── منصات التداول ────────────────────
  // لإضافة منصة جديدة: أضف كائن هنا فقط
  PLATFORMS: {
    dex: [
      { v:'jupiter',   n:'Jupiter',     s:'Solana',  logo:'https://jup.ag/favicon.ico' },
      { v:'raydium',   n:'Raydium',     s:'Solana',  logo:'https://raydium.io/favicon.ico' },
      { v:'orca',      n:'Orca',        s:'Solana',  logo:'https://www.orca.so/favicon.ico' },
      { v:'uniswap',   n:'Uniswap',     s:'ETH/ARB', logo:'https://app.uniswap.org/favicon.ico' },
      { v:'gmx',       n:'GMX',         s:'ARB',     logo:'https://gmx.io/favicon.ico' },
      { v:'pancake',   n:'PancakeSwap', s:'BSC',     logo:'https://pancakeswap.finance/favicon.ico' },
      { v:'sushi',     n:'SushiSwap',   s:'Multi',   logo:'https://www.sushi.com/favicon.ico' },
      { v:'dydx',      n:'dYdX',        s:'ETH',     logo:'https://dydx.exchange/favicon.ico' },
    ],
    cex: [
      { v:'binance',   n:'Binance',     s:'CEX', logo:'https://bin.bnbstatic.com/static/images/common/favicon.ico' },
      { v:'bybit',     n:'Bybit',       s:'CEX', logo:'https://www.bybit.com/favicon.ico' },
      { v:'okx',       n:'OKX',         s:'CEX', logo:'https://www.okx.com/favicon.ico' },
      { v:'kucoin',    n:'KuCoin',      s:'CEX', logo:'https://www.kucoin.com/favicon.ico' },
      { v:'gate',      n:'Gate.io',     s:'CEX', logo:'https://www.gate.io/favicon.ico' },
      { v:'bitget',    n:'Bitget',      s:'CEX', logo:'https://www.bitget.com/favicon.ico' },
      { v:'mexc',      n:'MEXC',        s:'CEX', logo:'https://www.mexc.com/favicon.ico' },
      { v:'htx',       n:'HTX',         s:'CEX', logo:'https://www.htx.com/favicon.ico' },
    ]
  },

  // ── الشبكات ───────────────────────────
  // لإضافة شبكة جديدة: أضف هنا فقط
  CHAINS: [
    { id:'sol',  name:'Solana',    symbol:'SOL',  color:'#9945ff', icon:'SOL' },
    { id:'eth',  name:'Ethereum',  symbol:'ETH',  color:'#6288f5', icon:'ETH' },
    { id:'bsc',  name:'BSC',       symbol:'BNB',  color:'#f0b90b', icon:'BNB' },
    { id:'arb',  name:'Arbitrum',  symbol:'ARB',  color:'#12aaff', icon:'ARB' },
    { id:'base', name:'Base',      symbol:'BASE', color:'#0052ff', icon:'BASE'},
    { id:'tron', name:'Tron',      symbol:'TRX',  color:'#ff060a', icon:'TRX' },
    { id:'btc',  name:'Bitcoin',   symbol:'BTC',  color:'#f7931a', icon:'BTC' },
    { id:'poly', name:'Polygon',   symbol:'MATIC',color:'#8247e5', icon:'MATIC'},
  ],

  // ── أصول المحفظة الافتراضية ──────────
  DEFAULT_ASSETS: [
    { symbol:'BTC',  name:'Bitcoin',  network:'Bitcoin',      amount:0.012, color:'#f7931a' },
    { symbol:'USDT', name:'USDT',     network:'SOL·ETH·TRC20',amount:1240,  color:'#26a17b' },
    { symbol:'USDC', name:'USDC',     network:'SOL·ETH·BASE', amount:380,   color:'#2775ca' },
    { symbol:'SOL',  name:'Solana',   network:'Solana',       amount:12.4,  color:'#9945ff' },
    { symbol:'ETH',  name:'Ethereum', network:'ERC-20',       amount:0.48,  color:'#6288f5' },
    { symbol:'BNB',  name:'BNB',      network:'BEP-20',       amount:3.2,   color:'#f0b90b' },
  ],

});
