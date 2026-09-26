// Servidor mínimo: estático (página + painel) + API de acesso pós-compra (webhook Wiven).
// Sem dependências. Persistência: JSON em DATA_DIR (volume persistente).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PORT = Number(process.env.PORT || 80);
const DATA_DIR = process.env.DATA_DIR || path.join(ROOT, '.data');
const DB_FILE = path.join(DATA_DIR, 'compras.json');
const WEBHOOK_TOKEN = process.env.WIVEN_WEBHOOK_TOKEN || '';
const SESSION_SECRET = process.env.SESSION_SECRET || WEBHOOK_TOKEN;
const SESSION_TTL = 30 * 24 * 3600; // s

// Produto Wiven -> SKUs do painel.
const PRODUCT_SKUS = {
  cmubqz6yu010o01pqgcgfw6j0: ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4'],
  cmubsge6l026s01pux12tog1s: ['guia-flash'],
  cmubsk2bd023001pqtloo3zrz: ['perguntas-80'],
  cmubsl72o023t01pq3y1awjpj: ['folha-consulta'],
  cmubwg9a3052l01puaww8hmir: ['combo-3-bonus', 'guia-flash', 'perguntas-80', 'folha-consulta'],
};
// Ofertas do produto principal que incluem o Nível Completo.
const COMPLETO_OFFERS = new Set(['I38JADD', 'IIUQ8EW']);
const NOT_PAID_EVENT = /CREATED|CANCEL|REFUND|CHARGEBACK|CONTEST|MED|ABANDON|SESSION|TRANSFER|UPDATED/i;

fs.mkdirSync(DATA_DIR, { recursive: true });
let db = { tx: {}, buyers: {} }; // tx: id -> true ; buyers: email -> { skus: [], name }
try { db = JSON.parse(fs.readFileSync(DB_FILE, 'utf8')); } catch {}
function save() {
  const tmp = DB_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(db));
  fs.renameSync(tmp, DB_FILE);
}

const safeEq = (a, b) => {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
};
const sign = (v) => crypto.createHmac('sha256', SESSION_SECRET).update(v).digest('base64url');
function makeCookie(email) {
  const v = `${Buffer.from(email).toString('base64url')}.${Math.floor(Date.now() / 1000) + SESSION_TTL}`;
  return `${v}.${sign(v)}`;
}
function cookieEmail(req) {
  const m = /(?:^|;\s*)mdt_s=([^;]+)/.exec(req.headers.cookie || '');
  if (!m || !SESSION_SECRET) return null;
  const [e, exp, sig] = m[1].split('.');
  if (!e || !exp || !sig || !safeEq(sig, sign(`${e}.${exp}`)) || Number(exp) < Date.now() / 1000) return null;
  return Buffer.from(e, 'base64url').toString();
}
// Conta de demonstração (análise Mundpay): acesso completo sem compra, exige senha.
const DEMO_SKUS = ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4', 'completo', 'guia-flash', 'perguntas-80', 'folha-consulta', 'combo-3-bonus'];
const DEMO_USERS = { 'teste-mundpay@leadgo.dev': '4a3b0f722b261541514f159a10cb54db025947da3eb1773d798c5f8f9ef8981d' };
const DEMO_SALT = 'mdt-demo-salt';
for (const e of Object.keys(DEMO_USERS)) db.buyers[e] = { skus: DEMO_SKUS.slice(), name: 'Teste Mundpay' };
const demoOk = (email, pw) => DEMO_USERS[email] && safeEq(crypto.scryptSync(String(pw || ''), DEMO_SALT, 32).toString('hex'), DEMO_USERS[email]);
const owned = (email) => (db.buyers[email] ? db.buyers[email].skus.slice() : null);

// rate limit simples por IP
const hits = new Map();
function limited(req, max) {
  const ip = String(req.headers['x-forwarded-for'] || req.socket.remoteAddress).split(',')[0].trim();
  const now = Date.now(), arr = (hits.get(ip) || []).filter((t) => now - t < 60000);
  arr.push(now); hits.set(ip, arr);
  return arr.length > max;
}

function readBody(req, limit = 256 * 1024) {
  return new Promise((resolve, reject) => {
    let n = 0; const c = [];
    req.on('data', (d) => { n += d.length; if (n > limit) { reject(new Error('big')); req.destroy(); } else c.push(d); });
    req.on('end', () => resolve(Buffer.concat(c).toString('utf8')));
    req.on('error', reject);
  });
}
const json = (res, code, obj, headers = {}) => {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers });
  res.end(JSON.stringify(obj));
};

function handleWebhook(payload) {
  const tx = payload.transaction || {};
  const event = String(payload.event || '');
  const paid = String(tx.status || '').toUpperCase() === 'COMPLETED' || /PAID/i.test(event);
  if (!paid || NOT_PAID_EVENT.test(event.replace(/PAID/i, ''))) return { code: 200, body: { ok: true, ignored: 'not-paid-event' } };
  const email = String((payload.client || {}).email || '').trim().toLowerCase();
  if (!email || !tx.id) return { code: 400, body: { ok: false, error: 'missing-email-or-transaction' } };
  if (db.tx[tx.id]) return { code: 200, body: { ok: true, duplicate: true } };
  const skus = new Set();
  for (const item of tx.orderItems || []) {
    const pid = item && item.product && item.product.id;
    (PRODUCT_SKUS[pid] || []).forEach((s) => skus.add(s));
    if (pid === 'cmubqz6yu010o01pqgcgfw6j0' && COMPLETO_OFFERS.has(String(payload.offerCode || ''))) skus.add('completo');
  }
  if (!skus.size) return { code: 200, body: { ok: true, ignored: 'no-known-product' } };
  const b = db.buyers[email] || { skus: [], name: (payload.client || {}).name || '' };
  b.skus = [...new Set([...b.skus, ...skus])];
  db.buyers[email] = b;
  db.tx[tx.id] = true;
  save();
  return { code: 200, body: { ok: true, granted: [...skus] } };
}

const MIME = { '.html': 'text/html; charset=utf-8', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.css': 'text/css', '.js': 'text/javascript', '.mp4': 'video/mp4', '.json': 'application/json', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };

function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  if (rel === '/painel') rel = '/painel/index.html';
  if (rel === '/pt') rel = '/pt/index.html';
  if (rel === '/termos' || rel === '/pt/termos') rel = '/termos.html';
  if (rel === '/privacidade' || rel === '/pt/privacidade') rel = '/privacidade.html';
  if (rel === '/pt/painel' || rel === '/pt/painel/index.html') rel = '/painel/index-pt.html';
  const abs = path.join(ROOT, rel);
  const top = rel.split('/')[1];
  if (!abs.startsWith(ROOT + path.sep) || !(rel === '/index.html' || rel === '/pt/index.html' || rel === '/termos.html' || rel === '/privacidade.html' || top === 'assets' || top === 'painel')) return json(res, 404, { error: 'not-found' });
  // conteúdo pago: exige sessão + ownership do SKU
  const m = /^\/painel\/conteudo\/([^/]+)\//.exec(rel);
  if (m) {
    const o = owned(cookieEmail(req) || '');
    if (!o || !o.includes(m[1])) return json(res, 403, { error: 'forbidden' });
  }
  fs.stat(abs, (err, st) => {
    if (err || !st.isFile()) return json(res, 404, { error: 'not-found' });
    res.writeHead(200, { 'content-type': MIME[path.extname(abs)] || 'application/octet-stream', 'content-length': st.size, 'cache-control': m ? 'private, max-age=3600' : 'public, max-age=300' });
    fs.createReadStream(abs).pipe(res);
  });
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  try {
    if (p === '/painel/api/webhooks/wiven') {
      if (req.method !== 'POST') return json(res, 405, { error: 'method' });
      if (!WEBHOOK_TOKEN) return json(res, 503, { error: 'not-configured' });
      let payload;
      try { payload = JSON.parse(await readBody(req)); } catch { return json(res, 400, { error: 'bad-json' }); }
      const t = payload.token || (req.headers.authorization || '').replace(/^Bearer\s+/i, '') || req.headers['x-webhook-token'];
      if (!t || !safeEq(t, WEBHOOK_TOKEN)) return json(res, 401, { error: 'invalid-token' });
      const r = handleWebhook(payload);
      return json(res, r.code, r.body);
    }
    if (p === '/painel/api/login') {
      if (req.method !== 'POST') return json(res, 405, { error: 'method' });
      if (limited(req, 20)) return json(res, 429, { error: 'rate-limit' });
      let b; try { b = JSON.parse(await readBody(req, 4096)); } catch { return json(res, 400, { error: 'bad-json' }); }
      const email = String(b.email || '').trim().toLowerCase();
      const o = owned(email);
      if (!o) return json(res, 404, { error: 'not-found' });
      if (DEMO_USERS[email] && !demoOk(email, b.password)) return json(res, 401, { error: 'bad-password' });
      return json(res, 200, { ok: true, owned: o }, { 'set-cookie': `mdt_s=${makeCookie(email)}; Path=/painel; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_TTL}` });
    }
    if (p === '/painel/api/me') {
      const email = cookieEmail(req);
      const o = email && owned(email);
      return o ? json(res, 200, { ok: true, email, owned: o }) : json(res, 401, { error: 'no-session' });
    }
    if (p === '/painel/api/logout') return json(res, 200, { ok: true }, { 'set-cookie': 'mdt_s=; Path=/painel; HttpOnly; Secure; SameSite=Lax; Max-Age=0' });
    if (p.startsWith('/painel/api/')) return json(res, 404, { error: 'not-found' });
    if (req.method !== 'GET' && req.method !== 'HEAD') return json(res, 405, { error: 'method' });
    serveStatic(req, res, p);
  } catch (e) {
    console.error('erro', e.message);
    json(res, 500, { error: 'internal' });
  }
}).listen(PORT, () => console.log('mapa-do-tarot up :' + PORT));
