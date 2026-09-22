from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import CalendarDay
from life_os.models.base import now_iso

from .common import (
    NotFoundError,
    ValidationError,
    choice,
    optional_text,
    parse_life_date,
    transactional,
)
from .statutory_holidays import get_statutory_holiday


DAY_TYPES = {"workday", "rest_day"}
SOURCES = {"manual", "imported"}


@dataclass(frozen=True, slots=True)
class ResolvedCalendarDay:
    date: date
    day_type: str
    holiday_name: str | None
    custom_label: str | None
    note: str | None
    source: str
    explicit: bool


class CalendarService:
    @staticmethod
    def get_explicit(value: date | str) -> CalendarDay | None:
        target = parse_life_date(value)
        return db.session.scalar(
            select(CalendarDay).where(
                CalendarDay.date == target,
                CalendarDay.archived_at.is_(None),
            )
        )

    @staticmethod
    def resolve(value: date | str) -> ResolvedCalendarDay:
        target = parse_life_date(value)
        explicit = CalendarService.get_explicit(target)
        return CalendarService._resolve_record(target, explicit)

    @staticmethod
    def list_month(year: int, month: int) -> list[ResolvedCalendarDay]:
        if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
            raise ValidationError("year 必须是 1–9999 的整数。")
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
            raise ValidationError("month 必须是 1–12 的整数。")
        day_count = calendar.monthrange(year, month)[1]
        first_day = date(year, month, 1)
        last_day = date(year, month, day_count)
        explicit_records = {
            record.date: record
            for record in db.session.scalars(
                select(CalendarDay).where(
                    CalendarDay.date.between(first_day, last_day),
                    CalendarDay.archived_at.is_(None),
                )
            )
        }
        return [
            CalendarService._resolve_record(
                date(year, month, day_number),
                explicit_records.get(date(year, month, day_number)),
            )
            for day_number in range(1, day_count + 1)
        ]

    @staticmethod
    @transactional
    def set_day(
        value: date | str,
        *,
        day_type: str,
        holiday_name: str | None = None,
        custom_label: str | None = None,
        note: str | None = None,
        source: str = "manual",
    ) -> CalendarDay:
        target = parse_life_date(value)
        normalized_type = choice(day_type, "day_type", DAY_TYPES)
        normalized_source = choice(source, "source", SOURCES)
        record = db.session.scalar(
            select(CalendarDay).where(CalendarDay.date == target)
        )
        if record is None:
            record = CalendarDay(date=target, day_type=normalized_type)
            db.session.add(record)
        record.day_type = normalized_type
        record.holiday_name = optional_text(holiday_name, "holiday_name", 120)
        record.custom_label = optional_text(custom_label, "custom_label", 120)
        record.note = optional_text(note, "note", 1000)
        record.source = normalized_source
        record.archived_at = None
        db.session.flush()
        return record

    @staticmethod
    @transactional
    def clear_day(value: date | str) -> CalendarDay:
        record = CalendarService.get_explicit(value)
        if record is None:
            raise NotFoundError("该日期没有可清除的显式标记。")
        record.archived_at = now_iso()
        db.session.flush()
        return record

    @staticmethod
    def _resolve_record(
        target: date, explicit: CalendarDay | None
    ) -> ResolvedCalendarDay:
        if explicit is not None:
            return ResolvedCalendarDay(
                date=target,
                day_type=explicit.day_type,
                holiday_name=explicit.holiday_name,
                custom_label=explicit.custom_label,
                note=explicit.note,
                source=explicit.source,
                explicit=True,
            )
        official = get_statutory_holiday(target)
        if official is not None:
            return ResolvedCalendarDay(
                date=target,
                day_type=official.day_type,
                holiday_name=official.holiday_name,
                custom_label=official.custom_label,
                note=official.notice,
                source="official",
                explicit=False,
            )
        inferred_type = "workday" if target.weekday() < 5 else "rest_day"
        return ResolvedCalendarDay(
            date=target,
            day_type=inferred_type,
            holiday_name=None,
            custom_label=None,
            note=None,
            source="inferred",
            explicit=False,
        )
