// Servidor mínimo: estático (página + painel) + API de acesso pós-compra (webhook Wiven).
// Sem dependências. Persistência: JSON em DATA_DIR (volume persistente).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { sendAccessEmail } from './mail.mjs';
import { modulePdf } from './modulo-pdf.mjs';

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
  // Order bumps do Baralho Cigano: liberam só o próprio módulo (não o pacote).
  // O produto principal Cigano (cmulz3f9…) NÃO entra aqui: o plano sai do offerCode (CIGANO_OFFERS).
  cmurhf87201cu01q2wh0whdz0: ['cigano-flash'], // Guia Flash 36 Cartas
  cmurhgvnj01ff01q2jkkz4xx7: ['cigano-perguntas'], // Perguntas que Destravam a Leitura
};
// Baralho Cigano (produto único cmulz3f9…, 2 planos). O plano vem do offerCode da compra,
// conferido na Wiven em 05/10/2026 (produto > Ofertas): Plano Básico R$17,90, Popup Básico R$16,90,
// Plano Completo/Upsell R$27,90, Popup Completo R$22,90 e "Área de Membros" R$18,90 (preço de membro).
const CIGANO_PRODUCT = 'cmulz3f9a020701oo4fstsegf';
const CIGANO_OFFERS = {
  E6JPHKE: ['cigano-basico'], K9XTAHE: ['cigano-basico'],
  AQNS7ED: ['cigano-completo'], UTK2YWV: ['cigano-completo'], JXE3KNA: ['cigano-completo'],
};
// Módulo do Cigano (nome da pasta em painel/conteudo) -> SKUs que liberam. Mapa do Básico é só
// as 36 cartas (página: "Plano Básico" tem ✦ Mapa e ✗ o resto). Completo libera tudo + app.
const CIGANO_ACCESS = {
  'cigano-36cartas': ['cigano-basico', 'cigano-completo'],
  'cigano-antes': ['cigano-completo'], 'cigano-dicionario': ['cigano-completo'],
  'cigano-bonus-1': ['cigano-completo'], 'cigano-bonus-2': ['cigano-completo'],
  'cigano-bonus-3': ['cigano-completo', 'cigano-flash'], 'cigano-bonus-4': ['cigano-completo', 'cigano-perguntas'],
  'cigano-bonus-5': ['cigano-completo'], 'cigano-app': ['cigano-completo'],
};
// SKU antigo 'cigano' (um pacote só, antes da separação em planos) = Completo. Expande na leitura.
const CIGANO_EXPAND = { cigano: ['cigano-basico', 'cigano-completo'], 'cigano-completo': ['cigano-basico'] };
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
const DEMO_SKUS = ['principal', 'bonus-1', 'bonus-2', 'bonus-3', 'bonus-4', 'completo', 'guia-flash', 'perguntas-80', 'folha-consulta', 'combo-3-bonus', 'cigano-completo'];
for (const e of ['teste-mundpay@leadgo.dev', 'teste-4423c38c@leadgo.dev']) db.buyers[e] = { skus: DEMO_SKUS.slice(), name: 'Teste' };
// Conta de teste só do plano Básico do Cigano (prova de cadeado: Mapa liberado, resto bloqueado).
db.buyers['teste-cigano-basico@leadgo.dev'] = { skus: ['cigano-basico'], name: 'Teste Básico' };
// Acesso efetivo: SKU do plano expande (Completo inclui Básico; 'cigano' antigo = Completo).
const owned = (email) => {
  if (!db.buyers[email]) return null;
  const s = new Set(db.buyers[email].skus);
  for (const k of [...s]) (CIGANO_EXPAND[k] || []).forEach((x) => s.add(x));
  return [...s];
};
// Pasta de conteúdo liberada? Cigano por módulo (CIGANO_ACCESS); Tarot = SKU com o mesmo nome da pasta.
const canOpenFolder = (o, folder) => {
  if (!o) return false;
  if (CIGANO_ACCESS[folder]) return CIGANO_ACCESS[folder].some((s) => o.includes(s));
  return o.includes(folder);
};

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
  const offerCode = String(payload.offerCode || '');
  for (const item of (payload.orderItems || tx.orderItems || [])) {
    const pid = item && item.product && item.product.id;
    (PRODUCT_SKUS[pid] || []).forEach((s) => skus.add(s));
    if (pid === 'cmubqz6yu010o01pqgcgfw6j0' && COMPLETO_OFFERS.has(offerCode)) skus.add('completo');
    // Baralho Cigano: produto único, o plano sai da oferta. Oferta desconhecida = nada liberado (log "ignored").
    if (pid === CIGANO_PRODUCT) (CIGANO_OFFERS[offerCode] || []).forEach((s) => skus.add(s));
  }
  if (!skus.size) return { code: 200, body: { ok: true, ignored: 'no-known-product', offerCode } };
  const b = db.buyers[email] || { skus: [], name: (payload.client || {}).name || '' };
  const novos = [...skus].filter((s) => !b.skus.includes(s));
  b.skus = [...new Set([...b.skus, ...skus])];
  db.buyers[email] = b;
  db.tx[tx.id] = true;
  save();
  if (novos.length) sendAccessEmail(email, b.name, [...skus], 'br').then((id) => console.log('access-email sent', id), (e) => console.error('access-email failed', e.message));
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
const FX_CURRENCIES = ['MXN', 'COP', 'ARS', 'CLP', 'PEN', 'BOB', 'PYG', 'UYU', 'GTQ', 'HNL', 'NIO', 'CRC', 'DOP', 'VES', 'EUR', 'BRL', 'CAD'];
let fxCache = { at: 0, rates: null };
async function getFxRates() {
  if (fxCache.rates && Date.now() - fxCache.at < 12 * 3600 * 1000) return fxCache.rates;
  try {
    const r = await fetch('https://open.er-api.com/v6/latest/USD', { signal: AbortSignal.timeout(5000) });
    const d = await r.json();
    if (d.result !== 'success' || !d.rates) throw new Error('bad fx response');
    const rates = {};
    for (const c of FX_CURRENCIES) if (d.rates[c]) rates[c] = d.rates[c];
    fxCache = { at: Date.now(), rates };
  } catch (e) {
    console.error('fx fetch failed', e.message);
  }
  return fxCache.rates;
}
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
  if ((rel.startsWith('/es/assets/') || rel.startsWith('/pt/assets/')) && !fs.existsSync(path.join(ROOT, rel))) rel = rel.slice(3);
  const abs = path.join(ROOT, rel);
  const top = rel.split('/')[1];
  if (top === 'es' && !rel.startsWith('/es/assets/') && !rel.endsWith('.html')) return json(res, 404, { error: 'not-found' });
  if (!abs.startsWith(ROOT + path.sep) || !(rel === '/index.html' || rel === '/es/index.html' || rel === '/pt/index.html' || rel === '/termos.html' || rel === '/privacidade.html' || rel === '/es/termos.html' || rel === '/es/privacidade.html' || top === 'assets' || top === 'painel' || top === 'es' || rel.startsWith('/pt/assets/') || top === 'upsell-cigano' || top === 'js')) return json(res, 404, { error: 'not-found' });
  // conteúdo pago: exige sessão + ownership do SKU
  const m = /^\/painel\/conteudo\/([^/]+)\//.exec(rel);
  const mEs = /^\/painel\/conteudo-es\/([^/]+)\//.exec(rel);
  if (m) {
    const o = owned(cookieEmail(req) || '');
    if (!canOpenFolder(o, m[1])) return json(res, 403, { error: 'forbidden' });
  }
  if (mEs) {
    const o = owned(cookieEmail(req) || '');
    if (!canOpenFolder(o, mEs[1])) return json(res, 403, { error: 'forbidden' });
  }
  // App de Treino (PT e ES): bônus exclusivo do Nível Completo (SKU 'completo').
  if (rel === '/painel/treino' || rel.startsWith('/painel/treino/') || rel === '/painel/treino-es' || rel.startsWith('/painel/treino-es/')) {
    const o = owned(cookieEmail(req) || '');
    if (!o || !o.includes('completo')) {
      res.writeHead(302, { location: '/painel' });
      return res.end();
    }
  }
  // App de Treino do Baralho Cigano: só Completo do Cigano.
  if (rel === '/painel/treino-cigano' || rel.startsWith('/painel/treino-cigano/')) {
    if (!canOpenFolder(owned(cookieEmail(req) || ''), 'cigano-app')) {
      res.writeHead(302, { location: '/painel#cigano' });
      return res.end();
    }
  }
  // Painel: serve a versão .webp (gerada por scripts/otimiza-painel-webp.sh) quando existir e o browser aceitar.
  let file = abs;
  const reqExt = path.extname(abs).toLowerCase();
  const negotiable = top === 'painel' && (reqExt === '.jpg' || reqExt === '.jpeg' || reqExt === '.png');
  if (negotiable && /image\/webp/.test(req.headers.accept || '')) {
    const w = abs.slice(0, -reqExt.length) + '.webp';
    if (fs.existsSync(w)) file = w;
  }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) return json(res, 404, { error: 'not-found' });
    const ext = path.extname(file).toLowerCase();
    // Área de membros nunca serve cópia velha: tudo em /painel (e todo HTML) revalida
    // sempre por ETag (304 barato). Imutável só para asset do site fora do painel.
    const cacheControl = (m || mEs) ? 'private, no-cache' : (top === 'painel' || ext === '.html') ? 'no-cache' : 'public, max-age=31536000, immutable';
    const etag = `W/"${st.size.toString(36)}-${Math.floor(st.mtimeMs).toString(36)}"`;
    const headers = { 'content-type': MIME[ext] || 'application/octet-stream', 'cache-control': cacheControl, etag };
    if (negotiable) headers.vary = 'Accept';
    if (req.headers['if-none-match'] === etag) { res.writeHead(304, headers); return res.end(); }
    const compressible = /^(text\/|application\/(json|javascript)|image\/svg)/.test(headers['content-type']) && st.size > 1024;
    if (compressible && /\bgzip\b/.test(req.headers['accept-encoding'] || '')) {
      headers['content-encoding'] = 'gzip';
      headers.vary = 'Accept-Encoding';
      res.writeHead(200, headers);
      return fs.createReadStream(file).pipe(zlib.createGzip()).pipe(res);
    }
    headers['content-length'] = st.size;
    res.writeHead(200, headers);
    fs.createReadStream(file).pipe(res);
  });
}

// Domínios próprios por idioma (26b1a... Coolify): host decide o idioma, não mais
// só o prefixo /pt /es. BR continua em mapadotarot.leadgo.dev sem prefixo.
const HOST_PT = 'pt.mapadotarot.leadgo.dev';
const HOST_ES = 'mapadeltarot.leadgo.dev';
const HOST_BR = 'mapadotarot.leadgo.dev';
// Domínio decide o idioma nos hosts novos (PT e ES); o BR legado segue o lang do comprador.
const hostLang = (req) => { const h = String(req.headers.host || '').split(':')[0].toLowerCase(); return h === HOST_PT ? 'pt' : h === HOST_ES ? 'es' : null; };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  let p = url.pathname;
  const host = String(req.headers.host || '').split(':')[0].toLowerCase();
  try {
    // mapadotarot.leadgo.dev/pt(/*) e /es(/*) -> domínio próprio, 301, path+query intactos.
    // URL de agradecimento e de entrega cadastradas na Mundpay (produto único PT+ES) = /pt/painel
    // no domínio BR. Não mexemos na Mundpay (edição volta o produto pra análise): aqui ela cai na
    // página de obrigado em modo automático, que manda pro painel PT ou ES pelo fuso/idioma.
    if (host === HOST_BR && (p === '/pt/painel' || p === '/pt/painel/')) {
      const q = new URLSearchParams(url.search); q.set('go', '1');
      res.writeHead(302, { location: `https://${HOST_PT}/obrigado?${q}`, 'cache-control': 'no-store' });
      return res.end();
    }
    if (host === HOST_BR && (p === '/pt' || p.startsWith('/pt/') || p === '/es' || p.startsWith('/es/'))) {
      const lang = p.startsWith('/pt') ? 'pt' : 'es';
      const newHost = lang === 'pt' ? HOST_PT : HOST_ES;
      const rest = p.slice(3) || '/';
      res.writeHead(301, { location: `https://${newHost}${rest}${url.search}` });
      return res.end();
    }
    // Página de obrigado bilíngue (Mundpay PT/ES usa o mesmo produto, logo o mesmo redirect):
    // mesma página em qualquer domínio, botão para o painel PT e ES.
    if (p === '/obrigado' || p === '/gracias' || p === '/obrigado/' || p === '/gracias/') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache' });
      return fs.createReadStream(path.join(ROOT, 'obrigado.html')).pipe(res);
    }
    // Domínio PT/ES: reescreve pathname para o prefixo interno já existente,
    // menos webhook (global) e /painel/api/* (compartilhado, sem prefixo).
    if ((host === HOST_PT || host === HOST_ES) && !p.startsWith('/painel/api/')) {
      const lang = host === HOST_PT ? 'pt' : 'es';
      // /painel/* fora da raiz (treino, conteudo, conteudo-es, assets do painel) é
      // pasta física compartilhada — não leva prefixo. Só a raiz do painel escolhe idioma.
      if (p === '/') p = `/${lang}`;
      else if (p === '/painel' || p === '/painel/' || p === '/painel/index.html') p = `/${lang}/painel`;
      else if (p === '/termos' || p === '/privacidade') p = `/${lang}${p}`;
      else if (p.startsWith('/painel/')) { /* mantém: treino, conteudo, conteudo-es, api já fora */ }
      // Imagem própria do mercado (es/assets, pt/assets) vence a do BR; sem ela, cai em /assets.
      else if (p.startsWith('/assets/') && fs.existsSync(path.join(ROOT, lang, p))) p = `/${lang}${p}`;
      else if (!p.startsWith(`/${lang}/`) && !p.startsWith('/assets/') && !p.startsWith('/js/')) p = `/${lang}${p}`;
    }
    // Câmbio USD→moeda local da página ES (preço aproximado na moeda do visitante).
    // Cache 12h; se a fonte cair, devolve o último valor bom (ou 503 e a página fica só em USD).
    if (p === '/painel/api/fx') {
      const rates = await getFxRates();
      if (!rates) return json(res, 503, { error: 'fx-unavailable' });
      return json(res, 200, { base: 'USD', rates }, { 'cache-control': 'public, max-age=3600' });
    }
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
      const lang = hostLang(req) || db.buyers[email]?.lang || 'pt';
      return json(res, 200, { ok: true, owned: o, lang }, { 'set-cookie': `mdt_s=${makeCookie(email)}; Path=/painel; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_TTL}` });
    }
    if (p === '/painel/api/me') {
      const email = cookieEmail(req);
      const o = email && owned(email);
      if (!o) return json(res, 401, { error: 'no-session' });
      const lang = hostLang(req) || db.buyers[email]?.lang || 'pt';
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
      if (!canOpenFolder(o, sku)) return json(res, 403, { error: 'forbidden' });
      const lang = url.searchParams.get('lang') === 'es' ? 'es' : null;
      // PDF montado na hora com as mesmas páginas do leitor; nome do arquivo = nome do módulo.
      const built = modulePdf(ROOT, sku, lang);
      if (built) {
        const fname = built.title.replace(/[\\/:*?"<>|]+/g, '-') + '.pdf';
        const hdr = { etag: built.etag, 'cache-control': 'private, no-cache', 'content-disposition': `attachment; filename="${fname.replace(/[^\x20-\x7e]/g, '_')}"; filename*=UTF-8''${encodeURIComponent(fname)}` };
        if (req.headers['if-none-match'] === built.etag) return res.writeHead(304, hdr), res.end();
        return res.writeHead(200, { ...hdr, 'content-type': 'application/pdf', 'content-length': built.buf.length }), res.end(built.buf);
      }
      const pdfPath = path.join(ROOT, 'painel', lang === 'es' ? 'conteudo-es' : 'conteudo', sku, sku + '.pdf');
      if (fs.existsSync(pdfPath)) {
        const st = fs.statSync(pdfPath);
        const etag = `"${st.size.toString(16)}-${Math.floor(st.mtimeMs).toString(16)}"`;
        if (req.headers['if-none-match'] === etag) return res.writeHead(304, { etag, 'cache-control': 'private, no-cache' }), res.end();
        return res.writeHead(200, { 'content-type': 'application/pdf', 'content-length': st.size, etag, 'cache-control': 'private, no-cache' }), fs.createReadStream(pdfPath).pipe(res);
      }
      if (sku.startsWith('cigano-') && url.searchParams.get('lang') !== 'es') {
        generatePDF(sku, pdfPath, (err) => {
          if (err) return json(res, 500, { error: 'pdf-generation-failed' });
          const st = fs.statSync(pdfPath);
          res.writeHead(200, { 'content-type': 'application/pdf', 'content-length': st.size, 'cache-control': 'private, no-cache' });
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
      let lang = hostLang(req) || okLang(urlLang);
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
