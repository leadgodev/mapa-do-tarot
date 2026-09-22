#!/usr/bin/env bash
# GATE de identidade: bloqueia commit se nossa página/painel referenciar
# imagem que aponta pra pasta de referência/concorrente (asset não nosso).
#
# REGRA REAL (dono, 21/09/2026): idioma NAO e o criterio. Espanhol num banner
# foi so SINTOMA de um caso — o problema de fundo e usar arte/mockup do
# concorrente direto na nossa peca, ou deixar asset dele na pagina sem
# substituir pelo nosso. Nao temos os mockups do concorrente salvos em
# arquivo (vivem na pagina ao vivo dele) — entao nao da pra comparar hash,
# so caminho.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

FAIL=0

echo "== GATE DE IDENTIDADE (critério: asset do concorrente, não idioma) =="
echo "-- Layer 1 (CRITÉRIO): PATH — HTML nosso referenciando pasta de referência/concorrente --"

# fragmentos de path que so existem em pasta de referencia do concorrente,
# nunca em asset nosso publicado (assets/, painel/capas, painel/conteudo).
PATH_PATTERNS=(
  'CLONE-ORIGINAL'
  'MOCKUPS-TROCAR'
  'concorrente'
  'original'
  'referencia'
  'mapadeltaro'
)

mapfile -t HTML_FILES < <(
  {
    [ -f index.html ] && echo index.html
    find painel -type f -name '*.html' 2>/dev/null
  } | sort -u
)

for f in "${HTML_FILES[@]}"; do
  [ -f "$f" ] || continue
  # so olha atributos de path de imagem (src/href/url(...)), nao texto solto
  refs=$(grep -inoE '(src|href)="[^"]+"|url\([^)]+\)' "$f" 2>/dev/null)
  [ -z "$refs" ] && continue
  for pat in "${PATH_PATTERNS[@]}"; do
    hit=$(echo "$refs" | grep -inE -- "$pat")
    if [ -n "$hit" ]; then
      echo "FALHOU [path] $f — referencia caminho de pasta de referência/concorrente ('$pat'):"
      echo "$hit" | sed 's/^/    /'
      FAIL=1
    fi
  done
done

if [ "$FAIL" -eq 0 ]; then
  echo "Layer 1 OK — nenhuma referência a pasta de concorrente/referência no HTML."
fi

echo ""
echo "-- Layer 2 (SECUNDÁRIA / smell test): texto que costuma vir junto de arte do concorrente --"
echo "   Isto é HEURÍSTICA, não a regra. Hit aqui é indício pra investigar se é"
echo "   arte/mockup do concorrente colada — NÃO falha o gate sozinho. Idioma não é critério."

TEXT_PATTERNS=(
  'mapadeltaro'
  'mapadeltarot'
  'mapa del tarot'
  'conceptos'
  'sumario'
  'arcanos mayores'
  'codigo de colores'
  'código de colores'
  'el viaje del loco'
  'preguntas poderosas'
  'hoja de trucos'
)

mapfile -t TEXT_FILES < <(
  {
    [ -f index.html ] && echo index.html
    find painel -type f -name '*.html' 2>/dev/null
    find . -type f \( -name '*.css' -o -name '*.js' \) -not -path './.git/*' 2>/dev/null
  } | sort -u
)

SMELL_HIT=0
for f in "${TEXT_FILES[@]}"; do
  [ -f "$f" ] || continue
  for pat in "${TEXT_PATTERNS[@]}"; do
    hit=$(grep -inE -- "$pat" "$f" 2>/dev/null)
    if [ -n "$hit" ]; then
      echo "SMELL [texto] $f — termo '$pat' (investigar se veio junto de asset do concorrente):"
      echo "$hit" | sed 's/^/    /'
      SMELL_HIT=1
    fi
  done
done

if [ "$SMELL_HIT" -eq 0 ]; then
  echo "Layer 2: nenhum indício textual — sem sinal de arte do concorrente colada."
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "GATE FALHOU — caminho de asset do concorrente referenciado na nossa peça. Corrija antes de commitar/publicar."
  exit 1
fi

echo "GATE OK — nenhum caminho de asset do concorrente referenciado nas peças nossas."
exit 0
