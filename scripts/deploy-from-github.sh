#!/usr/bin/env bash
# Actualiza el código desde GitHub y reconstruye los contenedores.
# Uso en el servidor: ./scripts/deploy-from-github.sh
# Cron cada hora: 0 * * * * cd /ruta/Dashboard && ./scripts/deploy-from-github.sh >> /var/log/dashboard-deploy.log 2>&1

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BRANCH="${DEPLOY_BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git no está instalado." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker no está instalado." >&2
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Error: no se encontró $COMPOSE_FILE en $ROOT_DIR" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "Error: crea .env a partir de .env.example antes de desplegar." >&2
  exit 1
fi

echo "==> Fetch origin ($BRANCH)"
git fetch origin "$BRANCH"

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "==> Ya estás en el último commit ($LOCAL). Reconstruyendo por si hubo cambios locales en Docker."
else
  echo "==> Actualizando $LOCAL -> $REMOTE"
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
fi

echo "==> docker compose build"
docker compose -f "$COMPOSE_FILE" build --pull

echo "==> docker compose up"
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

docker image prune -f >/dev/null 2>&1 || true

echo "==> Despliegue listo ($(git rev-parse --short HEAD))"
