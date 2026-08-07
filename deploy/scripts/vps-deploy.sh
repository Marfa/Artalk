#!/usr/bin/env bash
# Pull pre-built Artalk GHCR image; build tiny marfabot sidecar locally; restart.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/artalk}"
COMPOSE_FILE="${COMPOSE_FILE:-compose.instance.yml}"
BRANCH="${DEPLOY_BRANCH:-master}"
IMAGE="${ARTALK_IMAGE:-ghcr.io/marfa/artalk:instance-latest}"

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: $APP_DIR/.env is missing" >&2
  exit 1
fi

cp -a .env /tmp/artalk.env.bak
if [[ -f .env.secrets ]]; then
  cp -a .env.secrets /tmp/artalk.env.secrets.bak
fi

git fetch --prune origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

cp -a /tmp/artalk.env.bak .env
rm -f /tmp/artalk.env.bak
if [[ -f /tmp/artalk.env.secrets.bak ]]; then
  cp -a /tmp/artalk.env.secrets.bak .env.secrets
  rm -f /tmp/artalk.env.secrets.bak
fi

# Optional private GHCR: read token without `source` (bcrypt `$` must not expand).
if [[ -f .env.secrets ]]; then
  GHCR_TOKEN="$(grep -E '^GHCR_TOKEN=' .env.secrets | head -1 | cut -d= -f2- || true)"
  GHCR_USER="$(grep -E '^GHCR_USER=' .env.secrets | head -1 | cut -d= -f2- || true)"
  GHCR_USER="${GHCR_USER:-Marfa}"
fi
if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

docker compose -f "$COMPOSE_FILE" pull artalk
docker compose -f "$COMPOSE_FILE" build --pull marfabot
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans --build marfabot
# Ensure artalk is up with the newly pulled image (no rebuild).
docker compose -f "$COMPOSE_FILE" up -d --no-build artalk

if [[ -f deploy/scripts/backup.sh ]]; then
  install -m 755 deploy/scripts/backup.sh /usr/local/sbin/artalk-backup
  cat >/etc/cron.d/artalk-backup <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
15 3 * * * root /usr/local/sbin/artalk-backup >>/var/log/artalk-backup.log 2>&1
EOF
  chmod 644 /etc/cron.d/artalk-backup
fi

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8085/" >/dev/null 2>&1; then
    echo "health: ok ($IMAGE)"
    docker compose -f "$COMPOSE_FILE" ps
    exit 0
  fi
  sleep 2
done

echo "WARNING: Artalk did not become ready in time" >&2
docker compose -f "$COMPOSE_FILE" ps
docker compose -f "$COMPOSE_FILE" logs --tail=80 artalk || true
exit 1
