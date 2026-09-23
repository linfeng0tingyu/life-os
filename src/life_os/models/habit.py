from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_os.extensions import db

from .base import TimestampMixin


class Habit(TimestampMixin, db.Model):
    __tablename__ = "habits"
    __table_args__ = (
        Index("ix_habits_active_sort", "active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_habits_active"),
        nullable=False,
        default=True,
    )
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    logs: Mapped[list["HabitLog"]] = relationship(
        back_populates="habit", order_by="HabitLog.date"
    )


class HabitLog(TimestampMixin, db.Model):
    __tablename__ = "habit_logs"
    __table_args__ = (
        UniqueConstraint("habit_id", "date", name="uq_habit_logs_habit_date"),
        CheckConstraint("value IS NULL OR value >= 0", name="ck_habit_logs_value"),
        Index("ix_habit_logs_date", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    habit_id: Mapped[int] = mapped_column(
        ForeignKey("habits.id", ondelete="RESTRICT"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_habit_logs_status"),
        nullable=False,
        default=False,
    )
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    habit: Mapped[Habit] = relationship(back_populates="logs")
