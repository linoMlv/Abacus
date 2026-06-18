#!/usr/bin/env bash
# Launch Abacus locally with your .env and the app port published on the host.
# For local testing only — production uses `docker compose up` (no port mapping).
set -euo pipefail

# Run from the repo root regardless of where the script is invoked.
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Erreur : fichier .env introuvable à la racine." >&2
  echo "Créez-le : cp .env.example .env  (puis renseignez vos valeurs)." >&2
  exit 1
fi

echo "Démarrage d'Abacus (build + migrations au démarrage)..."
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build

cat <<'EOF'

Abacus est lancé : http://localhost:8000

  Logs en direct : docker compose logs -f app
  Arrêt (données conservées) : docker compose down
  Ne JAMAIS utiliser `down -v` : cela supprime le volume et les données.
EOF
