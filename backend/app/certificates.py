"""Private certificate downloads and privacy-preserving public verification."""

from __future__ import annotations

import hashlib
import io
import secrets
import threading
from pathlib import Path
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user
from app.models import Certificate, QuizAttempt, User, utcnow

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
    """Generate a one-page PDF with embedded Unicode font and verification QR."""
    font = _certificate_font()
    output = io.BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(width, height), pageCompression=1)
    pdf.setTitle(f"Сертификат {certificate.number}")
    pdf.setAuthor("Удивительная и неизведанная Арктика")
    pdf.setFillColor(HexColor("#E9F0F3"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.rect(24, 24, width - 48, height - 48, fill=1, stroke=0)
    pdf.setStrokeColor(HexColor("#345F73"))
    pdf.setLineWidth(1.2)
    pdf.rect(38, 38, width - 76, height - 76, fill=0, stroke=1)
    # Северный силуэт остаётся лёгким при печати на обычной бумаге.
    pdf.setFillColor(HexColor("#E9F0F3"))
    ridge = pdf.beginPath()
    ridge.moveTo(39, 39)
    for x, y in [(39, 66), (110, 93), (162, 68), (234, 114), (299, 76), (376, 99), (462, 60), (width - 39, 52), (width - 39, 39)]:
        ridge.lineTo(x, y)
    ridge.close()
    pdf.drawPath(ridge, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#345F73"))
    pdf.setFont(font, 12)
    pdf.drawCentredString(width / 2, 511, "УДИВИТЕЛЬНАЯ И НЕИЗВЕДАННАЯ АРКТИКА")
    pdf.setFillColor(HexColor("#1D343D"))
    layouts = {
        "test_passed": (
            "СЕРТИФИКАТ",
            "об успешном прохождении тестирования",
            "Настоящим подтверждается, что",
            "успешно прошёл(прошла) тестирование",
        ),
        "test_participation": (
            "СЕРТИФИКАТ",
            "участника тестирования",
            "Настоящим подтверждается, что",
            "принял(а) участие в тестировании",
        ),
        "diploma": (
            "ДИПЛОМ",
            "за достижения в конкурсе",
            "Награждается",
            "За достижения в исследовательском конкурсе",
        ),
        "teacher_thanks": (
            "БЛАГОДАРНОСТЬ",
            "наставнику участников конкурса",
            "Настоящей благодарностью отмечается",
            "За подготовку и поддержку участников конкурса",
        ),
    }
    heading, subtitle, introduction, description = layouts.get(
        certificate.kind,
        ("СЕРТИФИКАТ", "участника конкурса", "Настоящим сертификатом отмечается", "За участие в конкурсе"),
    )
    mascot = Path(__file__).with_name('assets') / 'arctic-bear.png'
    if mascot.is_file():
        pdf.drawImage(str(mascot), 54, 382, width=130, height=130, mask='auto')
    pdf.setFont(font, 34 if certificate.kind == "teacher_thanks" else 39)
    pdf.drawCentredString(width / 2, 448, heading)
    pdf.setFont(font, 15)
    pdf.drawCentredString(width / 2, 414, subtitle)
    pdf.setFillColor(HexColor("#58717E"))
    pdf.setFont(font, 11)
    pdf.drawCentredString(width / 2, 367, introduction)
    pdf.setFillColor(HexColor("#1D343D"))
    _fit_centered(pdf, user.full_name, font, width / 2, 333, 660, 74, 27)
    pdf.setFillColor(HexColor("#58717E"))
    pdf.setFont(font, 12)
    pdf.drawCentredString(width / 2, 253, description)
    pdf.setFillColor(HexColor("#1D343D"))
    _fit_centered(pdf, certificate.title, font, width / 2, 224, 660, 54, 18)
    pdf.setFont(font, 10)
    pdf.drawString(78, 139, f"Номер: {certificate.number}")
    pdf.drawString(78, 116, f"Дата выдачи: {certificate.issued_at:%d.%m.%Y}")
    pdf.setFillColor(HexColor("#58717E"))
    pdf.setFont(font, 9)
    pdf.drawString(78, 80, "Подлинность сертификата подтверждается по QR-коду.")
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=4)
    qr.add_data(verification_url(certificate))
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    png = io.BytesIO()
    qr_image.save(png, format="PNG")
    png.seek(0)
    pdf.drawImage(ImageReader(png), width - 184, 71, width=106, height=106)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


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
