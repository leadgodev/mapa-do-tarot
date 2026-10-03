#!/bin/bash
# Gera .webp ao lado de cada .jpg/.png do painel (páginas, capas, assets).
# O servidor entrega o .webp no lugar do .jpg quando o browser aceita (mesma URL).
# Idempotente: só refaz quando o .webp não existe ou é mais velho que o original.
# Rodar depois de adicionar páginas novas, antes do commit.
set -euo pipefail
cd "$(dirname "$0")/.."
MAXW=${MAXW:-1200}
QUAL=${QUAL:-78}
n=0
while IFS= read -r -d '' f; do
  w="${f%.*}.webp"
  if [ ! -e "$w" ] || [ "$f" -nt "$w" ]; then
    magick "$f" -resize "${MAXW}x>" -strip -quality "$QUAL" -define webp:method=6 "$w"
    n=$((n+1))
  fi
done < <(find painel -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) -not -path '*/_*' -print0)
echo "webp gerados/atualizados: $n"
