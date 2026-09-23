from __future__ import annotations

from flask import Blueprint

from life_os.api import json_object, query_bool, success_response
from life_os.serializers import habit_data, habit_log_data
from life_os.services.habit_service import HabitService


blueprint = Blueprint("habits", __name__)
HABIT_FIELDS = {"name", "description", "icon", "category", "sort_order"}
HABIT_UPDATE_FIELDS = HABIT_FIELDS | {"active"}
HABIT_LOG_FIELDS = {"status", "value", "value_unit", "note"}


@blueprint.get("/api/habits")
def get_habits():
    include_inactive = query_bool("include_inactive")
    habits = HabitService.list_habits(include_inactive=include_inactive)
    return success_response([habit_data(habit) for habit in habits])


@blueprint.post("/api/habits")
def post_habit():
    payload = json_object(allowed=HABIT_FIELDS, required={"name"})
    habit = HabitService.create(**payload)
    return success_response(habit_data(habit), status=201)


@blueprint.put("/api/habits/<int:habit_id>")
def put_habit(habit_id: int):
    payload = json_object(allowed=HABIT_UPDATE_FIELDS, require_any=True)
    habit = HabitService.update(habit_id, **payload)
    return success_response(habit_data(habit))


@blueprint.put("/api/habits/<int:habit_id>/log/<value_date>")
def put_habit_log(habit_id: int, value_date: str):
    payload = json_object(allowed=HABIT_LOG_FIELDS, required={"status"})
    log = HabitService.set_log(habit_id, value_date, **payload)
    return success_response(habit_log_data(log))
