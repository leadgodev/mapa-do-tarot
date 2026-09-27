// E-mail de acesso via Resend (fetch, sem dependência).
const SKU_NAMES = {
  principal: 'Mapa do Tarot', 'bonus-1': 'Bônus 1', 'bonus-2': 'Bônus 2', 'bonus-3': 'Bônus 3', 'bonus-4': 'Bônus 4',
  completo: 'Nível Completo', 'guia-flash': 'Guia Flash', 'perguntas-80': '80 Perguntas', 'folha-consulta': 'Folha de Consulta', 'combo-3-bonus': 'Combo dos 3 bônus',
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const LINK = 'https://mapadotarot.leadgo.dev/painel';

export function accessEmail(email, name, skus) {
  const items = skus.map((s) => SKU_NAMES[s] || s);
  const first = String(name || '').trim().split(/\s+/)[0];
  const html = `<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#222;line-height:1.5">
<h2>Seu acesso ao Mapa do Tarot</h2>
<p>Olá${first ? ', ' + esc(first) : ''}! Seu pagamento foi confirmado e o acesso já está liberado.</p>
<p><a href="${LINK}" style="display:inline-block;background:#6b21a8;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none">Acessar meu Mapa do Tarot</a></p>
<p>Ou copie este link: ${LINK}</p>
<p><b>Entre com este e-mail:</b> ${esc(email)}</p>
<p><b>Você comprou:</b></p><ul>${items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>
<p>Precisa de ajuda? Escreva para support@leadgo.dev ou chame no WhatsApp (11) 5177-0499.</p></div>`;
  const text = `Seu acesso ao Mapa do Tarot\n\nSeu pagamento foi confirmado e o acesso já está liberado.\nAcesse: ${LINK}\nEntre com este e-mail: ${email}\n\nVocê comprou: ${items.join(', ')}\n\nSuporte: support@leadgo.dev / WhatsApp (11) 5177-0499`;
  return { subject: 'Seu acesso ao Mapa do Tarot', html, text };
}

export async function sendAccessEmail(email, name, skus) {
  const key = process.env.RESEND_API_KEY;
  if (!key) throw new Error('RESEND_API_KEY ausente');
  const m = accessEmail(email, name, skus);
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' },
    body: JSON.stringify({ from: process.env.MAIL_FROM || 'Mapa do Tarot <no-reply@leadgo.dev>', to: [email], reply_to: 'support@leadgo.dev', ...m }),
    signal: AbortSignal.timeout(15000),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`resend ${r.status} ${j.message || ''}`);
  return j.id;
}
