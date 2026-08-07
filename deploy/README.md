# Instance deploy (comments.themarfa.name)

Self-hosted Artalk fork for `blog.themarfa.name`, reverse-proxied at `comments.themarfa.name`.

```bash
# VPS: pull pre-built image (no local build)
bash deploy/scripts/vps-deploy.sh
```

| Piece | Where it runs |
|---|---|
| Docker image build | GitHub Actions → `ghcr.io/marfa/artalk` |
| Runtime + SQLite data | VPS `/opt/artalk` |
| Nginx TLS terminator | Host nginx → `127.0.0.1:8085` |

## Quick start (VPS, one-time)

```bash
# On the VPS — migrate existing /opt/artalk into this git checkout
cd /opt
mv artalk artalk.bak
git clone https://github.com/Marfa/Artalk.git artalk
mkdir -p artalk/data
cp -a artalk.bak/data/. artalk/data/
cp -a artalk.bak/backups artalk/backups 2>/dev/null || true
cp deploy/.env.example .env
cp deploy/.env.secrets.example .env.secrets
# Fill ATK_APP_KEY and ATK_ADMIN_USERS_0_PASSWORD in .env.secrets (bcrypt `$` stays single).
chmod 600 .env .env.secrets
cd /opt/artalk
docker compose -f compose.instance.yml pull
docker compose -f compose.instance.yml up -d --no-build
```

After that, every push to `master` builds on GitHub and runs `deploy/scripts/vps-deploy.sh` over SSH.

## Secrets

GitHub Actions repo secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`.

| File | Contents |
|---|---|
| `/opt/artalk/.env` | Non-secret Compose vars (`ARTALK_IMAGE_TAG`, site URLs) |
| `/opt/artalk/.env.secrets` | `ATK_APP_KEY`, bcrypt admin password, optional `GHCR_TOKEN` |

Telegram / SMTP and other keys stay in `/opt/artalk/data/artalk.yml` (not in git). Use `deploy/artalk.yml.example` as a reference.

## Layout

| Path | Role |
|---|---|
| `compose.instance.yml` | Production compose (GHCR image, no `build:`) |
| `deploy/artalk.yml.example` | Sanitized instance config template |
| `deploy/nginx-artalk.conf` | Nginx site snippet |
| `deploy/scripts/vps-deploy.sh` | Pull image + restart |
| `deploy/scripts/backup.sh` | Nightly DB/export backup |
| `deploy/scripts/fc_to_artrans.py` | FastComments → Artrans migration |

## Author notes

Код подготовлен с помощью Cursor.

Поддержка проекта Донат https://www.donationalerts.com/r/themarfa  
Донат криптой https://nowpayments.io/donation/themarfa
