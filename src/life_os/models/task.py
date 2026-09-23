from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_os.extensions import db

from .base import TimestampMixin


class Task(TimestampMixin, db.Model):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'doing', 'done', 'cancelled')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_tasks_priority",
        ),
        CheckConstraint("parent_id IS NULL OR parent_id != id", name="ck_tasks_parent"),
        Index(
            "ix_tasks_scheduled_status_archived",
            "scheduled_date",
            "status",
            "archived_at",
        ),
        Index(
            "ix_tasks_due_status_archived", "due_date", "status", "archived_at"
        ),
        Index("ix_tasks_status_archived", "status", "archived_at"),
        Index("ix_tasks_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="todo"
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal"
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    archived_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    parent: Mapped["Task | None"] = relationship(
        remote_side="Task.id", back_populates="children"
    )
    children: Mapped[list["Task"]] = relationship(back_populates="parent")
