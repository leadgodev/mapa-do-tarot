#!/bin/bash
# Genera 2 imágenes para página ES: logo + testimonios. Chat nuevo por imagen.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap "rm -rf '$TMP'" EXIT

# Pega lane
S=$(~/.claude/bin/gpt-livre.sh es-img) || { echo "FAIL gpt-livre"; exit 1; }
echo "Lane: $S"

ab(){ agent-browser --session "$S" "$@"; }
js(){ ab eval --stdin; }

mkdir -p "$ROOT/entregas-es"

# ===== IMAGEN 1: LOGO =====
echo "=== IMAGEN 1: LOGO ==="
ab navigate https://chatgpt.com/ >/dev/null 2>&1; sleep 5

# Anexo
ab upload "input[type=file]" "$ROOT/painel/conteudo/principal/pagina-01-capa.jpg" >/dev/null 2>&1
ok=0
for i in $(seq 1 20); do
  n=$(echo "(()=>[...document.querySelectorAll('[aria-label]')].filter(e=>e.getAttribute('aria-label').includes('pagina-01-capa')).length)()" | js | tr -dc '0-9')
  [ "${n:-0}" -gt 0 ] && { ok=1; break; }; sleep 1
done
[ $ok = 1 ] || { echo "FAIL anexo logo"; exit 2; }
sleep 6

# Srcs antes
echo "(()=>[...new Set([...document.querySelectorAll('img')].map(i=>i.src))].join('\n'))()" | js | tr -d '"' | sed 's/\\n/\n/g' > "$TMP/pre1.txt"

# Prompt + enviar
PROMPT1='Crea un logotipo cuadrado (1:1) para la marca "Mapa Visual del Tarot", en el mismo estilo de esta portada: grabado vintage, morado profundo y dorado, luna creciente y estrella, pequeño detalle de carta de tarot. Fondo morado oscuro liso que llene todo el cuadrado, bordes redondeados no. Texto "Mapa Visual del Tarot" en tipografía elegante dorada, legible en tamaño pequeño. Sin otros textos, sin marcas de agua.'
P1_JSON=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$PROMPT1")
echo "(()=>{const e=document.querySelector('.ProseMirror');if(!e)return 'no-editor';e.focus();document.execCommand('insertText',false,$P1_JSON);return 'ok'})()" | js | grep -q ok || { echo "FAIL editor logo"; exit 3; }
sleep 2

for k in $(seq 1 30); do
  sent=$(echo "(()=>{const b=document.querySelector('button[data-testid=\"send-button\"]')||document.querySelector('button[aria-label=\"Enviar prompt\"]')||document.querySelector('button[aria-label=\"Enviar\"]');if(!b||b.disabled)return 'nobtn';b.click();return 'sent'})()" | js)
  echo "$sent" | grep -q sent && break; sleep 2
done
echo "$sent" | grep -q sent || { echo "FAIL envio logo ($sent)"; exit 4; }

# Espera imagen
NEW1=""
for i in $(seq 1 96); do
  sleep 5
  echo "(()=>[...document.querySelectorAll('img')].filter(i=>/gerada|generated|generada/i.test(i.alt)&&i.complete&&i.naturalWidth>800).map(i=>i.src).join('\n'))()" | js | tr -d '"' | sed 's/\\n/\n/g' > "$TMP/now1.txt"
  NEW1=$(grep -vxF -f "$TMP/pre1.txt" "$TMP/now1.txt" | grep -v '^$' | tail -1)
  busy=$(echo "(()=>document.body.innerText.includes('Quase pronto')||document.body.innerText.includes('Criando imagem')||/\\b\\d{1,2}%/.test(document.querySelector('main')?.innerText||''))()" | js)
  [ -n "$NEW1" ] && [ "$busy" = "false" ] && break
  NEW1=""
done
[ -n "$NEW1" ] || { echo "FAIL sin imagen logo en 8 min"; ab screenshot "$TMP/fail1.png" >/dev/null 2>&1; exit 5; }
echo "Logo src: $NEW1"

# Descarga logo
U1_JSON=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$NEW1")
echo "(async()=>{const r=await fetch($U1_JSON,{credentials:'include'});const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return btoa(s)})()" | js | tr -d '"' > "$TMP/b64_1.txt"
python3 - "$TMP/b64_1.txt" "$ROOT/entregas-es/logo-mapa-visual-del-tarot.png" "$ROOT/painel/conteudo/principal/pagina-01-capa.jpg" <<'PYEOF' || { echo "FAIL validacion logo"; exit 6; }
import sys,base64,io
from PIL import Image
raw=base64.b64decode(open(sys.argv[1]).read().strip())
im=Image.open(io.BytesIO(raw)).convert('RGB')
if im.width<200 or im.height<200: sys.exit(f'FAIL imagen pequena {im.size}')
im.save(sys.argv[2],'PNG',quality=95)
print('OK logo', sys.argv[2], im.size)
PYEOF

# ===== IMAGEN 2: TESTIMONIOS =====
echo ""
echo "=== IMAGEN 2: TESTIMONIOS ==="
ab navigate https://chatgpt.com/ >/dev/null 2>&1; sleep 5

# Anexo
ab upload "input[type=file]" "$ROOT/assets/testimonios.png" >/dev/null 2>&1
ok=0
for i in $(seq 1 20); do
  n=$(echo "(()=>[...document.querySelectorAll('[aria-label]')].filter(e=>e.getAttribute('aria-label').includes('testimonios')).length)()" | js | tr -dc '0-9')
  [ "${n:-0}" -gt 0 ] && { ok=1; break; }; sleep 1
done
[ $ok = 1 ] || { echo "FAIL anexo testimonios"; exit 7; }
sleep 6

# Srcs antes
echo "(()=>[...new Set([...document.querySelectorAll('img')].map(i=>i.src))].join('\n'))()" | js | tr -d '"' | sed 's/\\n/\n/g' > "$TMP/pre2.txt"

# Prompt + enviar
PROMPT2='Recrea esta misma imagen exactamente igual (mismo diseño de comentarios estilo Instagram, mismas fotos de perfil, mismos recuadros morados que ocultan los nombres, mismos colores, misma proporción cuadrada). Cambia SOLAMENTE el texto al español neutro latinoamericano, natural como lo escribiría una clienta real: "Acabo de comprarlo y me llegó todo al correo 👏 me encantó el material, lo voy a imprimir." / "Felicitaciones por el material, está súper organizado y es muy fácil de aprender." / "¡Me encantó, muy bueno y didáctico!" / "Me encantó el material, amo los resúmenes tan coloridos e ilustrados ❤️😍 Felicitaciones por el trabajo." Botones de la interfaz en español: "Responder", "Me encanta", "Enviar mensaje", "Ocultar", "1 Me gusta". Tiempos: "14 s", "4 h", "1 sem". Nada en portugués.'
P2_JSON=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$PROMPT2")
echo "(()=>{const e=document.querySelector('.ProseMirror');if(!e)return 'no-editor';e.focus();document.execCommand('insertText',false,$P2_JSON);return 'ok'})()" | js | grep -q ok || { echo "FAIL editor testimonios"; exit 8; }
sleep 2

for k in $(seq 1 30); do
  sent=$(echo "(()=>{const b=document.querySelector('button[data-testid=\"send-button\"]')||document.querySelector('button[aria-label=\"Enviar prompt\"]')||document.querySelector('button[aria-label=\"Enviar\"]');if(!b||b.disabled)return 'nobtn';b.click();return 'sent'})()" | js)
  echo "$sent" | grep -q sent && break; sleep 2
done
echo "$sent" | grep -q sent || { echo "FAIL envio testimonios ($sent)"; exit 9; }

# Espera imagen
NEW2=""
for i in $(seq 1 96); do
  sleep 5
  echo "(()=>[...document.querySelectorAll('img')].filter(i=>/gerada|generated|generada/i.test(i.alt)&&i.complete&&i.naturalWidth>800).map(i=>i.src).join('\n'))()" | js | tr -d '"' | sed 's/\\n/\n/g' > "$TMP/now2.txt"
  NEW2=$(grep -vxF -f "$TMP/pre2.txt" "$TMP/now2.txt" | grep -v '^$' | tail -1)
  busy=$(echo "(()=>document.body.innerText.includes('Quase pronto')||document.body.innerText.includes('Criando imagem')||/\\b\\d{1,2}%/.test(document.querySelector('main')?.innerText||''))()" | js)
  [ -n "$NEW2" ] && [ "$busy" = "false" ] && break
  NEW2=""
done
[ -n "$NEW2" ] || { echo "FAIL sin imagen testimonios en 8 min"; ab screenshot "$TMP/fail2.png" >/dev/null 2>&1; exit 10; }
echo "Testimonios src: $NEW2"

# Descarga testimonios
U2_JSON=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$NEW2")
echo "(async()=>{const r=await fetch($U2_JSON,{credentials:'include'});const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return btoa(s)})()" | js | tr -d '"' > "$TMP/b64_2.txt"
python3 - "$TMP/b64_2.txt" "$ROOT/entregas-es/testimonios-es.png" "$ROOT/assets/testimonios.png" <<'PYEOF' || { echo "FAIL validacion testimonios"; exit 11; }
import sys,base64,io
from PIL import Image
raw=base64.b64decode(open(sys.argv[1]).read().strip())
im=Image.open(io.BytesIO(raw)).convert('RGB')
if im.width<800 or im.height<800: sys.exit(f'FAIL imagen pequena {im.size}')
im.save(sys.argv[2],'PNG',quality=95)
print('OK testimonios', sys.argv[2], im.size)
PYEOF

echo ""
echo "✓ OK ambas imágenes generadas"
echo "  1: entregas-es/logo-mapa-visual-del-tarot.png"
echo "  2: entregas-es/testimonios-es.png"
