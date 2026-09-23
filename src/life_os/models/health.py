from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from life_os.extensions import db

from .base import TimestampMixin


class DailyHealth(TimestampMixin, db.Model):
    __tablename__ = "daily_health"
    __table_args__ = (
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="ck_health_weight"),
        CheckConstraint(
            "sleep_duration_minutes IS NULL OR "
            "(sleep_duration_minutes >= 0 AND sleep_duration_minutes <= 1440)",
            name="ck_health_sleep_duration",
        ),
        CheckConstraint(
            "sleep_quality IS NULL OR sleep_quality BETWEEN 1 AND 5",
            name="ck_health_sleep_quality",
        ),
        CheckConstraint(
            "energy_level IS NULL OR energy_level BETWEEN 1 AND 5",
            name="ck_health_energy",
        ),
        CheckConstraint(
            "mood_level IS NULL OR mood_level BETWEEN 1 AND 5",
            name="ck_health_mood",
        ),
        CheckConstraint(
            "exercise_minutes IS NULL OR exercise_minutes >= 0",
            name="ck_health_exercise",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_start: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sleep_end: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sleep_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    sleep_duration_manual: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_health_sleep_manual"),
        nullable=False,
        default=False,
    )
    sleep_quality: Mapped[int | None] = mapped_column(nullable=True)
    energy_level: Mapped[int | None] = mapped_column(nullable=True)
    mood_level: Mapped[int | None] = mapped_column(nullable=True)
    body_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exercise_minutes: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
