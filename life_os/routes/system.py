from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template


blueprint = Blueprint("system", __name__)


@blueprint.get("/")
def index():
    return render_template("index.html")


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

