from __future__ import annotations

import pytest

from life_os.services import TaskService, ValidationError


def test_task_lifecycle_and_completion_timestamp(app_context: None) -> None:
    task = TaskService.create(
        "学习 FPGA", scheduled_date="2026-09-18", priority="high"
    )
    assert task.status == "todo"
    assert task.completed_at is None

    TaskService.update(task.id, status="done")
    assert task.completed_at is not None
    TaskService.update(task.id, status="doing")
    assert task.completed_at is None

    TaskService.archive(task.id)
    assert TaskService.list_tasks() == []
    assert len(TaskService.list_tasks(include_archived=True)) == 1
    TaskService.restore(task.id)
    assert len(TaskService.list_tasks()) == 1


def test_task_parent_cycle_is_rejected_and_rolled_back(app_context: None) -> None:
    parent = TaskService.create("父任务")
    child = TaskService.create("子任务", parent_id=parent.id)

    with pytest.raises(ValidationError, match="循环"):
        TaskService.update(parent.id, parent_id=child.id)
    assert parent.parent_id is None
    assert child.parent_id == parent.id


def test_task_validation_does_not_partially_update(app_context: None) -> None:
    task = TaskService.create("原始任务")
    with pytest.raises(ValidationError):
        TaskService.update(task.id, title="新标题", priority="impossible")

    assert TaskService.list_tasks()[0].title == "原始任务"
