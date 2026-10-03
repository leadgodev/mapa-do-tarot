#!/usr/bin/env bash
# Instala o pre-commit hook (nao versionado em .git/) a partir de scripts/.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$REPO_ROOT/.git/hooks/pre-commit"

cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
"$REPO_ROOT/scripts/gate-identidade.sh" || exit 1
# Módulos de imagem: PDF sai na hora do array pages (server/modulo-pdf.mjs), nada a conferir.
# Módulos HTML (cigano-*): PDF estático tem que existir e ser mais novo que o index.html.
for d in "$REPO_ROOT"/painel/conteudo/cigano-*/; do
  k=$(basename "$d")
  [ -f "$d/index.html" ] || continue
  if [ ! -f "$d/$k.pdf" ] || [ "$d/index.html" -nt "$d/$k.pdf" ]; then
    echo "PDF desatualizado: $k. Rode: chromium --headless --no-pdf-header-footer --print-to-pdf=\"$d$k.pdf\" \"file://$d""index.html\"" >&2
    exit 1
  fi
done
EOF

chmod +x "$HOOK"
echo "pre-commit instalado em $HOOK"
