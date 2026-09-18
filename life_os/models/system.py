from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from life_os.extensions import db

from .base import now_iso


class SchemaMeta(db.Model):
    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=now_iso, onupdate=now_iso
    )
