#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
. /etc/os-release
[[ "$ID" == ubuntu ]] || { echo 'This installer targets Ubuntu 22.04 or 24.04.' >&2; exit 1; }
case "$VERSION_ID" in
    22.04) docker_suite=jammy ;;
    24.04) docker_suite=noble ;;
    *) echo 'This installer targets Ubuntu 22.04 or 24.04.' >&2; exit 1 ;;
esac
apt-get update
apt-get install -y ca-certificates curl python3 unzip
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $docker_suite
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker compose version
