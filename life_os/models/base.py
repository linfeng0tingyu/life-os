from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class TimestampMixin:
    created_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=now_iso
    )
    updated_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=now_iso, onupdate=now_iso
    )
