#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
deploy_dir="$(pwd -P)"
ip="${1:?Usage: bash deploy/enable-ip-tls.sh PUBLIC_IPV4 [REAL_EMAIL]}"
email="${2:-}"
[[ $# -le 2 && "$EUID" -eq 0 ]] || { echo 'Run as root; arguments: PUBLIC_IPV4 [REAL_EMAIL].' >&2; exit 1; }
for tool in docker python3 openssl curl timeout systemctl; do
    command -v "$tool" >/dev/null || { echo "Missing command: $tool" >&2; exit 1; }
done
python3 - "$ip" <<'PY'
import ipaddress
import sys
try:
    address = ipaddress.IPv4Address(sys.argv[1])
except ValueError:
    raise SystemExit('A canonical public IPv4 address is required.')
if not address.is_global or str(address) != sys.argv[1]:
    raise SystemExit('A canonical public IPv4 address is required.')
PY
grep -Fxq "PUBLIC_ORIGIN=https://$ip" .env || { echo "Set PUBLIC_ORIGIN=https://$ip in deploy/.env first." >&2; exit 1; }
test -f .runtime/nginx/default.conf || { echo 'Start the HTTP stack with up.sh first.' >&2; exit 1; }
[[ "$deploy_dir" != *[[:space:]]* ]] || { echo 'The deployment path must not contain whitespace.' >&2; exit 1; }

docker compose --profile tls pull certbot
certbot_version="$(docker compose --profile tls run --rm certbot --version)"
if [[ "$certbot_version" =~ ([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
    (( BASH_REMATCH[1] > 5 || (BASH_REMATCH[1] == 5 && BASH_REMATCH[2] >= 4) )) || { echo 'Certbot 5.4+ is required for IP webroot validation.' >&2; exit 1; }
else
    echo 'Unable to verify the Certbot version.' >&2
    exit 1
fi
printf '%s\n' "$certbot_version"
contact_args=(--register-unsafely-without-email)
if [[ -n "$email" ]]; then
    contact_args=(--email "$email")
fi
docker compose --profile tls run --rm certbot certonly \
    --non-interactive --agree-tos --no-eff-email "${contact_args[@]}" \
    --webroot -w /var/www/acme --preferred-profile shortlived \
    --ip-address "$ip" --cert-name "$ip" --keep-until-expiring

cp .runtime/nginx/default.conf .runtime/nginx.previous.conf
sed "s/__DOMAIN__/$ip/g; s/listen 443 ssl;/listen 443 ssl default_server;/" \
    nginx-https.conf.template > .runtime/nginx/default.conf
if ! docker compose exec -T web nginx -t; then
    cp .runtime/nginx.previous.conf .runtime/nginx/default.conf
    echo 'Previous nginx configuration restored; check certificate paths.' >&2
    exit 1
fi
docker compose up -d --wait --wait-timeout 180 api
docker compose exec -T web nginx -s reload

# Docker Certbot has no host timer; reload nginx after successful renewals.
cat > /etc/systemd/system/arctic-cert-renew.service <<EOF
[Unit]
Description=Renew Arctic HTTPS certificates
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash $deploy_dir/renew-tls.sh
TimeoutStartSec=1800
EOF
cat > /etc/systemd/system/arctic-cert-renew.timer <<'EOF'
[Unit]
Description=Check Arctic HTTPS certificates twice daily

[Timer]
OnCalendar=*-*-* 03,15:17:00
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
EOF
chmod 644 /etc/systemd/system/arctic-cert-renew.service /etc/systemd/system/arctic-cert-renew.timer
systemctl daemon-reload
systemctl enable --now arctic-cert-renew.timer

docker compose exec -T web cat "/etc/letsencrypt/live/$ip/fullchain.pem" \
    | openssl x509 -noout -checkip "$ip" -ext subjectAltName -dates
printf 'HEAD / HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n' "$ip" \
    | timeout 20 openssl s_client -connect "$ip:443" -verify_ip "$ip" \
        -verify_return_error -CApath /etc/ssl/certs -brief
curl --fail --silent --show-error --retry 5 --retry-delay 2 --retry-connrefused "https://$ip/health/ready"
redirect="$(curl --silent --show-error --output /dev/null --write-out '%{http_code} %{redirect_url}' "http://$ip/")"
[[ "$redirect" == "301 https://$ip/" ]] || { echo "Unexpected HTTP redirect: $redirect" >&2; exit 1; }
systemctl is-enabled --quiet arctic-cert-renew.timer
systemctl is-active --quiet arctic-cert-renew.timer
printf '\nHTTPS enabled for %s; IP SAN and trust verified; renewal timer active.\n' "$ip"
