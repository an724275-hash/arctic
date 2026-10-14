#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
domain="${1:?Usage: bash deploy/enable-tls.sh DOMAIN EMAIL}"
email="${2:?Email is required for certificate expiry notices}"
[[ "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] || { echo 'Invalid domain' >&2; exit 1; }
grep -Fxq "PUBLIC_ORIGIN=https://$domain" .env || { echo 'Set PUBLIC_ORIGIN=https://DOMAIN in deploy/.env first.' >&2; exit 1; }
docker compose --profile tls run --rm certbot certonly --non-interactive --webroot -w /var/www/acme --cert-name "$domain" -d "$domain" --email "$email" --agree-tos --no-eff-email
cp .runtime/nginx/default.conf .runtime/nginx.previous.conf
sed "s/__DOMAIN__/$domain/g" nginx-https.conf.template > .runtime/nginx/default.conf
if ! docker compose exec -T web nginx -t; then
    cp .runtime/nginx.previous.conf .runtime/nginx/default.conf
    echo 'Previous nginx configuration restored; check certificate paths.' >&2
    exit 1
fi
docker compose up -d --wait --wait-timeout 180 api
docker compose exec -T web nginx -s reload
curl --fail --silent --show-error --retry 5 --retry-delay 2 --retry-connrefused "https://$domain/health/ready"
printf '\nHTTPS configured. Install the renewal timer from README.md.\n'
