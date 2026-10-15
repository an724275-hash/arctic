from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import common
from app.models import Stage


@pytest.mark.parametrize(
    "offset,enabled,status,open_now",
    [(-1, True, "upcoming", False), (0, True, "active", True), (59, True, "active", True), (60, True, "completed", False), (1, False, "disabled", False)],
)
def test_stage_status_and_access_share_date_boundaries(db, users, monkeypatch, offset, enabled, status, open_now):
    start = datetime(2030, 1, 15, 0, 0, tzinfo=timezone.utc)
    stage = db.scalar(select(Stage).where(Stage.slug == "testing"))
    stage.starts_at = start
    stage.ends_at = start + timedelta(seconds=60)
    stage.is_enabled = enabled
    db.commit()
    monkeypatch.setattr(common, "utcnow", lambda: start + timedelta(seconds=offset))
    assert common.stage_state(stage) == status
    if open_now:
        common.require_stage_open(db, "testing")
    else:
        with pytest.raises(HTTPException) as error:
            common.require_stage_open(db, "testing")
        assert error.value.status_code == 409
