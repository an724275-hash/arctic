from collections import defaultdict, deque
from time import monotonic
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import settings


class ApiMiddleware:
    def __init__(self, app):
        self.app = app
        self.buckets = defaultdict(deque)
        self.last_cleanup = monotonic()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        request_id = uuid4().hex
        path = scope.get("path", "")
        maximum = (settings.max_upload_mb + 2) * 1024 * 1024
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
        if length > maximum:
            return await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)

        if settings.environment != "test" and path.startswith("/api/"):
            now = monotonic()
            client = scope.get("client") or ("unknown", 0)
            auth = "/auth/" in path or path.endswith("/contact")
            key = (client[0], auth)
            bucket = self.buckets[key]
            while bucket and bucket[0] < now - 60:
                bucket.popleft()
            cap = settings.auth_rate_limit_per_minute if auth else settings.rate_limit_per_minute
            if len(bucket) >= cap:
                return await JSONResponse(
                    {"detail": "Слишком много запросов"}, 429, headers={"Retry-After": "60"}
                )(scope, receive, send)
            bucket.append(now)
            if now - self.last_cleanup > 60:
                self.buckets = defaultdict(
                    deque, {k: v for k, v in self.buckets.items() if v and v[-1] >= now - 60}
                )
                self.last_cleanup = now

        received = 0
        started = False

        async def checked_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > maximum:
                    raise BodyTooLarge()
            return message

        async def secured_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                response_headers = message.setdefault("headers", [])
                defaults = [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                ]
                existing = {key.lower() for key, _ in response_headers}
                response_headers.extend((key, value) for key, value in defaults if key not in existing)
                if not any(key.lower() == b"cache-control" for key, _ in response_headers):
                    response_headers.append((b"cache-control", b"no-store"))
            await send(message)

        try:
            await self.app(scope, checked_receive, secured_send)
        except BodyTooLarge:
            if not started:
                await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)


class BodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(status_code=413, detail="Request body too large")
