# Checkout Mundpay — Mapa del Tarot ES (USD)

**Decisão da dona (05/10/2026):** ES NÃO tem produto Mundpay próprio. ES vende dentro do produto PT já aprovado:
**Mapa do Tarot Essencial - PT** (`01a0d98a-e8f5-72a6-b1d4-43b36f5ee190`), com ofertas `– ES` em USD.
Produto `Mapa del Tarot - ES` (`01a10edc-f0d8-7011-9877-cff035cc2282`) fica **Em análise**, sem uso: ofertas
desativadas, bumps desligados, webhooks desativados. Nada foi apagado.

Regra de pagamento (todas as ofertas ES): só recebimento na hora (cartão, Pix, Apple/Google Pay, carteiras e
transferência instantânea). Sem boleto, OXXO, Efecty, Rapipago, dinheiro em loja, voucher, PagoEfectivo.

## Ofertas ES (produto 01a0d98a)

| Oferta | Valor | Checkout (link na página ES) | Status | Métodos |
|---|---|---|---|---|
| Mapa do Tarot Basico - ES | US$ 6,50 | `01a0f31a-3680-70ba-97df-674bf221c815` | Ativo | Não alterados nesta tarefa |
| Mapa del Tarot Completo - ES | US$ 12,50 | `01a0f31b-96df-70a0-9e7c-1891d7fcd5ac` | Ativo | Não alterados nesta tarefa |
| Mapa del Tarot Oferta Especial - ES (downsell) | US$ 9,50 | `01a0f31c-06d3-73ae-866f-74e142a2fc53` | Ativo | Não alterados nesta tarefa |
| Mapa del Tarot Completo Salida - ES (popup de saída) | US$ 7,50 | `01a11632-63df-730a-8058-f271468e61d0` | Ativo | Não alterados nesta tarefa |

Métodos alternativos instantâneos marcados (24 itens, por país):
- Argentina: Mercado Pago, MODO, Khipu.
- Brasil: PicPay.
- Chile: Khipu, Mach, Banco de Chile, Banco Estado, Banco Falabella, Banco Santander, BCI, Fintoc.
- Colômbia: PSE, Nequi PSE.
- Costa Rica: Banco Nacional.
- Equador: Banco Guayaquil, Banco Pichincha.
- México: SPEI, Scotiabank.
- Peru: Banco de Crédito, Interbank, Scotiabank, BBVA Continental, Khipu.
- Principais: Cartão de Crédito, Pix, Apple Pay, Google Pay.

Excluídos: Boleto (BR), Rapipago, Otros Bancos/Billeteras (AR), ServiPag (CL), Efecty (CO), Red Activa, Mi Comisariato,
Pichincha Mi Vecino (EC), OXXO e lojas (MX), Caja/Ripley/Western Union/Kasnet (PE).
Obs.: o painel mostra "26/64" no cabeçalho (4 principais + 22), mas o total por país é 24 itens. A contagem global do
painel conta Khipu/Scotiabank uma vez só. Não é erro de seleção (conferido por país ao reabrir a oferta).

Checkout público (teste, país padrão Brasil): cada link mostra o preço convertido para BRL no seletor local e o total
em R$. O preço em moeda do comprador (ES/MX/CO…) NÃO foi conferido: exige trocar o país no checkout.

## Order bumps (produto 01a0d98a, aba Order Bumps)

Ligados como order bump (4 ofertas ES, origem no produto `Extras Mapa do Tarot - PT`, `01a0eaf0`):

| Título exibido | Oferta de origem | Preço |
|---|---|---|
| 80 Preguntas Poderosas | Extras Mapa del Tarot - ES - 80 Preguntas Poderosas - ES | US$ 5,90 |
| Hoja de Consulta del Tarot | Hoja de Consulta del Tarot - ES | US$ 6,90 |
| Guía Flash · Arcanos Mayores | Guía Flash · Arcanos Mayores - ES | US$ 5,00 |
| Llévate los 3 con descuento | Llévate los 3 con descuento - ES (combo) | US$ 11,90 |

- Bump não tem escopo por oferta: os 4 ES também aparecem no checkout PT (dona aceitou). Os 3 bumps PT continuam ligados.
- Bump ES: 4 principais + 0 alternativos (só instantâneos).
- Imagem do bump: sem campo no formulário Mundpay.
- Bump aparece no checkout só depois de identificação (email)? Não verificado: não preenchi email pra não gerar lead.
  Pendente: fazer uma compra de teste ou conferir pelo fluxo real antes de tráfego.

## Webhooks Mundpay (Integrações → Webhook Genérico)

| Nome | Produto | URL (destino) | Status |
|---|---|---|---|
| Painel PT - liberacao de acesso | Mapa do Tarot Essencial - PT | `mapadotarot.leadgo.dev/painel/api/webhooks/mundpay` | Ativo |
| Trackeador - Mapa do Tarot PT | Mapa do Tarot Essencial - PT | conexão `6d593083-…` | Ativo |
| Painel ES - liberacao de acesso | Mapa del Tarot - ES | `mapadeltarot.leadgo.dev/painel/…` | **Inativo** |
| Trackeador - Mapa del Tarot ES | Mapa del Tarot - ES | conexão `dabe9e22-…` | **Inativo** |

Venda ES do produto compartilhado chega pelos webhooks do PT (produto 01a0d98a). Painel: o mapeamento de SKU é por nome
da oferta (`MUNDPAY_NAME_SKUS` em `server/index.mjs`): `– ES` cai nos mesmos regex do PT e USD força `lang=es`.

## Trackeador

- Conexão ES `dabe9e22-00de-4cf7-8a8c-a15f3e6ba56e` (`Mapa del Tarot - ES — Mundpay`): pixel LATAM `1107064091683532`,
  CAPI desligada, webhook Mundpay **inativo** (produto 01a10edc, sem vendas).
- Conexão PT `6d593083-…` (`Mapa do Tarot - PT — Mundpay`): pixel PT `1661093678974999` (novo desde 09/10, era `4048960295234961`), CAPI desligada (decisão de 29/09).
- **Roteamento por oferta (05/10/2026, deploy Trackeador `03203e7` em origin/master):** venda ES do produto 01a0d98a
  (oferta/produto com ` - ES` ou payload USD sem oferta) vai pra conexão ES `dabe9e22` (pixel LATAM). O resto segue na PT
  `6d593083`. Regra e par em `web/lib/mundpay-es-routing.ts` (repo trackeador-mvp). Testes unitários: 5/5.
  Prova ponta a ponta no webhook de produção: PENDENTE (o guard bloqueia curl em /api/webhooks; falta uma venda real ou
  teste autorizado). Smoke de produção ok (5/5).
- Painel ES: SKUs ES mapeados por nome no `server/index.mjs` (`MUNDPAY_NAME_SKUS`), webhook do painel = "Painel PT - liberacao
  de acesso". Prova com conta teste pendente.

## Gate no ar (05/10/2026, headed, `mapadeltarot.leadgo.dev/es/` com UTM)

- PageView ✓ e ViewContent ✓ (`facebook.com/tr`, id `1107064091683532`), ViewContent `value 14.9 USD`.
- InitiateCheckout ✓ em cada um dos 5 botões de checkout, uma vez por clique, moeda USD:
  Completo 14.9 · Completo 14.9 · Downsell 12.9 · Básico 7.9 · Saída 12.9.

## Histórico
- 2026-10-05: produto separado "Mapa del Tarot - ES" abandonado (ofertas e webhooks desativados). ES volta pro produto
  compartilhado 01a0d98a. Ofertas ES com métodos instantâneos. Bumps ES ligados no produto compartilhado.
  Página ES repontada (commit `13ad322`, já publicado; o commit `da4e0d9` que trocava pro produto separado também já estava no remoto,
  por isso não foi revertido: foi feito commit novo).
