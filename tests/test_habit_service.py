from __future__ import annotations

import pytest

from life_os.extensions import db
from life_os.models import HabitLog
from life_os.services import HabitService, ValidationError


def test_habit_lifecycle_and_stable_order(app_context: None) -> None:
    later = HabitService.create("阅读", sort_order=20)
    earlier = HabitService.create("健身", sort_order=10)

    assert [habit.id for habit in HabitService.list_habits()] == [
        earlier.id,
        later.id,
    ]
    HabitService.update(earlier.id, active=False)
    assert [habit.id for habit in HabitService.list_habits()] == [later.id]
    assert len(HabitService.list_habits(include_inactive=True)) == 2
    HabitService.update(earlier.id, active=True)
    assert len(HabitService.list_habits()) == 2


def test_habit_log_upsert_does_not_duplicate(app_context: None) -> None:
    habit = HabitService.create("学习")
    first = HabitService.set_log(
        habit.id, "2026-09-18", status=True, value=60, value_unit="min"
    )
    second = HabitService.set_log(
        habit.id, "2026-09-18", status=False, value=30, value_unit="min"
    )

    assert first.id == second.id
    assert second.status is False
    assert second.value == 30
    assert db.session.query(HabitLog).count() == 1


def test_failed_habit_update_rolls_back_all_changes(app_context: None) -> None:
    habit = HabitService.create("钢琴")
    with pytest.raises(ValidationError):
        HabitService.update(habit.id, active=False, sort_order=True)

    db.session.expire_all()
    persisted = HabitService.list_habits(include_inactive=True)[0]
    assert persisted.active is True
    assert persisted.sort_order == 0
