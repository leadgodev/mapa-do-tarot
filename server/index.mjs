// Servidor mínimo: estático (página + painel) + API de acesso pós-compra (webhook Wiven).
// Sem dependências. Persistência: JSON em DATA_DIR (volume persistente).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { sendAccessEmail } from './mail.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PORT = Number(process.env.PORT || 80);
const DATA_DIR = process.env.DATA_DIR || path.join(ROOT, '.data');
const DB_FILE = path.join(DATA_DIR, 'compras.json');
const WEBHOOK_TOKEN = process.env.WIVEN_WEBHOOK_TOKEN || '';
const MUNDPAY_WEBHOOK_TOKEN = process.env.MUNDPAY_WEBHOOK_TOKEN || '';
const SESSION_SECRET = process.env.SESSION_SECRET || WEBHOOK_TOKEN || MUNDPAY_WEBHOOK_TOKEN;
const SESSION_TTL = 30 * 24 * 3600; // s

// Gerador de PDF para módulos Cigano via Chromium headless
function generatePDF(moduleKey, outputPath, callback) {
  const htmlPath = path.join(ROOT, 'painel', 'conteudo', moduleKey, 'index.html');
  if (!fs.existsSync(htmlPath)) return callback(new Error('html-not-found'));
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const args = ['--headless', '--disable-gpu', `--print-to-pdf=${outputPath}`, `file://${htmlPath}`];
  execFile('chromium', args, { timeout: 30000 }, (err) => {
    if (err && err.code === 'ENOENT') {
      return execFile('chromium-browser', args, { timeout: 30000 }, callback);
    }
    callback(err);
  });
}

// Produto Wiven -> SKUs do painel.
const PRODUCT_SKUS = {
  cmubqz6yu010o01pqgcgfw6j0: ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4'],
  cmubsge6l026s01pux12tog1s: ['guia-flash'],
  cmubsk2bd023001pqtloo3zrz: ['perguntas-80'],
  cmubsl72o023t01pq3y1awjpj: ['folha-consulta'],
  cmubwg9a3052l01puaww8hmir: ['combo-3-bonus', 'guia-flash', 'perguntas-80', 'folha-consulta'],
  // Mapa do Baralho Cigano: principal e order bumps da página pública.
  cmulz3f9a020701oo4fstsegf: ['cigano'],
  cmurhf87201cu01q2wh0whdz0: ['cigano'], // Guia Flash 36 Cartas
  cmurhgvnj01ff01q2jkkz4xx7: ['cigano'], // Perguntas que Destravam a Leitura
};
// Ofertas do produto principal que incluem o Nível Completo.
const COMPLETO_OFFERS = new Set(['I38JADD', 'IIUQ8EW', 'G8MYTZF']);
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
// Contas de demonstração/teste: acesso completo sem compra. Login só por e-mail,
// sem senha — a área de membros inteira é e-mail-only (regra da dona, 29/09/2026).
const DEMO_SKUS = ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4', 'completo', 'guia-flash', 'perguntas-80', 'folha-consulta', 'combo-3-bonus', 'cigano'];
for (const e of ['teste-mundpay@leadgo.dev', 'teste-4423c38c@leadgo.dev']) db.buyers[e] = { skus: DEMO_SKUS.slice(), name: 'Teste' };
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
  for (const item of (payload.orderItems || tx.orderItems || [])) {
    const pid = item && item.product && item.product.id;
    (PRODUCT_SKUS[pid] || []).forEach((s) => skus.add(s));
    if (pid === 'cmubqz6yu010o01pqgcgfw6j0' && COMPLETO_OFFERS.has(String(payload.offerCode || ''))) skus.add('completo');
  }
  // Baralho Cigano ("- Área de Membros", 29/09/2026): produto novo, sem o id interno
  // do webhook confirmado ainda (só temos o id da URL de checkout, que a Wiven usa
  // diferente do product.id do payload). Casa pelo offerCode, que é único por oferta
  // -- não depende do product id.
  if (String(payload.offerCode || '') === 'JXE3KNA') skus.add('cigano');
  if (!skus.size) return { code: 200, body: { ok: true, ignored: 'no-known-product' } };
  const b = db.buyers[email] || { skus: [], name: (payload.client || {}).name || '' };
  const novos = [...skus].filter((s) => !b.skus.includes(s));
  b.skus = [...new Set([...b.skus, ...skus])];
  db.buyers[email] = b;
  db.tx[tx.id] = true;
  save();
  if (novos.length) sendAccessEmail(email, b.name, [...skus]).then((id) => console.log('access-email sent', id), (e) => console.error('access-email failed', e.message));
  return { code: 200, body: { ok: true, granted: [...skus] } };
}

// Mercado PT (Mundpay). Payload confirmado via "Testar Webhook" do painel Mundpay em 2026-09-29
// (não verificado ainda numa venda real): { id, event_type, customer:{email,name}, offers:[{id,name,type,sku}],
// amount, currency, status }. status 'paid' = pago. Sem HMAC/assinatura visível no teste — segurança
// via token na querystring da URL de postback (?token=...), igual ao padrão do webhook Wiven.
// offers[].name é o nome de exibição da OFERTA específica comprada (ex.: "Mapa do Tarot Essencial - PT –
// 80 Perguntas Poderosas - PT"), não do produto — por isso o SKU é resolvido casando por trecho do nome,
// não por offers[].id (que no teste veio igual ao id do PRODUTO, não da oferta individual).
const MUNDPAY_NAME_SKUS = [
  [/leve os 3 com desconto/i, ['combo-3-bonus', 'guia-flash', 'perguntas-80', 'folha-consulta']],
  [/80 perguntas poderosas/i, ['perguntas-80']],
  [/folha de consulta/i, ['folha-consulta']],
  [/guia flash/i, ['guia-flash']],
  [/oferta especial/i, ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4', 'completo']],
  [/completo/i, ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4', 'completo']],
  [/essencial/i, ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4']],
  [/b[aá]sico.*(es|spanish|español)?/i, ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4']],
];
function handleMundpayWebhook(payload) {
  const paid = String(payload.status || '').toLowerCase() === 'paid' || /\.paid$/i.test(String(payload.event_type || ''));
  if (!paid) return { code: 200, body: { ok: true, ignored: 'not-paid-event' } };
  const email = String((payload.customer || {}).email || '').trim().toLowerCase();
  const txId = String(payload.id || '');
  if (!email || !txId) return { code: 400, body: { ok: false, error: 'missing-email-or-transaction' } };
  const txKey = 'mundpay:' + txId;
  if (db.tx[txKey]) return { code: 200, body: { ok: true, duplicate: true } };
  const skus = new Set();
  let lang = null;
  for (const offer of (payload.offers || [])) {
    const name = String(offer.name || (offer.product || {}).name || '');
    if (/\s-\s(ES|es|Spanish|spanish|Español|español)$/i.test(name)) lang = 'es';
    for (const [re, mapped] of MUNDPAY_NAME_SKUS) {
      if (re.test(name)) { mapped.forEach((s) => skus.add(s)); break; }
    }
  }
  if (String(payload.currency || '').toUpperCase() === 'USD') lang = 'es';
  if (!skus.size) return { code: 200, body: { ok: true, ignored: 'no-known-offer' } };
  const b = db.buyers[email] || { skus: [], name: (payload.customer || {}).name || '' };
  if (lang) b.lang = lang;
  else if (!b.lang) b.lang = 'pt';
  const novos = [...skus].filter((s) => !b.skus.includes(s));
  b.skus = [...new Set([...b.skus, ...skus])];
  db.buyers[email] = b;
  db.tx[txKey] = true;
  save();
  if (novos.length) sendAccessEmail(email, b.name, [...skus], b.lang).then((id) => console.log('access-email sent (mundpay)', id), (e) => console.error('access-email failed (mundpay)', e.message));
  return { code: 200, body: { ok: true, granted: [...skus] } };
}

const MIME = { '.html': 'text/html; charset=utf-8', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.css': 'text/css', '.js': 'text/javascript', '.mp4': 'video/mp4', '.json': 'application/json', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };

function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  if (rel === '/es' || rel === '/es/') rel = '/es/index.html';
  if (rel === '/es/termos') rel = '/es/termos.html';
  if (rel === '/es/privacidade') rel = '/es/privacidade.html';
  if (rel === '/painel' || rel === '/painel/index.html') rel = '/painel/index.html';
  if (rel === '/pt' || rel === '/pt/') rel = '/pt/index.html';
  if (rel === '/termos' || rel === '/pt/termos') rel = '/termos.html';
  if (rel === '/privacidade' || rel === '/pt/privacidade') rel = '/privacidade.html';
  if (rel === '/pt/painel' || rel === '/pt/painel/index.html') rel = '/painel/index-pt.html';
  if (rel === '/es/painel' || rel === '/es/painel/index.html') rel = '/painel/index-es.html';
  if (rel.startsWith('/es/assets/') && !fs.existsSync(path.join(ROOT, rel))) rel = rel.slice(3);
  const abs = path.join(ROOT, rel);
  const top = rel.split('/')[1];
  if (top === 'es' && !rel.startsWith('/es/assets/') && !rel.endsWith('.html')) return json(res, 404, { error: 'not-found' });
  if (!abs.startsWith(ROOT + path.sep) || !(rel === '/index.html' || rel === '/es/index.html' || rel === '/pt/index.html' || rel === '/termos.html' || rel === '/privacidade.html' || rel === '/es/termos.html' || rel === '/es/privacidade.html' || top === 'assets' || top === 'painel' || top === 'es' || top === 'upsell-cigano' || top === 'js')) return json(res, 404, { error: 'not-found' });
  // conteúdo pago: exige sessão + ownership do SKU
  const m = /^\/painel\/conteudo\/([^/]+)\//.exec(rel);
  const mEs = /^\/painel\/conteudo-es\/([^/]+)\//.exec(rel);
  if (m) {
    const o = owned(cookieEmail(req) || '');
    const skuToCheck = m[1].startsWith('cigano-') || m[1] === 'cigano' ? 'cigano' : m[1];
    if (!o || !o.includes(skuToCheck)) return json(res, 403, { error: 'forbidden' });
  }
  if (mEs) {
    const o = owned(cookieEmail(req) || '');
    const skuToCheck = mEs[1].startsWith('cigano-') || mEs[1] === 'cigano' ? 'cigano' : mEs[1];
    if (!o || !o.includes(skuToCheck)) return json(res, 403, { error: 'forbidden' });
  }
  // App de Treino: bônus exclusivo do Nível Completo (SKU 'completo').
  if (rel === '/painel/treino' || rel.startsWith('/painel/treino/')) {
    const o = owned(cookieEmail(req) || '');
    if (!o || !o.includes('completo')) {
      res.writeHead(302, { location: '/painel' });
      return res.end();
    }
  }
  fs.stat(abs, (err, st) => {
    if (err || !st.isFile()) return json(res, 404, { error: 'not-found' });
    const ext = path.extname(abs).toLowerCase();
    const cacheControl = (m || mEs) ? 'private, max-age=3600' : (ext === '.html' ? 'public, max-age=300, must-revalidate' : 'public, max-age=31536000, immutable');
    res.writeHead(200, { 'content-type': MIME[ext] || 'application/octet-stream', 'content-length': st.size, 'cache-control': cacheControl });
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
    if (p === '/painel/api/webhooks/mundpay') {
      if (req.method !== 'POST') return json(res, 405, { error: 'method' });
      if (!MUNDPAY_WEBHOOK_TOKEN) return json(res, 503, { error: 'not-configured' });
      const t = url.searchParams.get('token') || (req.headers.authorization || '').replace(/^Bearer\s+/i, '') || req.headers['x-webhook-token'];
      if (!t || !safeEq(t, MUNDPAY_WEBHOOK_TOKEN)) return json(res, 401, { error: 'invalid-token' });
      let payload;
      try { payload = JSON.parse(await readBody(req)); } catch { return json(res, 400, { error: 'bad-json' }); }
      const r = handleMundpayWebhook(payload);
      return json(res, r.code, r.body);
    }
    if (p === '/painel/api/login') {
      if (req.method !== 'POST') return json(res, 405, { error: 'method' });
      if (limited(req, 20)) return json(res, 429, { error: 'rate-limit' });
      let b; try { b = JSON.parse(await readBody(req, 4096)); } catch { return json(res, 400, { error: 'bad-json' }); }
      const email = String(b.email || '').trim().toLowerCase();
      const o = owned(email);
      if (!o) return json(res, 404, { error: 'not-found' });
      const lang = db.buyers[email]?.lang || 'pt';
      return json(res, 200, { ok: true, owned: o, lang }, { 'set-cookie': `mdt_s=${makeCookie(email)}; Path=/painel; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_TTL}` });
    }
    if (p === '/painel/api/me') {
      const email = cookieEmail(req);
      const o = email && owned(email);
      if (!o) return json(res, 401, { error: 'no-session' });
      const lang = db.buyers[email]?.lang || 'pt';
      return json(res, 200, { ok: true, email, owned: o, lang });
    }
    if (p === '/painel/api/logout') return json(res, 200, { ok: true }, { 'set-cookie': 'mdt_s=; Path=/painel; HttpOnly; Secure; SameSite=Lax; Max-Age=0' });
    if (p === '/painel/api/treino/progresso') {
      const email = cookieEmail(req);
      if (!email) return json(res, 401, { error: 'no-session' });
      const o = owned(email);
      if (!o || !o.includes('completo')) return json(res, 403, { error: 'forbidden' });
      if (req.method === 'GET') return json(res, 200, { ok: true, progresso: (db.buyers[email] && db.buyers[email].treino) || null });
      if (req.method === 'POST') {
        let b; try { b = JSON.parse(await readBody(req, 64 * 1024)); } catch { return json(res, 400, { error: 'bad-json' }); }
        db.buyers[email].treino = b.progresso || {};
        save();
        return json(res, 200, { ok: true });
      }
      return json(res, 405, { error: 'method' });
    }
    if (p.startsWith('/painel/api/modulo-pdf/')) {
      const m = /^\/painel\/api\/modulo-pdf\/([^/]+)$/.exec(p);
      if (!m) return json(res, 404, { error: 'not-found' });
      const email = cookieEmail(req);
      const o = email && owned(email);
      const sku = m[1];
      const skuToCheck = sku.startsWith('cigano-') || sku === 'cigano' ? 'cigano' : sku;
      if (!o || !o.includes(skuToCheck)) return json(res, 403, { error: 'forbidden' });
      const pdfPath = path.join(ROOT, 'painel', url.searchParams.get('lang') === 'es' ? 'conteudo-es' : 'conteudo', sku, sku + '.pdf');
      if (fs.existsSync(pdfPath)) {
        const st = fs.statSync(pdfPath);
        return res.writeHead(200, { 'content-type': 'application/pdf', 'content-length': st.size, 'cache-control': 'public, max-age=86400' }), fs.createReadStream(pdfPath).pipe(res);
      }
      if (sku.startsWith('cigano-') && url.searchParams.get('lang') !== 'es') {
        generatePDF(sku, pdfPath, (err) => {
          if (err) return json(res, 500, { error: 'pdf-generation-failed' });
          const st = fs.statSync(pdfPath);
          res.writeHead(200, { 'content-type': 'application/pdf', 'content-length': st.size, 'cache-control': 'public, max-age=86400' });
          fs.createReadStream(pdfPath).pipe(res);
        });
        return;
      }
      return json(res, 404, { error: 'pdf-not-found' });
    }
    // Compatibilidade: /painel/api/cigano-pdf/* redireciona para /painel/api/modulo-pdf/*
    if (p.startsWith('/painel/api/cigano-pdf/')) {
      const m = /^\/painel\/api\/cigano-pdf\/(.+)$/.exec(p);
      if (!m) return json(res, 404, { error: 'not-found' });
      res.writeHead(301, { location: '/painel/api/modulo-pdf/' + m[1] });
      return res.end();
    }
    if (p === '/painel/api/conteudo-es/manifest') {
      const email = cookieEmail(req);
      if (!email) return json(res, 401, { error: 'no-session' });
      const owned_skus = owned(email);
      if (!owned_skus) return json(res, 403, { error: 'forbidden' });
      const manifest = {};
      for (const sku of owned_skus) {
        const dir = path.join(ROOT, 'painel', 'conteudo-es', sku);
        try {
          if (fs.existsSync(dir)) {
            manifest[sku] = fs.readdirSync(dir).filter((f) => f.endsWith('.jpg')).sort();
          } else {
            manifest[sku] = [];
          }
        } catch {
          manifest[sku] = [];
        }
      }
      return json(res, 200, { ok: true, manifest });
    }
    if (p.startsWith('/painel/api/')) return json(res, 404, { error: 'not-found' });
    if (req.method !== 'GET' && req.method !== 'HEAD') return json(res, 405, { error: 'method' });
    // Language selection for panel: query lang > cookie mdt_lang > buyer's lang > Accept-Language > /es/painel -> es > pt
    if (p === '/pt/painel' || p === '/pt/painel/index.html' || p === '/es/painel' || p === '/es/painel/index.html') {
      const urlLang = url.searchParams.get('lang');
      const okLang = (v) => (v === 'es' || v === 'pt' ? v : null);
      let lang = okLang(urlLang);
      const m_lang = /(?:^|;\s*)mdt_lang=([^;]+)/.exec(req.headers.cookie || '');
      if (!lang && m_lang) lang = okLang(m_lang[1]);
      const email = cookieEmail(req);
      if (!lang && email && db.buyers[email]) lang = db.buyers[email].lang;
      if (!lang) {
        const alang = (req.headers['accept-language'] || '').split(',')[0];
        if (alang.startsWith('es')) lang = 'es';
      }
      if (!lang) lang = (p.startsWith('/es') ? 'es' : 'pt');
      if (okLang(urlLang)) {
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'set-cookie': `mdt_lang=${lang}; Path=/; Max-Age=31536000` });
      } else {
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
      }
      const file = lang === 'es' ? 'painel/index-es.html' : 'painel/index-pt.html';
      return fs.createReadStream(path.join(ROOT, file)).pipe(res);
    }
    serveStatic(req, res, p);
  } catch (e) {
    console.error('erro', e.message);
    json(res, 500, { error: 'internal' });
  }
}).listen(PORT, () => console.log('mapa-do-tarot up :' + PORT));
