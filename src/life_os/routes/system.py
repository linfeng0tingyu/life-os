from __future__ import annotations

from collections import deque
from datetime import datetime
import re

from flask import Blueprint, current_app, jsonify, render_template
from sqlalchemy import text

from life_os.api import json_object, success_response
from life_os.extensions import db
from life_os.services.common import ValidationError
from life_os.services.data_protection_service import DataProtectionService
from life_os.settings import SettingsError, update_backup_retention


blueprint = Blueprint("system", __name__)
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\S+)\s+(?P<level>\S+)\s+(?P<logger>\S+)\s+(?P<message>.*)$"
)


def _recent_log_entries(limit: int = 20) -> list[dict[str, str]]:
    paths = current_app.extensions["life_os_runtime"]
    if not paths.log_file.is_file():
        return []
    with paths.log_file.open("r", encoding="utf-8", errors="replace") as handle:
        lines = deque(handle, maxlen=limit)
    entries = []
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        match = LOG_LINE_PATTERN.match(line)
        if match:
            entry = match.groupdict()
            entry["message"] = entry["message"].replace(
                str(paths.home), "<LIFE_OS_HOME>"
            )
            entries.append(entry)
        elif line:
            entries.append(
                {
                    "timestamp": "",
                    "level": "INFO",
                    "logger": "life_os",
                    "message": line.replace(str(paths.home), "<LIFE_OS_HOME>"),
                }
            )
    return entries


@blueprint.get("/")
def index():
    from life_os import __version__

    return render_template(
        "index.html", app_version=__version__, active_page="today"
    )


@blueprint.get("/calendar")
def calendar_page():
    from life_os import __version__

    return render_template(
        "calendar.html", app_version=__version__, active_page="calendar"
    )


@blueprint.get("/tasks")
def tasks_page():
    from life_os import __version__

    return render_template(
        "tasks.html", app_version=__version__, active_page="tasks"
    )


@blueprint.get("/habits")
def habits_page():
    from life_os import __version__

    return render_template(
        "habits.html", app_version=__version__, active_page="habits"
    )


@blueprint.get("/health")
def health_page():
    from life_os import __version__

    return render_template(
        "health.html", app_version=__version__, active_page="health"
    )


@blueprint.get("/journal")
def journal_page():
    from life_os import __version__

    return render_template(
        "journal.html", app_version=__version__, active_page="journal"
    )


@blueprint.get("/finance")
def finance_page():
    from life_os import __version__

    return render_template(
        "finance.html", app_version=__version__, active_page="finance"
    )


@blueprint.get("/settings")
def settings_page():
    from life_os import __version__

    return render_template(
        "settings.html", app_version=__version__, active_page="settings"
    )


@blueprint.get("/api/system/health")
def health():
    from life_os import __version__

    paths = current_app.extensions["life_os_runtime"]
    return jsonify(
        {
            "success": True,
            "data": {
                "status": "ok",
                "version": __version__,
                "runtime_ready": paths.home.is_dir(),
                "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
        }
    )


@blueprint.get("/api/system/info")
def info():
    from life_os import __version__

    paths = current_app.extensions["life_os_runtime"]
    return success_response(
        {
            "version": __version__,
            "schema_version": current_app.extensions["life_os_schema_version"],
            "runtime": {
                "ready": paths.home.is_dir(),
                "portable": True,
                "home": str(paths.home),
                "database": "database/life.db",
            },
            "capabilities": {
                "backup": True,
                "export": True,
                "restore_on_restart": True,
            },
            "backup": {
                "retention_count": current_app.extensions[
                    "life_os_settings"
                ].backup_retention_count,
                "startup": current_app.extensions.get(
                    "life_os_startup_backup", {"status": "unknown"}
                ),
            },
            "restore": DataProtectionService.restore_status(paths),
        }
    )


@blueprint.get("/api/system/diagnostics")
def diagnostics():
    from life_os import __version__

    paths = current_app.extensions["life_os_runtime"]
    database_ok = db.session.execute(text("SELECT 1")).scalar_one() == 1
    log_entries = _recent_log_entries()
    return success_response(
        {
            "status": "ok" if database_ok and paths.home.is_dir() else "error",
            "version": __version__,
            "schema_version": current_app.extensions["life_os_schema_version"],
            "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "runtime": {
                "ready": paths.home.is_dir(),
                "database_ready": database_ok,
                "database_size_bytes": (
                    paths.database_file.stat().st_size
                    if paths.database_file.is_file()
                    else 0
                ),
            },
            "backup": current_app.extensions.get(
                "life_os_startup_backup", {"status": "unknown"}
            ),
            "logs": {
                "relative_path": "logs/app.log",
                "error_count": sum(
                    entry["level"] in {"ERROR", "CRITICAL"}
                    for entry in log_entries
                ),
                "items": log_entries,
            },
        }
    )


@blueprint.get("/api/system/backups")
def backups():
    paths = current_app.extensions["life_os_runtime"]
    return success_response(
        {
            "items": [
                {
                    "filename": item.filename,
                    "relative_path": item.relative_path,
                    "created_at": item.created_at,
                    "size_bytes": item.size_bytes,
                    "kind": item.kind,
                }
                for item in DataProtectionService.list_backups(paths)
            ]
        }
    )


@blueprint.post("/api/system/backup")
def create_backup():
    paths = current_app.extensions["life_os_runtime"]
    settings = current_app.extensions["life_os_settings"]
    result = DataProtectionService.create_backup(
        paths, settings.backup_retention_count, kind="manual"
    )
    current_app.logger.info(
        "Manual backup created filename=%s removed=%s",
        result.backup.filename,
        result.removed_count,
    )
    return success_response(
        {
            "filename": result.backup.filename,
            "relative_path": result.backup.relative_path,
            "created_at": result.backup.created_at,
            "size_bytes": result.backup.size_bytes,
            "removed_count": result.removed_count,
        },
        status=201,
    )


@blueprint.post("/api/system/export")
def export_all():
    from life_os import __version__

    payload = json_object(allowed={"include_zip"})
    include_zip = payload.get("include_zip", True)
    if not isinstance(include_zip, bool):
        raise ValidationError("include_zip 必须是布尔值。")
    paths = current_app.extensions["life_os_runtime"]
    result = DataProtectionService.export_all(
        paths,
        app_version=__version__,
        schema_version=current_app.extensions["life_os_schema_version"],
        include_zip=include_zip,
    )
    current_app.logger.info(
        "Full export created path=%s zip=%s",
        result["relative_path"],
        bool(result["zip_relative_path"]),
    )
    return success_response(result, status=201)


@blueprint.put("/api/system/settings/backup")
def update_backup_settings():
    payload = json_object(
        allowed={"retention_count"}, required={"retention_count"}
    )
    paths = current_app.extensions["life_os_runtime"]
    try:
        settings = update_backup_retention(
            paths.settings_file, payload["retention_count"]
        )
    except SettingsError as exc:
        raise ValidationError(str(exc)) from exc
    current_app.extensions["life_os_settings"] = settings
    return success_response(
        {"retention_count": settings.backup_retention_count}
    )


@blueprint.post("/api/system/restore")
def schedule_restore():
    payload = json_object(
        allowed={"backup_file", "confirmation"},
        required={"backup_file", "confirmation"},
    )
    paths = current_app.extensions["life_os_runtime"]
    result = DataProtectionService.schedule_restore(
        paths,
        payload["backup_file"],
        payload["confirmation"],
    )
    current_app.logger.warning(
        "Database restore scheduled backup=%s", result["backup_file"]
    )
    return success_response(result, status=202)


@blueprint.delete("/api/system/restore")
def cancel_restore():
    paths = current_app.extensions["life_os_runtime"]
    cancelled = DataProtectionService.cancel_pending_restore(paths)
    if cancelled:
        current_app.logger.info("Pending database restore cancelled")
    return success_response({"cancelled": cancelled})
