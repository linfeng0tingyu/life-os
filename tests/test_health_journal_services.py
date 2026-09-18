from __future__ import annotations

import pytest

from life_os.extensions import db
from life_os.models import DailyHealth, Journal
from life_os.services import HealthService, JournalService, ValidationError


def test_health_upsert_and_cross_midnight_sleep(app_context: None) -> None:
    record = HealthService.upsert(
        "2026-09-18",
        weight_kg=72.4,
        sleep_start="2026-09-17T23:30:00+08:00",
        sleep_end="2026-09-18T07:10:00+08:00",
        sleep_quality=4,
        energy_level=4,
    )
    assert record.sleep_duration_minutes == 460
    assert record.sleep_duration_manual is False

    updated = HealthService.upsert(
        "2026-09-18", mood_level=5, sleep_duration_minutes=450
    )
    assert updated.id == record.id
    assert updated.sleep_duration_minutes == 450
    assert updated.sleep_duration_manual is True
    assert db.session.query(DailyHealth).count() == 1

    automatic = HealthService.upsert(
        "2026-09-18", sleep_duration_minutes=None
    )
    assert automatic.sleep_duration_minutes == 460
    assert automatic.sleep_duration_manual is False


def test_health_allows_partial_values_and_rejects_invalid_score(
    app_context: None,
) -> None:
    record = HealthService.upsert("2026-09-19", note="仅记录备注")
    assert record.weight_kg is None
    with pytest.raises(ValidationError):
        HealthService.upsert("2026-09-19", mood_level=6)
    db.session.expire_all()
    assert HealthService.get("2026-09-19").mood_level is None


def test_invalid_sleep_range_rolls_back(app_context: None) -> None:
    with pytest.raises(ValidationError, match="晚于开始时间"):
        HealthService.upsert(
            "2026-09-20",
            sleep_start="2026-09-20T08:00:00+08:00",
            sleep_end="2026-09-20T07:00:00+08:00",
        )
    assert HealthService.get("2026-09-20") is None


def test_journal_upsert_preserves_unicode_and_single_row(app_context: None) -> None:
    first = JournalService.upsert("2026-09-18", "# 日记\n第一版 🌱")
    second = JournalService.upsert("2026-09-18", "# 日记\n第二版")

    assert first.id == second.id
    assert JournalService.get("2026-09-18").content == "# 日记\n第二版"
    assert db.session.query(Journal).count() == 1
