from __future__ import annotations

import re
from datetime import date

from flask import Blueprint, current_app, request, send_file

from life_os.api import json_object, success_response
from life_os.serializers import journal_data
from life_os.services.journal_service import JournalService
from life_os.services.journal_asset_service import JournalAssetService
from life_os.services.common import (
    ConflictError,
    NotFoundError,
    ValidationError,
    parse_life_date,
)


blueprint = Blueprint("journal", __name__)
MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def local_today() -> date:
    return date.today()


def require_today(value_date: str) -> None:
    if parse_life_date(value_date) != local_today():
        raise ConflictError("只有今天的日记可以修改，其他日期仅供阅读。")


@blueprint.get("/api/journal/month/<year_month>")
def get_journal_month(year_month: str):
    match = MONTH_PATTERN.fullmatch(year_month)
    if match is None:
        raise ValidationError("month 必须使用 YYYY-MM 格式。")
    year, month = (int(part) for part in match.groups())
    entries = JournalService.list_month(year, month)
    return success_response(
        {
            "month": year_month,
            "entries": [
                {
                    "date": entry.date.isoformat(),
                    "updated_at": entry.updated_at,
                }
                for entry in entries
            ],
        }
    )


@blueprint.get("/api/journal/<value_date>")
def get_journal(value_date: str):
    journal = JournalService.get(value_date)
    return success_response(journal_data(journal) if journal else None)


@blueprint.put("/api/journal/<value_date>")
def put_journal(value_date: str):
    require_today(value_date)
    payload = json_object(allowed={"content"}, required={"content"})
    journal = JournalService.upsert(value_date, payload["content"])
    return success_response(journal_data(journal))


@blueprint.post("/api/journal/<value_date>/assets")
def post_journal_asset(value_date: str):
    require_today(value_date)
    upload = request.files.get("image")
    if upload is None:
        raise ValidationError("image 为必填图片文件。")
    paths = current_app.extensions["life_os_runtime"]
    asset = JournalAssetService.save(paths, value_date, upload)
    return success_response(
        {
            "date": asset.date,
            "filename": asset.filename,
            "original_name": asset.original_name,
            "mime_type": asset.mime_type,
            "size": asset.size,
            "url": asset.url,
        },
        status=201,
    )


@blueprint.get("/api/journal/assets/<value_date>/<filename>")
def get_journal_asset(value_date: str, filename: str):
    paths = current_app.extensions["life_os_runtime"]
    path = JournalAssetService.asset_path(paths, value_date, filename)
    return send_file(path, mimetype=JournalAssetService.mime_type(path.suffix))


@blueprint.get("/api/journal/<value_date>/export")
def export_journal(value_date: str):
    journal = JournalService.get(value_date)
    if journal is None:
        raise NotFoundError("该日期还没有日记，无法导出。")
    paths = current_app.extensions["life_os_runtime"]
    path = JournalAssetService.export_markdown(paths, value_date, journal.content)
    return send_file(
        path,
        as_attachment=True,
        download_name=path.name,
        mimetype="text/markdown; charset=utf-8",
    )
