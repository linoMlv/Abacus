#!/usr/bin/env bash
# Abacus — local production-simulation environment, in one command.
#
# Builds the real production image (front + back), runs it with PostgreSQL,
# applies migrations, and (on `up`) seeds a ready-to-use demo login. Everything
# lives in an isolated docker compose project ("abacus-test") with its own
# volume, so it never touches any other local data.
#
# Usage:
#   ./scripts/run-test.sh [up]     Build + start (default), then seed demo data
#   ./scripts/run-test.sh down     Stop (data kept)
#   ./scripts/run-test.sh reset    Stop + wipe the test database volume
#   ./scripts/run-test.sh logs     Follow the app logs
#   ./scripts/run-test.sh seed     (Re)create the demo account/association
#   ./scripts/run-test.sh psql     Open a psql shell in the db container
#   ./scripts/run-test.sh status   Show container status
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="abacus-test"
ENV_FILE=".env.test"
URL="http://localhost:8000"

DEMO_EMAIL="demo@abacus.test"
DEMO_PASSWORD="demo-password-123"
DEMO_NAME="Trésorier Démo"
DEMO_ASSO="Association Démo"

compose() {
  docker compose -p "$PROJECT" --env-file "$ENV_FILE" \
    -f docker-compose.yml -f docker-compose.test.yml "$@"
}

require_env() {
  if [ ! -f "$ENV_FILE" ]; then
    echo "Erreur : $ENV_FILE introuvable (il devrait être versionné)." >&2
    exit 1
  fi
}

wait_for_health() {
  printf 'Attente du démarrage de l’app'
  for _ in $(seq 1 60); do
    if curl -fsS "$URL/health" >/dev/null 2>&1; then
      echo " — prêt."
      return 0
    fi
    printf '.'
    sleep 2
  done
  echo
  echo "L’app n’a pas répondu sur $URL/health. Voir : ./scripts/run-test.sh logs" >&2
  return 1
}

seed_demo() {
  # Best-effort: idempotent enough (a second run just no-ops on 400 "exists").
  local jar
  jar="$(mktemp)"
  trap 'rm -f "$jar"' RETURN

  curl -fsS -X POST "$URL/api/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\",\"name\":\"$DEMO_NAME\"}" \
    >/dev/null 2>&1 || true

  if ! curl -fsS -c "$jar" -X POST "$URL/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\"}" >/dev/null 2>&1; then
    echo "Seed : connexion démo impossible (l’app est-elle prête ?)." >&2
    return 0
  fi

  # Create the demo association only if the account has none yet.
  if curl -fsS -b "$jar" "$URL/api/auth/associations" 2>/dev/null | grep -q '"id"'; then
    return 0
  fi
  curl -fsS -b "$jar" -X POST "$URL/api/auth/associations" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$DEMO_ASSO\",\"email\":\"contact@asso.test\"}" >/dev/null 2>&1 || true
}

cmd_up() {
  require_env
  echo "Build + démarrage de l’environnement de test (projet $PROJECT)…"
  compose up -d --build
  wait_for_health
  echo "Initialisation des données de démo…"
  seed_demo
  cat <<EOF

✅ Abacus (simulation de prod) tourne sur $URL

  Connexion démo :
    e-mail        $DEMO_EMAIL
    mot de passe  $DEMO_PASSWORD
    (association « $DEMO_ASSO » déjà créée, plan comptable seedé)

  Page de logs (HTTP Basic) : $URL/api/logs  (admin / admin)
  PostgreSQL (hôte)         : localhost:5432  (abacus / abacus / abacus)

  Logs en direct : ./scripts/run-test.sh logs
  Arrêt          : ./scripts/run-test.sh down   (données conservées)
  Remise à zéro  : ./scripts/run-test.sh reset  (efface la base de test)
EOF
}

case "${1:-up}" in
  up) cmd_up ;;
  down) require_env; compose down ;;
  reset)
    require_env
    compose down -v
    echo "Volume de test effacé. Relancez : ./scripts/run-test.sh up"
    ;;
  logs) require_env; compose logs -f app ;;
  seed) seed_demo && echo "Données de démo prêtes ($DEMO_EMAIL / $DEMO_PASSWORD)." ;;
  psql)
    require_env
    compose exec db psql -U abacus -d abacus
    ;;
  status) require_env; compose ps ;;
  *)
    echo "Usage: $0 {up|down|reset|logs|seed|psql|status}" >&2
    exit 1
    ;;
esac
