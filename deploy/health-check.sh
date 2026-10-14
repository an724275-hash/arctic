#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
status=0
curl --fail --silent --show-error --max-time 15 https://95.85.251.67/health/ready >/dev/null || status=1
for service in db api web; do
    id=$(docker compose ps -q "$service")
    if [[ -z "$id" ]] || [[ $(docker inspect --format '{{.State.Health.Status}}' "$id") != healthy ]]; then
        echo "Unhealthy service: $service" >&2
        status=1
    fi
done
available=$(df --output=avail -k /var/backups/arctic | tail -n 1 | tr -d ' ')
if ((available < 2097152)); then
    echo 'Less than 2 GiB of disk space is available; review backups and uploads.' >&2
    status=1
fi
if ((status)); then
    logger -p daemon.err -t arctic-health 'Readiness, container health or disk check failed.'
    exit 1
fi
echo 'Readiness, three containers and disk space: healthy.'
