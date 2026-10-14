#!/usr/bin/env python3
"""Create host-specific configuration without printing secrets."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument("origin", help="Public origin, e.g. https://arctic.example.org")
args = parser.parse_args()
url = urlsplit(args.origin)
if (url.scheme not in {"http", "https"} or not url.hostname or url.username
        or url.password or url.path not in {"", "/"} or url.query or url.fragment
        or any(c in args.origin for c in "\n\r$#'\" ")):
    raise SystemExit("Expected an HTTP(S) origin without path, credentials or whitespace")
root = Path(__file__).resolve().parent
env = root / ".env"
if env.exists():
    raise SystemExit("deploy/.env already exists; preserved. Edit it manually if needed.")
os.umask(0o077)
origin = args.origin.rstrip("/")
content = (
    f"PUBLIC_ORIGIN={origin}\n"
    f"POSTGRES_PASSWORD={secrets.token_urlsafe(36)}\n"
    f"JWT_SECRET={secrets.token_urlsafe(48)}\n"
    "ENABLE_EMAIL_DELIVERY=false\nSMTP_HOST=\nSMTP_PORT=587\nSMTP_USER=\n"
    "SMTP_PASSWORD=\nSMTP_FROM=noreply@example.com\nSMTP_STARTTLS=true\n"
)
with env.open("x", encoding="utf-8") as file:
    file.write(content)
env.chmod(0o600)
nginx = root / ".runtime" / "nginx"
nginx.mkdir(parents=True, exist_ok=True)
nginx.chmod(0o755)
target = nginx / "default.conf"
if not target.exists():
    shutil.copyfile(root / "nginx-http.conf", target)
target.chmod(0o644)
print("Created deploy/.env (0600), secrets not displayed. Initial proxy is HTTP; enable TLS before real sign-ins.")
