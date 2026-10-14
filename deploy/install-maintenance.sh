#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ "$PWD" == /opt/arctic/deploy ]] || { echo 'Expected /opt/arctic/deploy.' >&2; exit 1; }
chmod 700 backup.sh verify-backup.sh nightly-backup.sh health-check.sh
cat >/etc/systemd/system/arctic-backup.service <<'EOF'
[Unit]
Description=Arctic database and uploads backup with restore verification
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/arctic/deploy
ExecStart=/opt/arctic/deploy/nightly-backup.sh
TimeoutStartSec=30min
Nice=10
EOF
cat >/etc/systemd/system/arctic-backup.timer <<'EOF'
[Unit]
Description=Nightly Arctic backup at 03:00 Yakutsk time

[Timer]
OnCalendar=*-*-* 18:00:00 UTC
RandomizedDelaySec=5min
Persistent=false

[Install]
WantedBy=timers.target
EOF
cat >/etc/systemd/system/arctic-health.service <<'EOF'
[Unit]
Description=Arctic readiness and disk checks
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/arctic/deploy
ExecStart=/opt/arctic/deploy/health-check.sh
TimeoutStartSec=45
EOF
cat >/etc/systemd/system/arctic-health.timer <<'EOF'
[Unit]
Description=Check Arctic health every five minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now arctic-backup.timer arctic-health.timer
systemctl start arctic-health.service
systemctl list-timers arctic-backup.timer arctic-health.timer --no-pager
