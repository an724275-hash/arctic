#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd "$(dirname "${BASH_SOURCE[0]}")"
docker compose --profile tls run --rm certbot renew --quiet --non-interactive
docker compose exec -T web nginx -t
docker compose exec -T web nginx -s reload
