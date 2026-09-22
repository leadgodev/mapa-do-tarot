# Gate de identidade

Bloqueia commit se marca/idioma do concorrente vazar pra pagina, painel ou imagens.
Motivo: banner subiu com mockup do concorrente dentro (21/09/2026).

## Rodar manual

```bash
bash scripts/gate-identidade.sh
```

Falha (exit != 0) e imprime arquivo + trecho quando acha algo. Sucesso imprime
`GATE OK — nenhuma identidade de concorrente detectada`.

## Camadas

- **Layer 1 (texto):** `grep -riE` em `index.html`, `painel/**/*.html`,
  `*.css`, `*.js` do repo, contra lista de termos do concorrente (mapadeltaro,
  "mapa del tarot", conceptos, sumario, arcanos mayores, codigo de colores,
  el viaje del loco, preguntas poderosas, hoja de trucos) + qualquer handle
  `instagram.com/...` que nao seja `auramystica.pt`.
- **Layer 2 (OCR):** se `tesseract` estiver instalado, roda OCR (por+spa) em
  cada imagem raster de `assets/`, `produto/MOCKUPS-NOSSOS/` e pastas de
  banner/checkout, procurando os mesmos termos em espanhol dentro da arte.
  Sem `tesseract`: WARN e pula, nao falha o gate.

## Hook de commit

O hook nao e versionado (`.git/hooks/` fica fora do git), entao:

```bash
bash scripts/install-hooks.sh
```

Cria `.git/hooks/pre-commit` executavel que chama `scripts/gate-identidade.sh`.
Rodar de novo apos clone/checkout novo — o hook some no clone.
