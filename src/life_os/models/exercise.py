from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from life_os.extensions import db

from .base import TimestampMixin


class ExerciseType(TimestampMixin, db.Model):
    __tablename__ = "exercise_types"
    __table_args__ = (
        UniqueConstraint("name", name="uq_exercise_types_name"),
        Index("ix_exercise_types_sort", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100, collation="NOCASE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)


class DailyHealthExerciseType(TimestampMixin, db.Model):
    __tablename__ = "daily_health_exercise_types"
    __table_args__ = (
        UniqueConstraint(
            "daily_health_id",
            "exercise_type_id",
            name="uq_daily_health_exercise_type",
        ),
        Index(
            "ix_daily_health_exercise_types_health",
            "daily_health_id",
            "exercise_type_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_health_id: Mapped[int] = mapped_column(
        ForeignKey("daily_health.id", ondelete="CASCADE"), nullable=False
    )
    exercise_type_id: Mapped[int] = mapped_column(
        ForeignKey("exercise_types.id", ondelete="RESTRICT"), nullable=False
    )
