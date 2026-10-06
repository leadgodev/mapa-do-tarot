# Checkout Mundpay — Mapa del Tarot ES (USD)

Produto Mundpay próprio: **Mapa del Tarot - ES** (`01a10edc-f0d8-7011-9877-cff035cc2282`).
Status do produto: **Em análise** (ainda não ativado para venda). Entrega: Integração Externa, `https://mapadeltarot.leadgo.dev/painel/`, conta teste padrão `teste-4423c38c@leadgo.dev`.

Regra de pagamento da dona (todas as ofertas ES, principal e bumps): só recebimento na hora (cartão, Apple/Google Pay, Pix e transferência instantânea). Sem boleto, OXXO, dinheiro em loja, voucher, Efecty, PagoEfectivo.

## Ofertas do produto ES

| Oferta | Valor | Checkout (link atual da página) | Status | Métodos |
|---|---|---|---|---|
| Básico - ES | US$ 7,90 | `01a10ee5-49dd-7348-9a21-350927feb4f0` — https://pay.mycheckoutt.com/01a10ee5-49dd-7348-9a21-350927feb4f0?ref= | Ativo (no produto) | 4 principais + alternativos instantâneos (ver abaixo) |
| Mapa del Tarot Completo - ES | US$ 14,90 | `01a10ede-2288-7064-b9a1-55f5502822c5` — https://pay.mycheckoutt.com/01a10ede-2288-7064-b9a1-55f5502822c5?ref= | Ativo | só instantâneos (criada assim no pane anterior; não reverificada nesta rodada) |
| Mapa del Tarot Oferta Especial - ES (popup) | US$ 12,90 | `01a10ede-d49e-700c-a945-f7bf3d79f356` — https://pay.mycheckoutt.com/01a10ede-d49e-700c-a945-f7bf3d79f356?ref= | Ativo | só instantâneos (criada assim no pane anterior; não reverificada nesta rodada) |
| Mapa del Tarot Básico - ES (antiga) | US$ 7,90 | — | **Inativo** (desativada, não apagada) | padrão (64, com boleto/OXXO) |

Pendente: reverificar os métodos de Completo e Oferta Especial na tela de edição antes de liberar tráfego.

### Métodos instantâneos do Básico - ES (marcados)
- Principais: Cartão de Crédito, Pix, Apple Pay, Google Pay.
- Argentina: Mercado Pago, MODO, Khipu.
- Brasil: PicPay.
- Chile: Khipu, Mach, Banco de Chile, Banco Estado, Banco Falabella, Banco Santander, BCI, Fintoc (ServiPag fora: pagamento em rede de caixas).
- Colômbia: PSE, Nequi PSE (Efecty fora).
- Costa Rica: Banco Nacional.
- Equador: Banco Guayaquil, Banco Pichincha (Red Activa, Mi Comisariato, Pichincha Mi Vecino fora).
- México: SPEI, Scotiabank (OXXO, lojas e demais fora).
- Peru: Banco de Crédito, Interbank, Scotiabank, BBVA Continental, Khipu (Caja, Ripley, Western Union, Kasnet fora).
- Excluídos: Boleto Bancário (BR), Rapipago, Otros Bancos/Billeteras (AR), Efecty (CO), todas as lojas/redes de pagamento em espécie.

Decisão de critério: Mercado Pago, MODO, PicPay, Scotiabank e Khipu entram como instantâneos (carteira ou transferência). Se a dona quiser restringir mais, tirar esses.

## Order bumps do produto ES (Order Bumps)

A Mundpay só aceita oferta de OUTRO produto como bump. Por isso os bumps ES usam as ofertas ES que estão no produto compartilhado **Extras Mapa do Tarot - PT** (`01a0eaf0`). Ligados como order bump no produto ES (4):

| Bump (título exibido) | Oferta de origem | Preço |
|---|---|---|
| 80 Preguntas Poderosas | Extras Mapa del Tarot - ES - 80 Preguntas Poderosas - ES | US$ 5,90 |
| Hoja de Consulta del Tarot | Hoja de Consulta del Tarot - ES | US$ 6,90 |
| Guía Flash · Arcanos Mayores | Guía Flash · Arcanos Mayores - ES | US$ 5,00 |
| Llévate los 3 con descuento | Llévate los 3 con descuento - ES (combo) | US$ 11,90 |

Pendências dos bumps:
- As 4 ofertas continuam ATIVAS no produto Extras PT: são a fonte dos bumps. Desativar quebra o bump.
- Imagem do bump não tem campo no formulário Mundpay (não anexada).
- Risco: os bumps ES vivem no produto Extras PT, que também é ligado no webhook PT. Vendas de bump ES podem chegar ao Trackeador PT e ao painel PT. Solução limpa = produto "Extras Mapa del Tarot - ES" próprio (exige o código de 4 dígitos do suporte, bloqueado sem humano).

## Webhooks Mundpay (Integrações → Webhook Genérico)

- `Trackeador - Mapa del Tarot ES`: produto Mapa del Tarot - ES; eventos padrão (Pago, Reembolsado, Chargeback incluídos); URL = conexão `dabe9e22-00de-4cf7-8a8c-a15f3e6ba56e` no adstrackeador (token em `~/.trackeador/mundpay-es-webhook-secret.txt`).
- `Painel ES - liberacao de acesso`: produto Mapa del Tarot - ES; URL `https://mapadeltarot.leadgo.dev/painel/api/webhooks/mundpay?token=<MUNDPAY_WEBHOOK_TOKEN>` (mesmo token do painel).
- Sem prova de disparo real: nenhuma venda teste feita (produto em análise).

## Trackeador

- Conexão `Mapa del Tarot - ES — Mundpay` (`dabe9e22`): dashboard `MAPA DE TAROT - LATAM`, pixel LATAM `1107064091683532`, CAPI desligada (de propósito, até provar a cadeia).
- `default_country`: deixado VAZIO de propósito (LATAM multi-país). Doctor acusa aviso; decisão da dona.
- Prova ponta a ponta (`checkout simular`, `test flow`) não rodada: o CLI não tem modo de teste para essa conexão sem enviar eventos; `check` acusa só "CAPI desligada" e produto não cadastrado (esperado enquanto não há CAPI).

## Histórico
- 2026-10-05: oferta Básico - ES criada (US$ 7,90, instantâneos); antiga Básico desativada. Bumps ES criados e ligados (4). Webhook Trackeador e painel ES cadastrados. Link do checkout Básico trocado na página ES (commit local, não publicado).
