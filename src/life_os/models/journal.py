from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from life_os.extensions import db

from .base import TimestampMixin


class Journal(TimestampMixin, db.Model):
    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
