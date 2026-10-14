import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Outbox, utcnow

logger = logging.getLogger("arctic.mail")


def deliver_batch() -> int:
    if not settings.enable_email_delivery or not settings.smtp_host:
        return 0
    delivered = 0
    with SessionLocal() as db:
        rows = db.scalars(
            select(Outbox)
            .where(Outbox.status == "pending", Outbox.attempts < 5)
            .order_by(Outbox.created_at)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.attempts += 1
            message = EmailMessage()
            message["From"] = settings.smtp_from
            message["To"] = row.recipient
            message["Subject"] = row.subject
            message["Message-ID"] = f"<{row.id}@arctic-outbox>"
            message.set_content(row.body)
            try:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                    if settings.smtp_starttls:
                        smtp.starttls(context=ssl.create_default_context())
                    if settings.smtp_user:
                        smtp.login(settings.smtp_user, settings.smtp_password)
                    smtp.send_message(message)
                row.status = "sent"
                row.sent_at = utcnow()
                row.last_error = None
                delivered += 1
            except (OSError, smtplib.SMTPException) as exc:
                row.last_error = type(exc).__name__
                if row.attempts >= 5:
                    row.status = "failed"
                logger.warning("Mail job %s failed: %s", row.id, type(exc).__name__)
        db.commit()
    return delivered


def main():
    logging.basicConfig(level=logging.INFO)
    if not settings.enable_email_delivery or not settings.smtp_host:
        raise SystemExit("Email delivery disabled. Configure SMTP and ENABLE_EMAIL_DELIVERY=true.")
    while True:
        try:
            deliver_batch()
        except Exception as exc:
            logger.error("Mail worker failed: %s", type(exc).__name__)
        time.sleep(15)


if __name__ == "__main__":
    main()
