#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export LC_ALL=C

[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ -f .env && -f table-counts.sql ]] || { echo 'Deployment files are missing.' >&2; exit 1; }
command -v flock >/dev/null
exec 9>/var/lock/arctic-backup.lock
flock -n 9 || { echo 'Another backup or verification is running.' >&2; exit 1; }

backup_root=/var/backups/arctic
[[ ! -L "$backup_root" ]] || { echo 'Backup root must not be a symlink.' >&2; exit 1; }
install -d -m 700 -o root -g root "$backup_root"
backup_dir=$(mktemp -d "$backup_root/$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
resume_services=()

resume_writers() {
    if ((${#resume_services[@]})); then
        docker compose --profile mail start --wait --wait-timeout 120 "${resume_services[@]}" \
            >>"$backup_dir/services.log" 2>&1 || return 1
        resume_services=()
    fi
}

finish() {
    local result=$?
    trap - EXIT INT TERM
    if ! resume_writers; then
        echo "Writer restart failed; inspect $backup_dir/services.log and start the previous services." >&2
        result=1
    fi
    if ((result != 0)); then
        printf 'Backup did not finish successfully.\n' >"$backup_dir/INCOMPLETE"
        echo "Backup failed. Partial files remain private at $backup_dir" >&2
    fi
    exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker compose config --quiet 2>"$backup_dir/compose.log"
running=$(docker compose --profile mail ps --status running --services 2>>"$backup_dir/compose.log")
if grep -Fxq migrate <<<"$running"; then
    echo 'A migration is running. Retry when deployment has finished.' >&2
    exit 1
fi
grep -Fxq db <<<"$running" || { echo 'Database is not running.' >&2; exit 1; }
for service in api mail-worker; do
    if grep -Fxq "$service" <<<"$running"; then
        resume_services+=("$service")
    fi
done
printf '%s\n' "${resume_services[@]}" >"$backup_dir/running-writers.txt"

# Stop all application writers before capturing the database and its files.
if ((${#resume_services[@]})); then
    docker compose --profile mail stop --timeout 60 "${resume_services[@]}" \
        >>"$backup_dir/services.log" 2>&1
fi
docker compose exec -T db sh -c \
    'exec psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    <table-counts.sql >"$backup_dir/table-counts.tsv" 2>"$backup_dir/database.log"
[[ -s "$backup_dir/table-counts.tsv" ]] || { echo 'No public tables found.' >&2; exit 1; }
docker compose exec -T db sh -c \
    'exec pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    >"$backup_dir/database.dump" 2>>"$backup_dir/database.log"
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/storage -czf - . \
    >"$backup_dir/uploads.tar.gz" 2>"$backup_dir/uploads.log"
install -m 600 .env "$backup_dir/deployment.env"
gzip -t "$backup_dir/uploads.tar.gz"
tar -tzf "$backup_dir/uploads.tar.gz" >/dev/null
printf 'created_utc=%s\nformat=arctic-backup-v1\n' "$(date -u +%FT%TZ)" >"$backup_dir/metadata.txt"
(
    cd "$backup_dir"
    sha256sum database.dump uploads.tar.gz deployment.env table-counts.tsv metadata.txt >SHA256SUMS
)
resume_writers
printf 'Backup files captured; restore verification is a separate step.\n' >"$backup_dir/COMPLETE"
echo "Backup created: $backup_dir"
echo 'Run verify-backup.sh with this exact directory before relying on the copy.'
