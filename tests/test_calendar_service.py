from __future__ import annotations

from life_os.services import CalendarService, NotFoundError, ValidationError

import pytest


def test_calendar_infers_weekdays_and_weekends(app_context: None) -> None:
    monday = CalendarService.resolve("2026-09-21")
    saturday = CalendarService.resolve("2026-09-19")

    assert monday.day_type == "workday"
    assert monday.explicit is False
    assert saturday.day_type == "rest_day"
    assert saturday.explicit is False


def test_official_holiday_schedule_precedes_weekday_inference(
    app_context: None,
) -> None:
    spring_festival = CalendarService.resolve("2026-02-17")
    adjusted_workday = CalendarService.resolve("2026-02-14")

    assert spring_festival.day_type == "rest_day"
    assert spring_festival.holiday_name == "春节"
    assert spring_festival.source == "official"
    assert spring_festival.explicit is False
    assert adjusted_workday.day_type == "workday"
    assert adjusted_workday.custom_label == "调休上班"
    assert adjusted_workday.source == "official"


def test_manual_marker_overrides_and_can_reveal_official_schedule(
    app_context: None,
) -> None:
    CalendarService.set_day(
        "2026-10-01",
        day_type="workday",
        custom_label="临时值班",
    )
    manual = CalendarService.resolve("2026-10-01")
    assert manual.source == "manual"
    assert manual.day_type == "workday"

    CalendarService.clear_day("2026-10-01")
    restored = CalendarService.resolve("2026-10-01")
    assert restored.source == "official"
    assert restored.day_type == "rest_day"
    assert restored.holiday_name == "国庆节"


def test_explicit_rest_day_holiday_and_custom_label(app_context: None) -> None:
    record = CalendarService.set_day(
        "2026-10-01",
        day_type="rest_day",
        holiday_name="国庆节",
        custom_label="家庭聚会",
        note="自定义安排",
    )
    resolved = CalendarService.resolve("2026-10-01")

    assert resolved.explicit is True
    assert resolved.day_type == "rest_day"
    assert resolved.holiday_name == "国庆节"
    assert resolved.custom_label == "家庭聚会"
    assert record.source == "manual"


def test_weekend_can_be_overridden_as_adjusted_workday(app_context: None) -> None:
    CalendarService.set_day(
        "2026-09-19", day_type="workday", custom_label="调休上班"
    )
    resolved = CalendarService.resolve("2026-09-19")

    assert resolved.day_type == "workday"
    assert resolved.custom_label == "调休上班"


def test_setting_same_date_updates_single_record(app_context: None) -> None:
    first = CalendarService.set_day("2026-09-18", day_type="rest_day")
    second = CalendarService.set_day(
        "2026-09-18", day_type="workday", custom_label="临时工作"
    )

    assert second.id == first.id
    assert CalendarService.resolve("2026-09-18").day_type == "workday"


def test_setting_archived_date_revives_original_record(app_context: None) -> None:
    first = CalendarService.set_day("2026-09-21", day_type="rest_day")
    CalendarService.clear_day("2026-09-21")
    revived = CalendarService.set_day(
        "2026-09-21", day_type="workday", custom_label="恢复"
    )

    assert revived.id == first.id
    assert revived.archived_at is None
    assert CalendarService.resolve("2026-09-21").custom_label == "恢复"


def test_clear_day_archives_and_restores_inference(app_context: None) -> None:
    CalendarService.set_day("2026-09-21", day_type="rest_day")
    archived = CalendarService.clear_day("2026-09-21")
    resolved = CalendarService.resolve("2026-09-21")

    assert archived.archived_at is not None
    assert resolved.day_type == "workday"
    assert resolved.explicit is False
    with pytest.raises(NotFoundError):
        CalendarService.clear_day("2026-09-21")


def test_month_resolution_and_validation(app_context: None) -> None:
    days = CalendarService.list_month(2026, 2)
    assert len(days) == 28
    with pytest.raises(ValidationError):
        CalendarService.list_month(2026, 13)
    with pytest.raises(ValidationError):
        CalendarService.set_day("2026-09-18", day_type="holiday")
