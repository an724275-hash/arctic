# HTTPS на публичном IPv4

`enable-ip-tls.sh` настраивает текущий Compose для `95.85.251.67` без домена. Скрипт предназначен для root, Ubuntu 24.04/22.04 с systemd и пути `/opt/arctic`. Наличие скрипта не подтверждает выпуск сертификата: результат серверного запуска и приёмки фиксируется отдельно в `status.json`.

Let's Encrypt выпускает публично доверенные IP-сертификаты с профилем `shortlived` на **160 часов**. Для IP и webroot требуется Certbot **5.4 или новее**; скрипт обновляет образ `certbot/certbot:latest` и проверяет версию перед обращением к CA. Используются `--ip-address`, а не `-d`, и `--cert-name`, равный IP. [Срок действия и доступность](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability), [официальный способ выпуска](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html).

## Первый запуск

Сначала HTTP-стек должен отвечать, а входящие порты 80/443 — быть доступны из интернета. Проверка владения IP идёт по `/.well-known/acme-challenge/` на **80**, который остаётся открытым для последующих продлений. Файлы challenge находятся в общем volume `acme`; весь каталог `/etc/letsencrypt` — в volume `certificates`.

В `deploy/.env` измените только `PUBLIC_ORIGIN` на `https://95.85.251.67`, сохранив существующие секреты. Затем:

```bash
cd /opt/arctic
bash -n deploy/enable-ip-tls.sh
bash -n deploy/renew-tls.sh
bash deploy/enable-ip-tls.sh 95.85.251.67
```

Без второго аргумента Certbot получает `--register-unsafely-without-email`: CA-аккаунт регистрируется без контактного email, адрес не выдумывается. Этот параметр поддерживается в [исходнике Certbot v5.8.0](https://github.com/certbot/certbot/blob/v5.8.0/certbot/src/certbot/_internal/cli/__init__.py), хотя скрыт из общего help. При необходимости второй аргумент может содержать реальный email владельца. Это не отключает проверку TLS и не меняет доверие к сертификату. Let's Encrypt [прекратил письма об истечении сертификатов](https://letsencrypt.org/2025/01/22/ending-expiration-emails.html) 4 июня 2025 года; наличие email не заменяет контроль продления.

Скрипт получает production-сертификат, проверяет nginx, дожидается API с HTTPS-origin, включает HTTPS и перенаправляет обычный HTTP на HTTPS. Проверка ACME остаётся доступной по HTTP. При ошибке `nginx -t` возвращается прежний конфиг. Проверяются SAN типа `IP Address`, цепочка доверия системным CA-хранилищем, readiness API, ответ HTTP 301 и активность таймера. Приватный ключ не выводится и остаётся в Docker volume.

## Продление дважды в сутки

Скрипт устанавливает `arctic-cert-renew.timer`: **03:17 и 15:17 по времени VPS**, с задержкой до пяти минут; `Persistent=true` догоняет пропущенный запуск после выключения. Systemd вызывает `renew-tls.sh`: Certbot обновляет только подходящие к сроку сертификаты, затем nginx проверяет конфигурацию и перечитывает сертификаты. Повторного выпуска при каждом запуске нет. Для сертификатов до 10 дней Certbot начинает продление при оставшейся половине срока; исходные параметры webroot/профиля сохраняются в volume. [Правила renew](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).

```bash
systemctl list-timers arctic-cert-renew.timer
systemctl status arctic-cert-renew.timer --no-pager
journalctl -u arctic-cert-renew.service --no-pager -n 40
```

Приёмка ACME-продления после первого выпуска:

```bash
cd /opt/arctic/deploy
docker compose --profile tls run --rm certbot renew \
  --cert-name 95.85.251.67 --dry-run --non-interactive
```

`--dry-run` обращается к staging CA и не заменяет действующий production-сертификат. Успешный dry-run проверяет текущую доступность challenge, но не гарантирует будущую доступность VPS. Не добавляйте одновременно cron-задание из доменного сценария: для этого IP уже установлен systemd timer. Ошибки продления доступны в journal; внешнее оповещение этим комплектом не настроено.

## Повторная проверка публичного HTTPS

```bash
curl --fail --show-error https://95.85.251.67/health/ready
curl --silent --show-error --output /dev/null \
  --write-out '%{http_code} %{redirect_url}\n' http://95.85.251.67/
openssl s_client -connect 95.85.251.67:443 -verify_ip 95.85.251.67 \
  -verify_return_error -CApath /etc/ssl/certs -brief </dev/null
```

Ожидаются readiness PostgreSQL, `301 https://95.85.251.67/` и успешная проверка TLS. В `openssl` обязателен `-verify_return_error`: без него диагностическая утилита может продолжить соединение после ошибки. [Документация OpenSSL](https://docs.openssl.org/3.0/man1/openssl-s_client/). В командах не используется `curl -k`, self-signed или staging-сертификат на публичном nginx.

При смене IP нужно выпустить сертификат для нового адреса, обновить `PUBLIC_ORIGIN` и nginx. DNS не требуется для этого сценария; скрипт намеренно принимает только канонический публичный IPv4. Переезд на домен выполняется отдельным `enable-tls.sh`.
