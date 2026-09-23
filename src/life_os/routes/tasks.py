from __future__ import annotations

from flask import Blueprint, request

from life_os.api import json_object, query_bool, success_response
from life_os.serializers import task_data
from life_os.services.common import parse_life_date
from life_os.services.task_service import TaskService


blueprint = Blueprint("tasks", __name__)
TASK_FIELDS = {
    "title",
    "description",
    "status",
    "priority",
    "category",
    "scheduled_date",
    "due_date",
    "sort_order",
    "parent_id",
}


@blueprint.get("/api/tasks")
def get_tasks():
    include_archived = query_bool("include_archived")
    value_date = request.args.get("date")
    target = parse_life_date(value_date) if value_date is not None else None
    tasks = TaskService.list_tasks(
        include_archived=include_archived,
        status=request.args.get("status"),
        value_date=target,
    )
    return success_response([task_data(task, target_date=target) for task in tasks])


@blueprint.post("/api/tasks")
def post_task():
    payload = json_object(allowed=TASK_FIELDS, required={"title"})
    task = TaskService.create(**payload)
    return success_response(task_data(task), status=201)


@blueprint.put("/api/tasks/<int:task_id>")
def put_task(task_id: int):
    payload = json_object(allowed=TASK_FIELDS, require_any=True)
    task = TaskService.update(task_id, **payload)
    return success_response(task_data(task))


@blueprint.delete("/api/tasks/<int:task_id>")
def delete_task(task_id: int):
    task = TaskService.archive(task_id)
    return success_response(task_data(task))


@blueprint.post("/api/tasks/<int:task_id>/restore")
def restore_task(task_id: int):
    task = TaskService.restore(task_id)
    return success_response(task_data(task))
