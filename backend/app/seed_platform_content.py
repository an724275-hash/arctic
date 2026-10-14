"""начальные публикации"""

import json
from pathlib import Path
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Content


def main():
    records = json.loads(Path(__file__).with_name("platform_content.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        for record in records:
            row = db.scalar(select(Content).where(Content.slug == record["slug"]))
            if row is not None:
                continue
            db.add(Content(**record))
        db.commit()
    print("Platform content imported; existing publications preserved.")


if __name__ == "__main__":
    main()
