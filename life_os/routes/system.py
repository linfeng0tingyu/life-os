from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template

from life_os.api import success_response


blueprint = Blueprint("system", __name__)


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
                "database": "database/life.db",
            },
            "capabilities": {
                "backup": False,
                "export": False,
                "backup_export_milestone": "M7",
            },
        }
    )
