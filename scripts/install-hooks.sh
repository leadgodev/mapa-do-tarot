#!/usr/bin/env bash
# Instala o pre-commit hook (nao versionado em .git/) a partir de scripts/.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$REPO_ROOT/.git/hooks/pre-commit"

cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
exec "$REPO_ROOT/scripts/gate-identidade.sh"
EOF

chmod +x "$HOOK"
echo "pre-commit instalado em $HOOK"
