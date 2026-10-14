"""Project ownership, submission, and private, validated file storage."""

from __future__ import annotations

import os
import re
import tempfile
import uuid
import zipfile
import zlib
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlsplit
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.common import require_stage_open
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    Assignment,
    AuditLog,
    Nomination,
    Notification,
    Project,
    QuizAttempt,
    TeacherLink,
    Upload,
    User,
    utcnow,
)

router = APIRouter(tags=["projects"])


def require_qualified_participant(db: Session, user_id: str):
    passed = db.scalar(
        select(QuizAttempt.id)
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.passed.is_(True),
            QuizAttempt.submitted_at.is_not(None),
        )
        .limit(1)
    )
    if passed is None:
        raise HTTPException(409, "Второй этап доступен после прохождения теста с проходным результатом")


class ProjectWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=250)
    abstract: str = Field(min_length=10, max_length=20000)
    nomination_id: str
    video_url: str | None = Field(default=None, max_length=2048)

    @field_validator("title", "abstract", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, value):
        return clean_video_url(value)


def clean_video_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Ссылка на видео должна начинаться с https://")
        if any(ord(char) < 32 for char in value):
            raise ValueError("Недопустимая ссылка на видео")
        _ = parsed.port
    except (ValueError, AttributeError) as exc:
        raise ValueError("Укажите корректную HTTPS-ссылку на видео") from exc
    return value


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=250)
    abstract: str | None = Field(default=None, min_length=10, max_length=20000)
    nomination_id: str | None = None
    video_url: str | None = Field(default=None, max_length=2048)

    @field_validator("title", "abstract", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, value):
        return clean_video_url(value)


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    original_name: str
    media_type: str
    size_bytes: int
    kind: str
    created_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    nomination_id: str
    title: str
    abstract: str
    video_url: str | None
    status: str
    moderation_comment: str | None
    reviews_released: bool
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None


class ProjectDetail(ProjectOut):
    files: list[FileOut]
    nomination_title: str | None
    participant_name: str
    mentor_name: str | None = None


class ModerationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["admitted", "rejected"]
    comment: str = Field(default="", max_length=5000)


def project_for_access(db: Session, project_id: str, user: User, *, lock: bool = False) -> Project:
    stmt = select(Project).where(Project.id == project_id)
    if lock:
        stmt = stmt.with_for_update()
    project = db.scalar(stmt)
    if project is None:
        raise HTTPException(404, "Проект не найден")
    if user.role in ("admin", "commission") or project.user_id == user.id:
        return project
    if user.role == "teacher" and db.scalar(
        select(TeacherLink.id).where(
            TeacherLink.participant_id == project.user_id,
            TeacherLink.teacher_id == user.id,
            TeacherLink.status == "accepted",
        )
    ):
        return project
    if user.role == "expert" and db.scalar(
        select(Assignment.id).where(
            Assignment.project_id == project.id,
            Assignment.expert_id == user.id,
        )
    ):
        return project
    raise HTTPException(403, "Нет доступа к этому проекту")


def editable_project(db: Session, project_id: str, user: User) -> Project:
    project = project_for_access(db, project_id, user, lock=True)
    if project.user_id != user.id or user.role != "participant":
        raise HTTPException(403, "Редактировать проект может только его автор")
    if project.status != "draft":
        raise HTTPException(409, "Изменять можно только черновик проекта")
    return project


def active_nomination(db: Session, nomination_id: str) -> Nomination:
    nomination = db.get(Nomination, nomination_id)
    if nomination is None or not nomination.is_active:
        raise HTTPException(422, "Выберите действующую номинацию")
    return nomination


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    stmt = select(Project)
    if user.role == "participant":
        stmt = stmt.where(Project.user_id == user.id)
    elif user.role == "teacher":
        participants = select(TeacherLink.participant_id).where(
            TeacherLink.teacher_id == user.id,
            TeacherLink.status == "accepted",
        )
        stmt = stmt.where(Project.user_id.in_(participants))
    elif user.role == "expert":
        assigned = select(Assignment.project_id).where(Assignment.expert_id == user.id)
        stmt = stmt.where(Project.id.in_(assigned))
    elif user.role not in ("admin", "commission"):
        raise HTTPException(403, "Недостаточно прав")
    return list(db.scalars(stmt.order_by(Project.created_at.desc(), Project.id).offset(offset).limit(limit)))


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("participant")),
):
    require_qualified_participant(db, user.id)
    active_nomination(db, payload.nomination_id)
    project = Project(user_id=user.id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = project_for_access(db, project_id, user)
    participant = db.get(User, project.user_id)
    nomination = db.get(Nomination, project.nomination_id)
    mentor = db.scalar(
        select(User.full_name)
        .join(TeacherLink, TeacherLink.teacher_id == User.id)
        .where(TeacherLink.participant_id == project.user_id, TeacherLink.status == "accepted")
    )
    return ProjectDetail(
        **ProjectOut.model_validate(project).model_dump(),
        files=[
            FileOut.model_validate(item)
            for item in db.scalars(
                select(Upload).where(Upload.project_id == project.id).order_by(Upload.created_at)
            )
        ],
        nomination_title=nomination.title if nomination else None,
        participant_name=participant.full_name if participant else "Участник",
        mentor_name=mentor,
    )


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: str,
    payload: ProjectPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = editable_project(db, project_id, user)
    updates = payload.model_dump(exclude_unset=True)
    for key in ("title", "abstract", "nomination_id"):
        if key in updates and updates[key] is None:
            raise HTTPException(422, f"Поле {key} не может быть пустым")
    if "nomination_id" in updates:
        active_nomination(db, updates["nomination_id"])
    for key, value in updates.items():
        setattr(project, key, value)
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.post("/projects/{project_id}/submit", response_model=ProjectOut)
def submit_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = editable_project(db, project_id, user)
    require_qualified_participant(db, project.user_id)
    require_stage_open(db, "projects")
    active_nomination(db, project.nomination_id)
    if not project.title.strip() or len(project.abstract.strip()) < 10:
        raise HTTPException(422, "Заполните название и аннотацию проекта")
    document = db.scalar(select(Upload.id).where(Upload.project_id == project.id, Upload.kind == "document"))
    if document is None:
        raise HTTPException(422, "Перед подачей загрузите основной документ PDF или DOCX")
    project.status = "submitted"
    project.submitted_at = utcnow()
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.post("/projects/{project_id}/reopen", response_model=ProjectOut)
def reopen_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = project_for_access(db, project_id, user, lock=True)
    if user.role != "participant" or project.user_id != user.id:
        raise HTTPException(403, "Вернуть проект в черновик может только автор")
    if project.status != "rejected":
        raise HTTPException(409, "В черновик можно вернуть только отклонённый проект")
    project.status = "draft"
    project.submitted_at = None
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.post("/admin/projects/{project_id}/moderate", response_model=ProjectOut)
def moderate_project(
    project_id: str,
    payload: ModerationWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    project = project_for_access(db, project_id, user, lock=True)
    if project.status != "submitted":
        raise HTTPException(409, "Модерация доступна только для поданных проектов")
    if payload.status == "rejected" and len(payload.comment.strip()) < 5:
        raise HTTPException(422, "Укажите причину отклонения проекта")
    project.status = payload.status
    project.moderation_comment = payload.comment.strip() or None
    project.updated_at = utcnow()
    title = "Проект допущен к экспертизе" if payload.status == "admitted" else "Проект требует доработки"
    db.add(
        Notification(
            user_id=project.user_id, title=title, body=f"«{project.title}». {payload.comment.strip()}".strip()
        )
    )
    db.add(
        AuditLog(
            actor_id=user.id,
            action="project.moderate",
            entity_id=project.id,
            details={"status": payload.status, "comment": payload.comment.strip()},
        )
    )
    db.commit()
    db.refresh(project)
    return project


def storage_path(stored_name: str) -> Path:
    root = Path(settings.uploads_dir).resolve()
    path = (root / stored_name).resolve()
    if path.parent != root:
        raise HTTPException(404, "Файл не найден")
    return path


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = editable_project(db, project_id, user)
    uploaded = list(db.scalars(select(Upload).where(Upload.project_id == project.id)))
    paths = [storage_path(item.stored_name) for item in uploaded]
    db.execute(delete(Upload).where(Upload.project_id == project.id))
    db.delete(project)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)


MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}
EXTENSIONS = {"document": {".pdf", ".docx"}, "presentation": {".pdf", ".pptx"}, "video": {".mp4", ".webm"}}


def safe_filename(filename: str | None) -> str:
    name = re.split(r"[/\\]", filename or "")[-1]
    name = "".join(char for char in name if ord(char) >= 32 and ord(char) != 127)
    name = name.strip(" .")
    if not name or len(name) > 240:
        raise HTTPException(422, "Некорректное имя файла")
    return name


def validate_file_content(path: Path, extension: str, limit: int) -> None:
    with path.open("rb") as stream:
        header = stream.read(64)
        stream.seek(max(0, path.stat().st_size - 2048))
        tail = stream.read(2048)
    valid = False
    if extension == ".pdf":
        valid = bool(re.match(rb"%PDF-[12]\.\d", header)) and b"%%EOF" in tail
    elif extension == ".mp4":
        box_size = int.from_bytes(header[:4], "big")
        valid = len(header) >= 16 and header[4:8] == b"ftyp" and 16 <= box_size <= path.stat().st_size
    elif extension == ".webm":
        with path.open("rb") as stream:
            ebml = stream.read(4096)
        valid = header.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in ebml.lower()
    elif extension in (".docx", ".pptx"):
        if not header.startswith(b"PK\x03\x04"):
            raise HTTPException(422, "Содержимое файла не соответствует расширению")
        required = "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
        forbidden = {".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".scr", ".lnk", ".msi"}
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if len(members) > 5000 or sum(info.file_size for info in members) > min(
                    limit * 20, 512 * 1024 * 1024
                ):
                    raise HTTPException(422, "Архив Office превышает допустимый размер")
                names = {info.filename for info in members}
                for info in members:
                    member = PurePosixPath(info.filename.replace("\\", "/"))
                    if member.is_absolute() or ".." in member.parts or info.flag_bits & 1:
                        raise HTTPException(422, "Небезопасная структура документа Office")
                    if member.suffix.lower() in forbidden or "vbaproject" in info.filename.lower():
                        raise HTTPException(422, "Исполняемые вложения и макросы запрещены")
                if required not in names or "[Content_Types].xml" not in names or "_rels/.rels" not in names:
                    raise HTTPException(422, "Некорректный документ Office")
                for member in ("[Content_Types].xml", required):
                    if archive.getinfo(member).file_size > 16 * 1024 * 1024:
                        raise HTTPException(422, "Структура документа слишком велика")
                    content = archive.read(member)
                    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                        raise HTTPException(422, "Небезопасная структура XML")
                    root = ElementTree.fromstring(content)
                    if member == required:
                        namespaces = (
                            (
                                "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                                "http://purl.oclc.org/ooxml/wordprocessingml/main",
                            )
                            if extension == ".docx"
                            else (
                                "http://schemas.openxmlformats.org/presentationml/2006/main",
                                "http://purl.oclc.org/ooxml/presentationml/main",
                            )
                        )
                        tag = "document" if extension == ".docx" else "presentation"
                        if root.tag not in {f"{{{namespace}}}{tag}" for namespace in namespaces}:
                            raise HTTPException(422, "Содержимое Office не соответствует расширению")
                valid = True
        except (
            zipfile.BadZipFile,
            KeyError,
            ElementTree.ParseError,
            RuntimeError,
            NotImplementedError,
            ValueError,
            OSError,
            EOFError,
            zlib.error,
        ) as exc:
            raise HTTPException(422, "Некорректный документ Office") from exc
    if not valid:
        raise HTTPException(422, "Содержимое файла не соответствует расширению")


@router.get("/projects/{project_id}/files", response_model=list[FileOut])
def list_files(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project_for_access(db, project_id, user)
    return list(db.scalars(select(Upload).where(Upload.project_id == project_id).order_by(Upload.created_at)))


@router.post("/projects/{project_id}/files", response_model=FileOut, status_code=201)
def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    kind: Literal["document", "presentation", "video"] = Form("document"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = editable_project(db, project_id, user)
    original_name = safe_filename(file.filename)
    extension = Path(original_name).suffix.lower()
    if extension not in EXTENSIONS[kind]:
        raise HTTPException(422, "Для этой категории выбран неподдерживаемый формат файла")
    root = Path(settings.uploads_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    limit = settings.max_upload_mb * 1024 * 1024
    temporary: Path | None = None
    destination: Path | None = None
    committed = False
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".upload-", delete=False) as output:
            temporary = Path(output.name)
            size = 0
            while True:
                chunk = file.file.read(min(1024 * 1024, limit - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"Размер файла не должен превышать {settings.max_upload_mb} МБ")
                output.write(chunk)
        if size == 0:
            raise HTTPException(422, "Нельзя загрузить пустой файл")
        validate_file_content(temporary, extension, limit)
        stored_name = uuid.uuid4().hex + extension
        destination = storage_path(stored_name)
        os.replace(temporary, destination)
        upload = Upload(
            project_id=project.id,
            uploaded_by=user.id,
            original_name=original_name,
            stored_name=stored_name,
            media_type=MIME_TYPES[extension],
            size_bytes=size,
            kind=kind,
        )
        project.updated_at = utcnow()
        db.add(upload)
        db.commit()
        committed = True
        db.refresh(upload)
        return upload
    except Exception:
        db.rollback()
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if destination is not None and not committed:
            destination.unlink(missing_ok=True)


@router.delete("/projects/{project_id}/files/{file_id}", status_code=204)
def delete_file(
    project_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = editable_project(db, project_id, user)
    upload = db.get(Upload, file_id)
    if upload is None or upload.project_id != project.id:
        raise HTTPException(404, "Файл не найден")
    path = storage_path(upload.stored_name)
    db.delete(upload)
    project.updated_at = utcnow()
    db.commit()
    path.unlink(missing_ok=True)


@router.get("/files/{file_id}/download")
def download_file(file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    upload = db.get(Upload, file_id)
    if upload is None:
        raise HTTPException(404, "Файл не найден")
    project_for_access(db, upload.project_id, user)
    path = storage_path(upload.stored_name)
    if not path.is_file():
        raise HTTPException(404, "Файл отсутствует в хранилище")
    return FileResponse(
        path,
        media_type=upload.media_type,
        filename=safe_filename(upload.original_name),
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
