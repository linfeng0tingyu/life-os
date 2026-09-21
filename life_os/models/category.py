from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from life_os.extensions import db

from .base import TimestampMixin


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('task', 'habit')",
            name="ck_categories_scope",
        ),
        UniqueConstraint("scope", "name", name="uq_categories_scope_name"),
        Index("ix_categories_scope_sort", "scope", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(
        String(100, collation="NOCASE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
