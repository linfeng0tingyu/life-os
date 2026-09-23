from __future__ import annotations

from datetime import date

from sqlalchemy import select

from life_os.extensions import db
from life_os.models import DailyHealth

from .common import (
    UNSET,
    ValidationError,
    integer_range,
    optional_float,
    optional_text,
    parse_aware_datetime,
    parse_life_date,
    transactional,
)


class HealthService:
    @staticmethod
    def get(value: date | str) -> DailyHealth | None:
        target = parse_life_date(value)
        return db.session.scalar(
            select(DailyHealth).where(DailyHealth.date == target)
        )

    @staticmethod
    @transactional
    def upsert(
        value: date | str,
        *,
        weight_kg: object = UNSET,
        sleep_start: object = UNSET,
        sleep_end: object = UNSET,
        sleep_duration_minutes: object = UNSET,
        sleep_quality: object = UNSET,
        energy_level: object = UNSET,
        mood_level: object = UNSET,
        body_status: object = UNSET,
        exercise_minutes: object = UNSET,
        note: object = UNSET,
    ) -> DailyHealth:
        target = parse_life_date(value)
        record = HealthService.get(target)
        if record is None:
            record = DailyHealth(date=target)
            db.session.add(record)

        if weight_kg is not UNSET:
            record.weight_kg = optional_float(weight_kg, "weight_kg", minimum=0.000001)
        if sleep_start is not UNSET:
            record.sleep_start = HealthService._normalize_datetime(
                sleep_start, "sleep_start"
            )
        if sleep_end is not UNSET:
            record.sleep_end = HealthService._normalize_datetime(sleep_end, "sleep_end")
        if sleep_quality is not UNSET:
            record.sleep_quality = HealthService._optional_rating(
                sleep_quality, "sleep_quality"
            )
        if energy_level is not UNSET:
            record.energy_level = HealthService._optional_rating(
                energy_level, "energy_level"
            )
        if mood_level is not UNSET:
            record.mood_level = HealthService._optional_rating(
                mood_level, "mood_level"
            )
        if body_status is not UNSET:
            record.body_status = optional_text(body_status, "body_status", 500)
        if exercise_minutes is not UNSET:
            record.exercise_minutes = HealthService._optional_integer(
                exercise_minutes, "exercise_minutes", 0, 1440
            )
        if note is not UNSET:
            record.note = optional_text(note, "note", 2000)

        if sleep_duration_minutes is not UNSET:
            record.sleep_duration_minutes = HealthService._optional_integer(
                sleep_duration_minutes, "sleep_duration_minutes", 0, 1440
            )
            record.sleep_duration_manual = sleep_duration_minutes is not None
            if sleep_duration_minutes is None:
                record.sleep_duration_minutes = HealthService._calculate_sleep_duration(
                    record.sleep_start, record.sleep_end
                )
        elif not record.sleep_duration_manual and (
            sleep_start is not UNSET or sleep_end is not UNSET
        ):
            record.sleep_duration_minutes = HealthService._calculate_sleep_duration(
                record.sleep_start, record.sleep_end
            )

        db.session.flush()
        return record

    @staticmethod
    def _normalize_datetime(value: object, field: str) -> str | None:
        if value is None:
            return None
        parsed = parse_aware_datetime(value, field)  # type: ignore[arg-type]
        return parsed.isoformat(timespec="minutes")

    @staticmethod
    def _optional_rating(value: object, field: str) -> int | None:
        if value is None:
            return None
        return integer_range(value, field, 1, 5)

    @staticmethod
    def _optional_integer(
        value: object, field: str, minimum: int, maximum: int
    ) -> int | None:
        if value is None:
            return None
        return integer_range(value, field, minimum, maximum)

    @staticmethod
    def _calculate_sleep_duration(
        start_value: str | None, end_value: str | None
    ) -> int | None:
        if start_value is None or end_value is None:
            return None
        start = parse_aware_datetime(start_value, "sleep_start")
        end = parse_aware_datetime(end_value, "sleep_end")
        minutes = int((end - start).total_seconds() // 60)
        if not 0 <= minutes <= 1440:
            raise ValidationError("睡眠结束时间必须晚于开始时间且间隔不超过 24 小时。")
        return minutes
