// E-mail de acesso via Resend (fetch, sem dependência).
const SKU_NAMES = {
  principal: 'Mapa do Tarot', 'bonus-1': 'Bônus 1', 'bonus-2': 'Bônus 2', 'bonus-3': 'Bônus 3', 'bonus-4': 'Bônus 4',
  completo: 'Nível Completo', 'guia-flash': 'Guia Flash', 'perguntas-80': '80 Perguntas', 'folha-consulta': 'Folha de Consulta', 'combo-3-bonus': 'Combo dos 3 bônus',
};
const SKU_NAMES_ES = {
  principal: 'Mapa del Tarot', 'bonus-1': 'Bono 1', 'bonus-2': 'Bono 2', 'bonus-3': 'Bono 3', 'bonus-4': 'Bono 4',
  completo: 'Nivel Completo', 'guia-flash': 'Guía Flash', 'perguntas-80': '80 Preguntas', 'folha-consulta': 'Hoja de Consulta', 'combo-3-bonus': 'Combo de 3 bonos',
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const LINK = 'https://mapadotarot.leadgo.dev/painel';
const LINK_PT = 'https://pt.mapadotarot.leadgo.dev/painel';
const LINK_ES = 'https://mapadeltarot.leadgo.dev/painel';

export function accessEmail(email, name, skus, lang = 'br') {
  if (lang === 'es') {
    const items = skus.map((s) => SKU_NAMES_ES[s] || s);
    const first = String(name || '').trim().split(/\s+/)[0];
    const html = `<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#222;line-height:1.5">
<h2>Tu acceso al Mapa del Tarot</h2>
<p>¡Hola${first ? ', ' + esc(first) : ''}! Tu pago ha sido confirmado y el acceso ya está disponible.</p>
<p><a href="${LINK_ES}" style="display:inline-block;background:#6b21a8;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none">Acceder a mi Mapa del Tarot</a></p>
<p>O copia este enlace: ${LINK_ES}</p>
<p><b>Inicia sesión con este correo:</b> ${esc(email)}</p>
<p><b>Compraste:</b></p><ul>${items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>
<p>¿Necesitas ayuda? Escribe a support@leadgo.dev</p></div>`;
    const text = `Tu acceso al Mapa del Tarot\n\nTu pago ha sido confirmado y el acceso ya está disponible.\nAccede: ${LINK_ES}\nInicia sesión con: ${email}\n\nCompraste: ${items.join(', ')}\n\nSoporte: support@leadgo.dev`;
    return { subject: 'Tu acceso al Mapa del Tarot', html, text };
  }
  const link = lang === 'pt' ? LINK_PT : LINK;
  const items = skus.map((s) => SKU_NAMES[s] || s);
  const first = String(name || '').trim().split(/\s+/)[0];
  const html = `<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#222;line-height:1.5">
<h2>Seu acesso ao Mapa do Tarot</h2>
<p>Olá${first ? ', ' + esc(first) : ''}! Seu pagamento foi confirmado e o acesso já está liberado.</p>
<p><a href="${link}" style="display:inline-block;background:#6b21a8;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none">Acessar meu Mapa do Tarot</a></p>
<p>Ou copie este link: ${link}</p>
<p><b>Entre com este e-mail:</b> ${esc(email)}</p>
<p><b>Você comprou:</b></p><ul>${items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>
<p>Precisa de ajuda? Escreva para support@leadgo.dev ou chame no WhatsApp (11) 5177-0499.</p></div>`;
  const text = `Seu acesso ao Mapa do Tarot\n\nSeu pagamento foi confirmado e o acesso já está liberado.\nAcesse: ${link}\nEntre com este e-mail: ${email}\n\nVocê comprou: ${items.join(', ')}\n\nSuporte: support@leadgo.dev / WhatsApp (11) 5177-0499`;
  return { subject: 'Seu acesso ao Mapa do Tarot', html, text };
}

export async function sendAccessEmail(email, name, skus, lang = 'pt') {
  const key = process.env.RESEND_API_KEY;
  if (!key) throw new Error('RESEND_API_KEY ausente');
  const m = accessEmail(email, name, skus, lang);
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
