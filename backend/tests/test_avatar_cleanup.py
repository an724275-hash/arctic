import asyncio
import io

import pytest
from fastapi import UploadFile
from PIL import Image

from app.avatars import upload_avatar
from app.config import settings
from app.models import User


def image_bytes():
    data = io.BytesIO()
    Image.new("RGB", (24, 24), "blue").save(data, "PNG")
    return data.getvalue()


def upload(client, headers):
    response = client.put(
        "/api/v1/users/me/avatar",
        headers=headers,
        files={"file": ("photo.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 200


def test_replacing_avatar_removes_only_previous_photo(client, db, users, auth_headers):
    headers = auth_headers("participant")
    upload(client, headers)
    old_name = users["participant"].avatar_filename
    upload(client, auth_headers("participant2"))
    other_name = users["participant2"].avatar_filename
    upload(client, headers)
    folder = settings.uploads_dir / "avatars"
    assert not (folder / old_name).exists()
    assert (folder / other_name).is_file()
    assert (folder / users["participant"].avatar_filename).is_file()
    assert len(list(folder.glob("*.webp"))) == 2


def test_rejected_avatar_keeps_current_photo(client, users, auth_headers):
    headers = auth_headers("participant")
    upload(client, headers)
    old_name = users["participant"].avatar_filename
    response = client.put(
        "/api/v1/users/me/avatar", headers=headers, files={"file": ("bad.png", b"invalid", "image/png")}
    )
    assert response.status_code == 422
    assert users["participant"].avatar_filename == old_name
    assert (settings.uploads_dir / "avatars" / old_name).is_file()


def test_avatar_commit_failure_keeps_old_file_and_removes_new(client, db, users, auth_headers, monkeypatch):
    upload(client, auth_headers("participant"))
    user = users["participant"]
    user_id, old_name = user.id, user.avatar_filename

    def fail_commit():
        raise RuntimeError("test commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="test commit failure"):
        asyncio.run(upload_avatar(UploadFile(io.BytesIO(image_bytes()), filename="photo.png"), db, user))
    assert db.get(User, user_id).avatar_filename == old_name
    assert [path.name for path in (settings.uploads_dir / "avatars").glob("*.webp")] == [old_name]


def test_anonymizing_account_clears_city_and_photo(client, db, users, auth_headers):
    user = users["participant"]
    user.city = "Нерюнгри"
    db.commit()
    upload(client, auth_headers("participant"))
    old_name = user.avatar_filename
    response = client.delete(f"/api/v1/admin/users/{user.id}", headers=auth_headers("admin"))
    assert response.status_code == 200
    db.refresh(user)
    assert user.city is None
    assert user.avatar_filename is None
    assert user.avatar_kind == "bear"
    assert not (settings.uploads_dir / "avatars" / old_name).exists()
