from __future__ import annotations

from flask import Blueprint

from life_os.api import json_object, success_response
from life_os.serializers import health_data
from life_os.services.health_service import HealthService


blueprint = Blueprint("health", __name__)
HEALTH_FIELDS = {
    "weight_kg",
    "sleep_start",
    "sleep_end",
    "sleep_duration_minutes",
    "sleep_quality",
    "energy_level",
    "mood_level",
    "body_status",
    "exercise_minutes",
    "note",
}


@blueprint.get("/api/health/<value_date>")
def get_health(value_date: str):
    record = HealthService.get(value_date)
    return success_response(health_data(record) if record else None)


@blueprint.put("/api/health/<value_date>")
def put_health(value_date: str):
    payload = json_object(allowed=HEALTH_FIELDS, require_any=True)
    record = HealthService.upsert(value_date, **payload)
    return success_response(health_data(record))
