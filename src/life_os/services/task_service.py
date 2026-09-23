from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select

from life_os.extensions import db
from life_os.models import Task
from life_os.models.base import now_iso

from .common import (
    UNSET,
    NotFoundError,
    ValidationError,
    choice,
    optional_text,
    parse_life_date,
    required_text,
    transactional,
)
from .category_service import CategoryService


TASK_STATUSES = {"todo", "doing", "done", "cancelled"}
TASK_PRIORITIES = {"low", "normal", "high", "urgent"}


class TaskService:
    @staticmethod
    def list_tasks(
        *,
        include_archived: bool = False,
        status: str | None = None,
        value_date: date | str | None = None,
    ) -> list[Task]:
        statement = select(Task)
        if not include_archived:
            statement = statement.where(Task.archived_at.is_(None))
        if status is not None:
            statement = statement.where(
                Task.status == choice(status, "status", TASK_STATUSES)
            )
        if value_date is not None:
            target = parse_life_date(value_date)
            statement = statement.where(
                or_(
                    Task.scheduled_date == target,
                    Task.due_date == target,
                    and_(
                        Task.due_date < target,
                        Task.status.not_in({"done", "cancelled"}),
                    ),
                )
            )
        return list(
            db.session.scalars(statement.order_by(Task.sort_order, Task.id))
        )

    @staticmethod
    @transactional
    def create(
        title: str,
        *,
        description: str | None = None,
        status: str = "todo",
        priority: str = "normal",
        category: str | None = None,
        scheduled_date: date | str | None = None,
        due_date: date | str | None = None,
        sort_order: int = 0,
        parent_id: int | None = None,
    ) -> Task:
        if isinstance(sort_order, bool) or not isinstance(sort_order, int):
            raise ValidationError("sort_order 必须是整数。")
        normalized_status = choice(status, "status", TASK_STATUSES)
        task = Task(
            title=required_text(title, "title", 300),
            description=optional_text(description, "description", 5000),
            status=normalized_status,
            priority=choice(priority, "priority", TASK_PRIORITIES),
            category=CategoryService.normalize_assignment("task", category),
            scheduled_date=(
                parse_life_date(scheduled_date, "scheduled_date")
                if scheduled_date is not None
                else None
            ),
            due_date=(
                parse_life_date(due_date, "due_date")
                if due_date is not None
                else None
            ),
            completed_at=now_iso() if normalized_status == "done" else None,
            sort_order=sort_order,
        )
        if parent_id is not None:
            task.parent = TaskService._get_parent(parent_id)
        db.session.add(task)
        db.session.flush()
        return task

    @staticmethod
    @transactional
    def update(
        task_id: int,
        *,
        title: object = UNSET,
        description: object = UNSET,
        status: object = UNSET,
        priority: object = UNSET,
        category: object = UNSET,
        scheduled_date: object = UNSET,
        due_date: object = UNSET,
        sort_order: object = UNSET,
        parent_id: object = UNSET,
    ) -> Task:
        task = db.session.get(Task, task_id)
        if task is None:
            raise NotFoundError("任务不存在。")
        if task.archived_at is not None:
            raise ValidationError("已归档任务需要先恢复后才能编辑。")
        if title is not UNSET:
            task.title = required_text(title, "title", 300)
        if description is not UNSET:
            task.description = optional_text(description, "description", 5000)
        if priority is not UNSET:
            task.priority = choice(priority, "priority", TASK_PRIORITIES)
        if category is not UNSET:
            task.category = CategoryService.normalize_assignment(
                "task", category
            )
        if scheduled_date is not UNSET:
            task.scheduled_date = (
                parse_life_date(scheduled_date, "scheduled_date")
                if scheduled_date is not None
                else None
            )
        if due_date is not UNSET:
            task.due_date = (
                parse_life_date(due_date, "due_date")
                if due_date is not None
                else None
            )
        if sort_order is not UNSET:
            if isinstance(sort_order, bool) or not isinstance(sort_order, int):
                raise ValidationError("sort_order 必须是整数。")
            task.sort_order = sort_order
        if parent_id is not UNSET:
            if parent_id is None:
                task.parent = None
            else:
                if isinstance(parent_id, bool) or not isinstance(parent_id, int):
                    raise ValidationError("parent_id 必须是整数或 null。")
                parent = TaskService._get_parent(parent_id)
                TaskService._ensure_no_cycle(task, parent)
                task.parent = parent
        if status is not UNSET:
            normalized_status = choice(status, "status", TASK_STATUSES)
            task.status = normalized_status
            task.completed_at = now_iso() if normalized_status == "done" else None
        db.session.flush()
        return task

    @staticmethod
    @transactional
    def archive(task_id: int) -> Task:
        task = db.session.get(Task, task_id)
        if task is None:
            raise NotFoundError("任务不存在。")
        if task.archived_at is None:
            task.archived_at = now_iso()
            db.session.flush()
        return task

    @staticmethod
    @transactional
    def restore(task_id: int) -> Task:
        task = db.session.get(Task, task_id)
        if task is None:
            raise NotFoundError("任务不存在。")
        task.archived_at = None
        db.session.flush()
        return task

    @staticmethod
    def _get_parent(parent_id: int) -> Task:
        if isinstance(parent_id, bool) or not isinstance(parent_id, int):
            raise ValidationError("parent_id 必须是整数。")
        parent = db.session.get(Task, parent_id)
        if parent is None:
            raise NotFoundError("父任务不存在。")
        return parent

    @staticmethod
    def _ensure_no_cycle(task: Task, parent: Task) -> None:
        visited: set[int] = set()
        current: Task | None = parent
        while current is not None:
            if current.id == task.id:
                raise ValidationError("任务父子关系不能形成循环。")
            if current.id in visited:
                raise ValidationError("现有任务父子关系包含循环。")
            visited.add(current.id)
            current = current.parent
