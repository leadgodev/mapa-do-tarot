#!/bin/bash
# Traduz UMA página-imagem PT -> ES no ChatGPT (perfil já logado) e salva em painel/conteudo-es/<sku>/.
# Uso: scripts/traduzir-pagina-es.sh <sku> <arquivo.jpg> [sessao]
#   ex.: scripts/traduzir-pagina-es.sh principal pagina-02-como-usar.jpg gpt-noelia.empt
# Só grava o arquivo final se o download for uma imagem válida (nunca sobrescreve com lixo).
set -u
SKU="$1"; NOME="$2"; S="${3:-gpt-noelia.empt}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/painel/conteudo/$SKU/$NOME"
OUT="$ROOT/painel/conteudo-es/$SKU/$NOME"
TMP="$(mktemp -d)"
[ -f "$SRC" ] || { echo "FAIL origem inexistente: $SRC"; exit 1; }
mkdir -p "$(dirname "$OUT")"
ab(){ agent-browser --session "$S" "$@"; }
js(){ ab eval --stdin; }

PROMPT='Recrea esta misma página exactamente igual: mismo diseño, misma composición, mismos colores, misma ilustración de la carta de tarot, misma tipografía y posición de cada bloque, mismo formato y proporción. Cambia SOLAMENTE el texto: tradúcelo del portugués al español neutro latinoamericano, traducción fiel y natural, sin agregar ni quitar contenido. Nombres de las cartas en español estándar del tarot (El Loco, El Mago, La Sacerdotisa, La Emperatriz, El Emperador, El Hierofante, Los Enamorados, El Carro, La Fuerza, El Ermitaño, La Rueda de la Fortuna, La Justicia, El Colgado, La Muerte, La Templanza, El Diablo, La Torre, La Estrella, La Luna, El Sol, El Juicio, El Mundo). Ortografía impecable con tildes y ñ. No escribas nada en portugués.'

# 1. chat novo
ab navigate https://chatgpt.com/ >/dev/null 2>&1; sleep 5
# 2. anexo (a prévia não é mais <img backend-api>; confirmamos pelo botão "Remover <nome>")
ab upload "input[type=file]" "$SRC" >/dev/null 2>&1
ok=0
for i in $(seq 1 20); do
  n=$(echo "(()=>[...document.querySelectorAll('[aria-label]')].filter(e=>e.getAttribute('aria-label').includes('$NOME')).length)()" | js | tr -dc '0-9')
  [ "${n:-0}" -gt 0 ] && { ok=1; break; }; sleep 1
done
[ $ok = 1 ] || { echo "FAIL anexo nao apareceu"; exit 2; }
sleep 6  # deixa o upload terminar no servidor
# 3. srcs antes
echo "(()=>[...new Set([...document.querySelectorAll('img')].map(i=>i.src))].join('\n'))()" | js | tr -d '"' | sed 's/\\n/\n/g' > "$TMP/pre.txt"
# 4. prompt + enviar
P_JSON=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$PROMPT")
echo "(()=>{const e=document.querySelector('.ProseMirror');if(!e)return 'no-editor';e.focus();document.execCommand('insertText',false,$P_JSON);return 'ok'})()" | js | grep -q ok || { echo "FAIL editor"; exit 3; }
sleep 2
for k in $(seq 1 30); do
  sent=$(echo "(()=>{const b=document.querySelector('button[data-testid=\"send-button\"]')||document.querySelector('button[aria-label=\"Enviar prompt\"]')||document.querySelector('button[aria-label=\"Enviar\"]');if(!b||b.disabled)return 'nobtn';b.click();return 'sent'})()" | js)
  echo "$sent" | grep -q sent && break; sleep 2
done
echo "$sent" | grep -q sent || { echo "FAIL envio ($sent)"; exit 4; }
# 5. espera imagem nova (até 8 min)
NEW=""
for i in $(seq 1 96); do
  sleep 5
  echo "(()=>[...document.querySelectorAll('img')].filter(i=>/gerada|generated|generada/i.test(i.alt)&&i.complete&&i.naturalWidth>800).map(i=>i.src).join('\n'))()" | js | tr -d '"' | sed 's/\\n/\n/g' > "$TMP/now.txt"
  NEW=$(grep -vxF -f "$TMP/pre.txt" "$TMP/now.txt" | grep -v '^$' | tail -1)
  # só aceita quando a geração terminou (sem botão de parar)
  busy=$(echo "(()=>document.body.innerText.includes('Quase pronto')||document.body.innerText.includes('Criando imagem')||/\\b\\d{1,2}%/.test(document.querySelector('main')?.innerText||''))()" | js)
  [ -n "$NEW" ] && [ "$busy" = "false" ] && break
  NEW=""
done
[ -n "$NEW" ] || { echo "FAIL sem imagem nova em 8 min"; ab screenshot "$TMP/fail.png" >/dev/null 2>&1; echo "screenshot $TMP/fail.png"; exit 5; }
# 6. baixa pelo próprio navegador (cookies) como base64
U_JSON=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$NEW")
echo "(async()=>{const r=await fetch($U_JSON,{credentials:'include'});const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return btoa(s)})()" | js | tr -d '"' > "$TMP/b64.txt"
python3 - "$TMP/b64.txt" "$OUT" "$SRC" <<'EOF' || exit 6
import sys,base64,io
from PIL import Image
raw=base64.b64decode(open(sys.argv[1]).read().strip())
im=Image.open(io.BytesIO(raw)).convert('RGB')
ref=Image.open(sys.argv[3])
if im.width<800 or im.height<800: sys.exit(f'FAIL imagem pequena {im.size}')
if (im.width>im.height)!=(ref.width>ref.height): print(f'AVISO orientacao diferente {im.size} vs {ref.size}')
im.save(sys.argv[2],'JPEG',quality=90)
print('OK',sys.argv[2],im.size)
EOF
rm -rf "$TMP"
