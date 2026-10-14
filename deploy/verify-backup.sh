#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export LC_ALL=C

[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
[[ $# -eq 1 ]] || { echo "Usage: $0 /var/backups/arctic/<UTC-directory>" >&2; exit 1; }
backup_dir=$(realpath -e -- "$1")
[[ -d "$backup_dir" && "$backup_dir" == /var/backups/arctic/* ]] || {
    echo 'Select a backup directory inside /var/backups/arctic.' >&2; exit 1;
}
[[ $(stat -c '%u:%a' "$backup_dir") == 0:700 ]] || {
    echo 'Backup directory must be owned by root with mode 700.' >&2; exit 1;
}
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec 9>/var/lock/arctic-backup.lock
flock -n 9 || { echo 'Another backup or verification is running.' >&2; exit 1; }
for item in COMPLETE SHA256SUMS database.dump uploads.tar.gz deployment.env table-counts.tsv metadata.txt; do
    [[ -f "$backup_dir/$item" && ! -L "$backup_dir/$item" ]] || { echo "Missing or unsafe backup file: $item" >&2; exit 1; }
    [[ $(stat -c '%u:%a' "$backup_dir/$item") == 0:600 ]] || { echo "Backup file must be root-owned, mode 600: $item" >&2; exit 1; }
done
[[ ! -e "$backup_dir/INCOMPLETE" ]] || { echo 'This backup is incomplete.' >&2; exit 1; }

work_dir=$(mktemp -d "$backup_dir/verify-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
temp_db="arctic_verify_$(date -u +%Y%m%d%H%M%S)_$$_${RANDOM}"
[[ "$temp_db" =~ ^arctic_verify_[0-9_]+$ && ${#temp_db} -lt 63 ]] || exit 1
created=0

drop_temporary_database() {
    if ((created)); then
        docker compose exec -T db sh -c \
            'exec dropdb --force -U "$POSTGRES_USER" -- "$1"' sh "$temp_db" \
            >>"$work_dir/database.log" 2>&1 || return 1
        created=0
    fi
}

finish() {
    local result=$?
    trap - EXIT INT TERM
    if ! drop_temporary_database; then
        echo "Could not remove the verification database $temp_db; inspect $work_dir/database.log" >&2
        result=1
    fi
    if ((result != 0)); then
        printf 'failed\n' >"$work_dir/status.txt"
        echo "Verification failed; private diagnostics: $work_dir" >&2
    fi
    exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Only the five known files are checked; never follow arbitrary manifest paths.
(
    cd "$backup_dir"
    sha256sum database.dump uploads.tar.gz deployment.env table-counts.tsv metadata.txt
) >"$work_dir/SHA256SUMS.actual"
cmp -s "$backup_dir/SHA256SUMS" "$work_dir/SHA256SUMS.actual" || {
    echo 'Backup checksum mismatch.' >&2; exit 1;
}
gzip -t "$backup_dir/uploads.tar.gz" 2>"$work_dir/uploads.log"
tar -tzf "$backup_dir/uploads.tar.gz" >"$work_dir/uploads-members.txt" 2>>"$work_dir/uploads.log"
docker compose exec -T db pg_restore --list \
    <"$backup_dir/database.dump" >"$work_dir/dump-contents.txt" 2>"$work_dir/database.log"

# createdb refuses an existing name. Cleanup is armed only after it succeeds.
docker compose exec -T db sh -c \
    'exec createdb --template=template0 -U "$POSTGRES_USER" -- "$1"' sh "$temp_db" \
    >>"$work_dir/database.log" 2>&1
created=1
docker compose exec -T db sh -c \
    'exec pg_restore --exit-on-error --single-transaction --no-owner --no-privileges -U "$POSTGRES_USER" --dbname="$1"' sh "$temp_db" \
    <"$backup_dir/database.dump" >>"$work_dir/database.log" 2>&1
docker compose exec -T db sh -c \
    'exec psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$temp_db" \
    <table-counts.sql >"$work_dir/table-counts.tsv" 2>>"$work_dir/database.log"
cmp -s "$backup_dir/table-counts.tsv" "$work_dir/table-counts.tsv" || {
    echo 'Restored table names or row counts differ from the backup.' >&2; exit 1;
}
table_count=$(wc -l <"$work_dir/table-counts.tsv")
[[ $table_count -gt 0 ]] || { echo 'Restored database has no public tables.' >&2; exit 1; }
drop_temporary_database
printf 'passed\nverified_utc=%s\ntables=%s\n' "$(date -u +%FT%TZ)" "$table_count" >"$work_dir/status.txt"
echo "Verification passed: $table_count tables with matching row counts; uploads archive and file checksums passed."
echo "Temporary database removed. Private verification receipt: $work_dir/status.txt"
