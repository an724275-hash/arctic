#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
available=$(df --output=avail -k /var | tail -n 1 | tr -d ' ')
((available >= 2097152)) || { echo 'Backup refused: less than 2 GiB free.' >&2; exit 1; }
./backup.sh
# Verification targets a separate temporary database, never the working one.
latest=$(find /var/backups/arctic -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tail -n 1)
[[ -n "$latest" && "$latest" != */* ]] || exit 1
./verify-backup.sh "/var/backups/arctic/$latest"
