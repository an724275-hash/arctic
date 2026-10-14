import asyncio

from fastapi import FastAPI, File, UploadFile

from app.config import settings
from app.middleware import ApiMiddleware


def streamed_request(app, content_type, chunks):
    messages = iter(chunks)
    responses = []

    async def receive():
        try:
            return {"type": "http.request", "body": next(messages), "more_body": True}
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        responses.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": "POST",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": [(b"content-type", content_type)],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 8000),
    }
    asyncio.run(app(scope, receive, send))
    return next(message["status"] for message in responses if message["type"] == "http.response.start")


def test_streaming_json_limit_returns_413(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    app = FastAPI()
    app.add_middleware(ApiMiddleware)

    @app.post("/upload")
    def upload(payload: dict):
        return {"accepted": True}

    chunks = [b'{"body":"', *([b"a" * (1024 * 1024)] * 4), b'"}']
    assert streamed_request(app, b"application/json", chunks) == 413


def test_streaming_multipart_limit_closes_temporary_file(monkeypatch):
    import starlette.formparsers

    monkeypatch.setattr(settings, "max_upload_mb", 1)
    opened = []
    original = starlette.formparsers.SpooledTemporaryFile

    def tracked_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", tracked_file)
    app = FastAPI()
    app.add_middleware(ApiMiddleware)

    @app.post("/upload")
    def upload(file: UploadFile = File(...)):
        return {"accepted": True}

    chunks = [
        b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="report.pdf"\r\nContent-Type: application/pdf\r\n\r\n',
        *([b"a" * (1024 * 1024)] * 4),
        b"\r\n--boundary--\r\n",
    ]
    try:
        status = streamed_request(app, b"multipart/form-data; boundary=boundary", chunks)
        assert opened and all(file.closed for file in opened)
        assert status == 413
    finally:
        for file in opened:
            file.close()
