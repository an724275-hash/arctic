#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
test -f .env || { echo 'Run python3 deploy/init-env.py PUBLIC_ORIGIN first.' >&2; exit 1; }
test -f .runtime/nginx/default.conf || { echo 'Missing runtime nginx configuration.' >&2; exit 1; }
docker compose config --quiet
# Sequential builds reduce peak memory on the 2 GB host.
docker compose build migrate
docker compose build web
docker compose up -d --wait --wait-timeout 180 api web
docker compose exec -T web nginx -t
curl --fail --silent --show-error http://127.0.0.1/nginx-health
printf '\nServices started. Run the external HTTPS and participant checks from README.md.\n'
