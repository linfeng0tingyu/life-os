from __future__ import annotations

from datetime import date

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import Habit, HabitLog

from .common import (
    UNSET,
    NotFoundError,
    ValidationError,
    optional_float,
    optional_text,
    parse_life_date,
    required_text,
    transactional,
)


class HabitService:
    @staticmethod
    def list_habits(*, include_inactive: bool = False) -> list[Habit]:
        statement = select(Habit)
        if not include_inactive:
            statement = statement.where(Habit.active.is_(True))
        return list(
            db.session.scalars(statement.order_by(Habit.sort_order, Habit.id))
        )

    @staticmethod
    def get_log(habit_id: int, value_date: date | str) -> HabitLog | None:
        target = parse_life_date(value_date)
        return db.session.scalar(
            select(HabitLog).where(
                HabitLog.habit_id == habit_id, HabitLog.date == target
            )
        )

    @staticmethod
    @transactional
    def create(
        name: str,
        *,
        description: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        sort_order: int = 0,
    ) -> Habit:
        if isinstance(sort_order, bool) or not isinstance(sort_order, int):
            raise ValidationError("sort_order 必须是整数。")
        habit = Habit(
            name=required_text(name, "name", 200),
            description=optional_text(description, "description", 2000),
            icon=optional_text(icon, "icon", 100),
            category=optional_text(category, "category", 100),
            sort_order=sort_order,
            active=True,
        )
        db.session.add(habit)
        db.session.flush()
        return habit

    @staticmethod
    @transactional
    def update(
        habit_id: int,
        *,
        name: object = UNSET,
        description: object = UNSET,
        icon: object = UNSET,
        category: object = UNSET,
        active: object = UNSET,
        sort_order: object = UNSET,
    ) -> Habit:
        habit = db.session.get(Habit, habit_id)
        if habit is None:
            raise NotFoundError("习惯不存在。")
        if name is not UNSET:
            habit.name = required_text(name, "name", 200)
        if description is not UNSET:
            habit.description = optional_text(description, "description", 2000)
        if icon is not UNSET:
            habit.icon = optional_text(icon, "icon", 100)
        if category is not UNSET:
            habit.category = optional_text(category, "category", 100)
        if active is not UNSET:
            if not isinstance(active, bool):
                raise ValidationError("active 必须是布尔值。")
            habit.active = active
        if sort_order is not UNSET:
            if isinstance(sort_order, bool) or not isinstance(sort_order, int):
                raise ValidationError("sort_order 必须是整数。")
            habit.sort_order = sort_order
        db.session.flush()
        return habit

    @staticmethod
    @transactional
    def set_log(
        habit_id: int,
        value_date: date | str,
        *,
        status: bool,
        value: float | int | None = None,
        value_unit: str | None = None,
        note: str | None = None,
    ) -> HabitLog:
        habit = db.session.get(Habit, habit_id)
        if habit is None:
            raise NotFoundError("习惯不存在。")
        if not isinstance(status, bool):
            raise ValidationError("status 必须是布尔值。")
        target = parse_life_date(value_date)
        log = db.session.scalar(
            select(HabitLog).where(
                HabitLog.habit_id == habit_id, HabitLog.date == target
            )
        )
        if log is None:
            log = HabitLog(habit_id=habit_id, date=target)
            db.session.add(log)
        log.status = status
        log.value = optional_float(value, "value", minimum=0)
        log.value_unit = optional_text(value_unit, "value_unit", 50)
        log.note = optional_text(note, "note", 1000)
        db.session.flush()
        return log
