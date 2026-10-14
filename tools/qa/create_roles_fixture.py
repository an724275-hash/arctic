"""Create isolated, fictional accounts for the browser role workflow check."""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

root = Path(__file__).resolve().parents[2]
os.chdir(root / "backend")
sys.path.insert(0, str(root / "backend"))

from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Criterion, ExpertNomination, Nomination, TeacherLink, User, utcnow
from app.security import hash_password


def main():
    run_id = os.environ["ARCTIC_QA_RUN_ID"]
    password = os.environ["ARCTIC_QA_PASSWORD"]
    if not re.fullmatch(r"[0-9a-f-]{10,80}", run_id):
        raise ValueError("Invalid fixture run identifier")
    fixture_dir = root / ".runtime" / "roles-e2e" / run_id
    fixture_dir.mkdir(parents=True, exist_ok=True)
    users = {}
    with SessionLocal.begin() as db:
        criteria = list(db.scalars(select(Criterion).where(Criterion.is_active.is_(True))))
        nomination = db.scalar(select(Nomination).where(Nomination.is_active.is_(True)))
        if not criteria or not nomination:
            raise RuntimeError("The running app needs its normal criteria and nominations")
        for role in ("participant", "teacher", "expert", "commission", "admin"):
            user = User(
                email=f"qa-roles-{run_id}-{role}@example.com",
                hashed_password=hash_password(password),
                full_name=f"QA {role} {run_id[-6:]}",
                role=role,
                birth_date=date(2000, 1, 15),
                school="Fictional QA school",
                grade=11 if role == "participant" else None,
                region="Fictional browser test",
                consent_at=utcnow(),
                email_verified=True,
            )
            db.add(user)
            db.flush()
            users[role] = {"id": user.id, "email": user.email, "name": user.full_name}
        db.add(ExpertNomination(expert_id=users["expert"]["id"], nomination_id=nomination.id))
        db.add(TeacherLink(
            participant_id=users["participant"]["id"],
            teacher_id=users["teacher"]["id"],
            status="accepted",
        ))
    files = {}
    for kind in ("document", "presentation"):
        target = fixture_dir / f"qa-{kind}.pdf"
        pdf = canvas.Canvas(str(target))
        pdf.setTitle(f"Fictional QA {kind}")
        pdf.drawString(60, 760, "Arctic role workflow browser verification")
        pdf.drawString(60, 730, f"Fixture: {run_id}")
        pdf.drawString(60, 700, "A test attachment, not a real competition submission.")
        pdf.save()
        files[kind] = str(target)
    print(json.dumps({"users": users, "files": files, "nomination_id": nomination.id}))


if __name__ == "__main__":
    main()
