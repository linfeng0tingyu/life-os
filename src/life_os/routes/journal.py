from __future__ import annotations

from flask import Blueprint, current_app, request, send_file

from life_os.api import json_object, success_response
from life_os.serializers import journal_data
from life_os.services.journal_service import JournalService
from life_os.services.journal_asset_service import JournalAssetService
from life_os.services.common import NotFoundError, ValidationError


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


@blueprint.post("/api/journal/<value_date>/assets")
def post_journal_asset(value_date: str):
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
