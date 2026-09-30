/* ============================================================================
 * checkout-membros.js — Mapa do Tarot / Baralho Cigano
 * ----------------------------------------------------------------------------
 * Mapa de ofertas de MEMBRO (área logada) por SKU.
 *   sku     → chave usada no `localStorage.mdt_owned` (liberado via webhook)
 *   title   → texto curto exibido em modal e card
 *   normal  → preço público (R$) — base do cálculo de 30% off
 *   member  → preço de MEMBRO — override; se null, calcula `normal × 0,70` →
 *             arredonda ,90 abaixo. Piso R$ 9,90 (abaixo disso = sem desconto)
 *   url     → link de checkout Wiven "Oferta - Área de Membros"
 *   text    → texto curto do botão (ex.: "Quero o Combo por R$ 21,90")
 *   currency → 'BRL' (BR/Wiven) ou 'EUR' (PT/Mundpay)
 *
 * FONTE DAS URLs: outro pane (Wiven perfil 9254) está criando as ofertas
 *   "- Área de Membros" no gateway. Quando entregar, substituir `url: ''`
 *   abaixo pelo link real. ATÉ LÁ o painel cai no fallback WhatsApp
 *   (support@leadgo / 11 5177-0499) já implementado em painel/index.html.
 *
 * REGRA DA DONA (skill area-membros-netflix, 29/09/2026):
 *   - Upgrade de tier → 50% off (entre 50 e 60%), ,90 abaixo, piso R$ 9,90
 *   - Tudo o mais que ela não tem → 30% off, ,90 abaixo, piso R$ 9,90
 *   - Currency BRL no BR (Wiven); EUR no PT (Mundpay)
 *
 * Este arquivo é EXPORTADO por `window.CHECKOUT_MEMBROS`. O painel/index.html
 * pode ler daqui em vez do CHECKOUT_URL inline (hoje está inline; migração
 * opcional depois — não quebrar o que já está no ar).
 * ========================================================================= */
(function (root) {
  'use strict';

  // PREENCHER COM URL DO PANE WIVEN (perfil 9254)
  // Cada SKU tem uma oferta "X - Área de Membros" criada no gateway.
  // Quando o outro pane entregar, substituir `url: ''` por `url: 'https://...'`.
  var CHECKOUT_MEMBROS = {
    // --- Mapa do Tarot -----------------------------------------------------
    'principal': {
      title: '22 Arcanos Maiores',
      normal: 17.90,
      member: null,                  // 30% off: R$ 12,90 (calculado)
      url: 'https://checkout.wiven.com.br/checkout/cmubqz6yy010p01pqilaiahqe?offer=G8MYTZF',
      text: 'Quero os 22 Arcanos Maiores',
      currency: 'BRL'
    },
    'bonus-1': {
      title: 'Bônus 1 · Ler Qualquer Carta',
      normal: 17.90,
      member: null,                  // R$ 12,90
      url: '',                       // SEM oferta-membro Wiven (30/09/2026) → painel cai em fallback WhatsApp
      text: 'Quero o Bônus 1',
      currency: 'BRL'
    },
    'bonus-2': {
      title: 'Bônus 2 · Tiragens Práticas',
      normal: 17.90,
      member: null,
      url: '',                       // SEM oferta-membro Wiven (30/09/2026) → fallback WhatsApp
      text: 'Quero o Bônus 2',
      currency: 'BRL'
    },
    'bonus-3': {
      title: 'Bônus 3 · Cuidando do Baralho',
      normal: 17.90,
      member: null,
      url: '',                       // SEM oferta-membro Wiven (30/09/2026) → fallback WhatsApp
      text: 'Quero o Bônus 3',
      currency: 'BRL'
    },
    'bonus-4': {
      title: 'Bônus 4 · Minha Primeira Tiragem',
      normal: 17.90,
      member: null,
      url: '',                       // SEM oferta-membro Wiven (30/09/2026) → fallback WhatsApp
      text: 'Quero o Bônus 4',
      currency: 'BRL'
    },
    'guia-flash': {
      title: 'Guia Flash · Arcanos Maiores',
      normal: 12.00,
      member: null,                  // 30% off = R$ 8,40 → piso R$ 9,90 (SEM desconto; usa preço normal)
      url: 'https://checkout.wiven.com.br/checkout/cmubsge70026t01pujoks75g2?offer=RLLEDP8',  // preço já abaixo do piso; mantém link público
      text: 'Quero o Guia Flash',
      currency: 'BRL'
    },
    'perguntas-80': {
      title: '80 Perguntas Poderosas',
      normal: 15.00,
      member: null,                  // R$ 10,50 → floor R$ 9,90
      url: 'https://checkout.wiven.com.br/checkout/cmubsk2bg023101pqxrvx8q4s?offer=ZWWA35E',
      text: 'Quero 80 Perguntas Poderosas',
      currency: 'BRL'
    },
    'folha-consulta': {
      title: 'A Folha de Consulta do Tarot',
      normal: 22.00,
      member: null,                  // R$ 15,40 → floor R$ 14,90
      url: 'https://checkout.wiven.com.br/checkout/cmubsl72s023u01pq0h7vf7a9?offer=N6J40YD',
      text: 'Quero a Folha de Consulta',
      currency: 'BRL'
    },
    'combo-3-bonus': {
      title: 'Combo · Os 3 Bônus',
      normal: 30.00,
      member: null,                  // R$ 21,00 → floor R$ 20,90
      url: 'https://checkout.wiven.com.br/checkout/cmubwg9ah052m01puqslkbogu?offer=CFJDIOJ',
      text: 'Quero o Combo dos 3 Bônus',
      currency: 'BRL'
    },
    'completo': {
      title: 'Nível Completo · 56 Arcanos Menores',
      normal: 27.90,
      member: 13.90,                 // OVERRIDE: 50% off confirmado ao vivo (R$ 27,90 × 0,50 ≈ R$ 13,90)
      url: 'https://checkout.wiven.com.br/checkout/cmubqz6yy010p01pqilaiahqe?offer=G8MYTZF',
      text: 'Quero o Nível Completo',
      currency: 'BRL'
    },

    // --- Baralho Cigano (produto irmão, 30% off padrão) -------------------
    'cigano': {
      title: 'Mapa do Baralho Cigano',
      normal: 27.90,
      member: 19.90,                 // já calculado no painel (CIGANO_MEMBER)
      url: 'https://checkout.wiven.com.br/checkout/cmulz3f9d020801oojrzs3854?offer=JXE3KNA',  // já existe — oferta - Área de Membros criada 29/09
      text: 'Quero o Baralho Cigano',
      currency: 'BRL'
    }
  };

  // --- helpers ------------------------------------------------------------
  // 30% off arredondado pro ,90 abaixo; piso R$ 9,90. NÃO inventa: se
  // member já está setado (override), usa ele.
  function memberPrice(sku) {
    var o = CHECKOUT_MEMBROS[sku];
    if (!o) return null;
    if (o.member != null) return o.member;
    var cents = Math.round(o.normal * 100);
    var offCents = Math.round(cents * 0.7);
    var v = Math.floor((offCents - 90) / 100) * 100 + 90;
    return v < 990 ? o.normal : v / 100;
  }

  function fmt(n, currency) {
    var s = (currency === 'EUR' ? '€' : 'R$') + n.toFixed(2).replace('.', ',');
    return s;
  }

  // URL de checkout com UTM/_tkid já decorados pelo trackeador:decorate() no DOM.
  // Retorna null se a URL ainda não foi preenchida — chamador decide o fallback.
  function buyUrl(sku) {
    var o = CHECKOUT_MEMBROS[sku];
    return (o && o.url) ? o.url : null;
  }

  // CTA HTML pronto pra usar (link + data-tk-value + data-tk-currency + target _blank).
  // Se url é null, devolve o que o chamador passou como fallback (ex.: link WhatsApp).
  function ctaHtml(sku, fallbackHref) {
    var o = CHECKOUT_MEMBROS[sku];
    if (!o) return '';
    var url = o.url || (fallbackHref || '#');
    var price = memberPrice(sku);
    var priceStr = (price < o.normal)
      ? '<span style="text-decoration:line-through;opacity:.6;font-size:.85em;margin-right:6px;">' + fmt(o.normal, o.currency) + '</span>' + fmt(price, o.currency)
      : fmt(price, o.currency);
    var text = (o.text || 'Quero desbloquear') + ' — ' + priceStr;
    return '<a class="btn btn-primary" href="' + url + '"' +
           ' data-tk-value="' + price.toFixed(2) + '"' +
           ' data-tk-currency="' + o.currency + '"' +
           ' target="_blank" rel="noopener">' + text + '</a>';
  }

  // Expor.
  root.CHECKOUT_MEMBROS = CHECKOUT_MEMBROS;
  root.memberPrice = memberPrice;
  root.memberBuyUrl = buyUrl;
  root.memberCtaHtml = ctaHtml;
})(typeof window !== 'undefined' ? window : this);
