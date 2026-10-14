"""Private certificate downloads and privacy-preserving public verification."""

from __future__ import annotations

import hashlib
import secrets
import threading
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.certificate_design import render_document
from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Certificate, QuizAttempt, TeacherLink, User, utcnow

router = APIRouter(prefix="/certificates", tags=["certificates"])
_font_lock = threading.Lock()


def verification_url(certificate: Certificate) -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/v1/certificates/verify/{certificate.public_token}"


def certificate_response(certificate: Certificate) -> dict:
    return {
        "id": str(certificate.id),
        "number": certificate.number,
        "kind": certificate.kind,
        "title": certificate.title,
        "attempt_id": str(certificate.attempt_id) if certificate.attempt_id else None,
        "issued_at": certificate.issued_at,
        "download_url": f"/api/v1/certificates/{certificate.id}/download",
        "verification_url": verification_url(certificate),
    }


def issue_quiz_certificate(db: Session, attempt: QuizAttempt) -> Certificate:
    """Called while the participant row is locked; the attempt FK is also unique.

    A submitted attempt earns participation; passing earns a success certificate.
    These are distinct kinds and participation must never imply passing.
    """
    existing = db.scalar(select(Certificate).where(Certificate.attempt_id == attempt.id))
    if existing:
        return existing
    if attempt.submitted_at is None:
        raise ValueError("An unfinished attempt cannot receive a certificate")
    issued_at = utcnow()
    certificate = Certificate(
        number=f"ARC-{issued_at.year}-{secrets.token_hex(6).upper()}",
        user_id=attempt.user_id,
        attempt_id=attempt.id,
        kind="test_passed" if attempt.passed else "test_participation",
        title=attempt.config_snapshot.get("title", "Удивительная и неизведанная Арктика"),
        issued_at=issued_at,
        public_token=secrets.token_urlsafe(32),
        mentor_name=db.scalar(
            select(User.full_name)
            .join(TeacherLink, TeacherLink.teacher_id == User.id)
            .where(TeacherLink.participant_id == attempt.user_id, TeacherLink.status == "accepted")
        ),
    )
    db.add(certificate)
    db.flush()
    return certificate


def _masked_name(full_name: str) -> str:
    return " ".join(f"{part[0]}***" for part in full_name.split()[:3]) or "Участник"


def _certificate_font() -> str:
    configured = getattr(settings, "certificate_font_path", None)
    candidates = [Path(configured)] if configured else []
    candidates += [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    font_path = next((path for path in candidates if path.is_file()), None)
    if font_path is None:
        raise HTTPException(
            status_code=503,
            detail="Не найден кириллический шрифт. Укажите CERTIFICATE_FONT_PATH.",
        )
    font_name = "Certificate-" + hashlib.sha256(str(font_path).encode()).hexdigest()[:12]
    with _font_lock:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    return font_name


def _wrapped_lines(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Wrap long names/titles, including a single unusually long word."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        for char in word:
            if current and pdfmetrics.stringWidth(current + char, font, size) > max_width:
                lines.append(current)
                current = char
            else:
                current += char
    if current:
        lines.append(current)
    return lines or [""]


def _fit_centered(
    pdf: canvas.Canvas,
    text: str,
    font: str,
    x: float,
    top: float,
    width: float,
    height: float,
    size: float,
) -> None:
    lines = _wrapped_lines(text, font, size, width)
    while len(lines) * size * 1.35 > height and size > 7:
        size -= 0.5
        lines = _wrapped_lines(text, font, size, width)
    pdf.setFont(font, size)
    for index, line in enumerate(lines):
        pdf.drawCentredString(x, top - index * size * 1.35, line)


def build_certificate_pdf(certificate: Certificate, user: User) -> bytes:
    return render_document(
        certificate, user, _certificate_font(), verification_url(certificate), _fit_centered
    )


@router.get("")
def list_certificates(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.user_id == user.id)
        .order_by(Certificate.issued_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [certificate_response(certificate) for certificate in certificates]


@router.get("/verify/{token}")
def verify_certificate(token: str, db: Session = Depends(get_db)) -> dict:
    if len(token) > 128:
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    certificate = db.scalar(select(Certificate).where(Certificate.public_token == token))
    if certificate is None:
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    owner = db.get(User, certificate.user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    return {
        "valid": True,
        "number": certificate.number,
        "kind": certificate.kind,
        "title": certificate.title,
        "issued_at": certificate.issued_at,
        "recipient": _masked_name(owner.full_name),
    }


@router.get("/{certificate_id}/download")
def download_certificate(
    certificate_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    certificate = db.get(Certificate, str(certificate_id))
    if certificate is None or (certificate.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    owner = db.get(User, certificate.user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    return Response(
        content=build_certificate_pdf(certificate, owner),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificate-{certificate.number}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
