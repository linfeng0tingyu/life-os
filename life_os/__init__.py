from __future__ import annotations

import atexit
from pathlib import Path

from flask import Flask, jsonify, request
from sqlalchemy import URL
from werkzeug.exceptions import HTTPException

from .database import initialize_database
from .extensions import db
from .instance_lock import InstanceLock
from .logging_setup import configure_logging
from .runtime import RuntimePaths, initialize_runtime, resolve_runtime_paths
from .settings import load_settings


__version__ = "0.1.0-dev"


def create_app(
    *,
    runtime_home: Path | None = None,
    acquire_lock: bool = False,
    testing: bool = False,
) -> Flask:
    project_root = Path(__file__).resolve().parents[1]
    paths = (
        RuntimePaths.from_home(runtime_home)
        if runtime_home is not None
        else resolve_runtime_paths(project_root=project_root)
    )
    paths.assert_contained()
    initialize_runtime(paths, __version__)
    settings = load_settings(paths.settings_file)

    app = Flask(
        __name__,
        instance_path=str(paths.cache_dir / "flask-instance"),
        template_folder="templates",
        static_folder="static",
    )
    app.config.update(
        TESTING=testing,
        DEBUG=settings.debug if not testing else False,
        JSON_AS_ASCII=False,
        SQLALCHEMY_DATABASE_URI=URL.create(
            "sqlite+pysqlite", database=str(paths.database_file)
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "connect_args": {"timeout": 5.0},
            "pool_pre_ping": True,
        },
    )
    app.extensions["life_os_runtime"] = paths
    app.extensions["life_os_settings"] = settings

    configure_logging(app, paths, settings)
    db.init_app(app)
    initialize_database(app)
    _register_error_handlers(app)

    from .routes.system import blueprint as system_blueprint

    app.register_blueprint(system_blueprint)

    if acquire_lock:
        instance_lock = InstanceLock(paths.lock_file)
        instance_lock.acquire()
        app.extensions["life_os_instance_lock"] = instance_lock
        atexit.register(instance_lock.release)

    app.logger.info(
        "Life OS initialized version=%s runtime_home=%s",
        __version__,
        paths.home,
    )
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": error.name.lower().replace(" ", "_"),
                            "message": error.description,
                            "details": {},
                        },
                    }
                ),
                error.code,
            )
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("Unhandled application error", exc_info=error)
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "internal_error",
                        "message": "服务器发生内部错误。",
                        "details": {},
                    },
                }
            ),
            500,
        )
