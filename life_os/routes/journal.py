from __future__ import annotations

from flask import Blueprint

from life_os.api import json_object, success_response
from life_os.serializers import journal_data
from life_os.services.journal_service import JournalService


blueprint = Blueprint("journal", __name__)


@blueprint.get("/api/journal/<value_date>")
def get_journal(value_date: str):
    journal = JournalService.get(value_date)
    return success_response(journal_data(journal) if journal else None)


@blueprint.put("/api/journal/<value_date>")
def put_journal(value_date: str):
    payload = json_object(allowed={"content"}, required={"content"})
    journal = JournalService.upsert(value_date, payload["content"])
    return success_response(journal_data(journal))
