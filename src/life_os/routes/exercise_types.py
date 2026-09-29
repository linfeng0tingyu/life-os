from __future__ import annotations

from flask import Blueprint

from life_os.api import json_object, success_response
from life_os.serializers import exercise_type_data
from life_os.services.exercise_type_service import ExerciseTypeService


blueprint = Blueprint("exercise_types", __name__)


@blueprint.get("/api/exercise-types")
def get_exercise_types():
    return success_response(
        [exercise_type_data(item) for item in ExerciseTypeService.list_types()]
    )


@blueprint.post("/api/exercise-types")
def post_exercise_type():
    payload = json_object(
        allowed={"name", "sort_order"},
        required={"name"},
    )
    item = ExerciseTypeService.create(**payload)
    return success_response(exercise_type_data(item), status=201)


@blueprint.put("/api/exercise-types/order")
def put_exercise_type_order():
    payload = json_object(
        allowed={"exercise_type_ids"},
        required={"exercise_type_ids"},
    )
    items = ExerciseTypeService.reorder(**payload)
    return success_response([exercise_type_data(item) for item in items])


@blueprint.delete("/api/exercise-types/<int:exercise_type_id>")
def delete_exercise_type(exercise_type_id: int):
    deleted_id = ExerciseTypeService.delete(exercise_type_id)
    return success_response({"id": deleted_id, "deleted": True})
