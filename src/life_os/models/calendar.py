from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from life_os.extensions import db

from .base import TimestampMixin


class CalendarDay(TimestampMixin, db.Model):
    __tablename__ = "calendar_days"
    __table_args__ = (
        CheckConstraint(
            "day_type IN ('workday', 'rest_day')",
            name="ck_calendar_days_day_type",
        ),
        CheckConstraint(
            "source IN ('manual', 'imported')",
            name="ck_calendar_days_source",
        ),
        Index("ix_calendar_days_active_date", "archived_at", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    day_type: Mapped[str] = mapped_column(String(20), nullable=False)
    holiday_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    custom_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
    archived_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
