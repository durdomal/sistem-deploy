#!/usr/bin/env bash
# Sistem Core — идемпотентный установщик на Netcup VPS 152.53.231.15
# Запускать под root или sudo. Безопасно перезапускать.
#
# Что делает:
#   1. Создаёт /opt/sistem структуру
#   2. Копирует репо-содержимое (если запускаешь из git-clone)
#   3. Проверяет наличие docker / docker compose / nginx / certbot
#   4. Готовит .env (если нет — из .env.example, требует ручной правки)
#   5. Стартует docker-compose (без падения при повторе)
#   6. Настраивает nginx-конфиг + сертификат Let's Encrypt (webroot, БЕЗ --nginx)
#   7. Reload nginx
#
# Финальные ручные действия — вписать реальные секреты в /opt/sistem/deploy/.env.

set -Eeuo pipefail

DOMAIN="sistem.globria.biz"
INSTALL_ROOT="/opt/sistem"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { echo -e "\e[1;34m[sistem]\e[0m $*"; }
die() { echo -e "\e[1;31m[fatal]\e[0m $*"; exit 1; }

[[ $EUID -eq 0 ]] || die "запусти под root"

log "1/7 Готовим директории"
mkdir -p "$INSTALL_ROOT"/{app,db,deploy,scripts,data/postgres,data/redis}
mkdir -p /var/www/letsencrypt

log "2/7 Копируем содержимое sistem-core → $INSTALL_ROOT"
rsync -a --delete \
    --exclude 'deploy/.env' \
    --exclude 'data' \
    "$REPO_ROOT/" "$INSTALL_ROOT/"

log "3/7 Проверяем зависимости"
for bin in docker nginx certbot rsync openssl; do
    command -v "$bin" >/dev/null || die "нет $bin — установи (apt install $bin)"
done
docker compose version >/dev/null 2>&1 || die "нет docker compose v2"

log "4/7 .env"
if [[ ! -f "$INSTALL_ROOT/deploy/.env" ]]; then
    cp "$INSTALL_ROOT/deploy/.env.example" "$INSTALL_ROOT/deploy/.env"
    echo
    echo ">>> ВНИМАНИЕ: $INSTALL_ROOT/deploy/.env создан из шаблона."
    echo ">>> Открой и впиши: POSTGRES_PASSWORD, REDIS_PASSWORD,"
    echo ">>> JWT_PRIVATE_KEY, JWT_PUBLIC_KEY, SISTEM_SECRETS_KEY."
    echo ">>> После этого перезапусти bootstrap.sh."
    exit 0
fi

log "5/7 Стартуем docker-compose"
cd "$INSTALL_ROOT/deploy"
docker compose --env-file .env pull || true
docker compose --env-file .env up -d --build

log "6/7 Nginx + SSL"
if [[ ! -e /etc/nginx/sites-available/sistem.conf ]]; then
    cp "$INSTALL_ROOT/deploy/nginx-sistem.conf" /etc/nginx/sites-available/sistem.conf
fi
ln -sf /etc/nginx/sites-available/sistem.conf /etc/nginx/sites-enabled/sistem.conf

if [[ ! -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
    log "  Получаем сертификат (webroot, НЕ --nginx!)"
    # временный HTTP-only конфиг чтобы certbot прошёл, если ещё нет SSL-файлов
    cat >/etc/nginx/sites-enabled/sistem-acme-tmp.conf <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/letsencrypt; }
    location / { return 404; }
}
EOF
    nginx -t && systemctl reload nginx
    certbot certonly --webroot -w /var/www/letsencrypt -d "$DOMAIN" \
        --agree-tos -m sullenlar4@gmail.com --non-interactive || \
        die "certbot не смог получить сертификат — проверь DNS A-запись $DOMAIN"
    rm /etc/nginx/sites-enabled/sistem-acme-tmp.conf
fi

log "7/7 Проверка nginx и reload"
nginx -t
systemctl reload nginx

log "Готово. Проверь: curl -s https://$DOMAIN/health"
