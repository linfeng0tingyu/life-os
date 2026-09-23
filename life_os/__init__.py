from __future__ import annotations

import atexit
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, request
from sqlalchemy import URL
from werkzeug.exceptions import BadRequest, HTTPException

from .api import error_response
from .database import initialize_database
from .extensions import db
from .instance_lock import InstanceLock
from .logging_setup import configure_logging
from .runtime import RuntimePaths, initialize_runtime, resolve_runtime_paths
from .settings import load_settings
from .services.common import ConflictError, DomainError, NotFoundError, ValidationError
from .services.data_protection_service import (
    DataProtectionError,
    DataProtectionService,
)


__version__ = "0.1.0-dev"


def create_app(
    *,
    runtime_home: Path | None = None,
    acquire_lock: bool = False,
    testing: bool = False,
) -> Flask:
    paths = (
        RuntimePaths.from_home(runtime_home)
        if runtime_home is not None
        else resolve_runtime_paths()
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
        SEND_FILE_MAX_AGE_DEFAULT=0,
        SQLALCHEMY_ENGINE_OPTIONS={
            "connect_args": {"timeout": 5.0},
            "pool_pre_ping": True,
        },
    )
    app.extensions["life_os_runtime"] = paths
    app.extensions["life_os_settings"] = settings

    configure_logging(app, paths, settings)
    instance_lock: InstanceLock | None = None
    try:
        if acquire_lock:
            instance_lock = InstanceLock(paths.lock_file)
            instance_lock.acquire()
            app.extensions["life_os_instance_lock"] = instance_lock
            atexit.register(instance_lock.release)
            restore_result = DataProtectionService.process_pending_restore(paths)
            if restore_result is not None:
                app.logger.info(
                    "Pending restore processed status=%s backup=%s",
                    restore_result.get("status"),
                    restore_result.get("backup_file"),
                )

        db.init_app(app)
        initialize_database(app)
        app.extensions["life_os_startup_backup"] = {"status": "not_run"}
        if not testing:
            try:
                backup_result = DataProtectionService.create_backup(
                    paths,
                    settings.backup_retention_count,
                    kind="auto",
                )
                app.extensions["life_os_startup_backup"] = {
                    "status": "created" if backup_result.created else "current",
                    "filename": backup_result.backup.filename,
                    "created_at": backup_result.backup.created_at,
                }
                app.logger.info(
                    "Daily backup ready filename=%s created=%s removed=%s",
                    backup_result.backup.filename,
                    backup_result.created,
                    backup_result.removed_count,
                )
            except DataProtectionError as exc:
                app.extensions["life_os_startup_backup"] = {
                    "status": "failed",
                    "message": str(exc),
                }
                app.logger.error(
                    "Daily backup failed error_type=%s", type(exc).__name__
                )

        _register_error_handlers(app)

        from .routes import BLUEPRINTS

        for blueprint in BLUEPRINTS:
            app.register_blueprint(blueprint)
    except Exception:
        if instance_lock is not None:
            instance_lock.release()
        raise

    app.logger.info(
        "Life OS initialized version=%s runtime_home=%s",
        __version__,
        paths.home,
    )
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        g.request_id = uuid4().hex[:12]

    @app.after_request
    def attach_request_id(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.errorhandler(DomainError)
    def handle_domain_error(error: DomainError):
        status, code = {
            ValidationError: (400, "validation_error"),
            NotFoundError: (404, "not_found"),
            ConflictError: (409, "conflict"),
        }.get(type(error), (400, "domain_error"))
        app.logger.warning(
            "API domain error request_id=%s method=%s path=%s code=%s",
            g.get("request_id", ""),
            request.method,
            request.path,
            code,
        )
        return error_response(
            code, str(error), status=status, details=error.details
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            code = (
                "invalid_json"
                if isinstance(error, BadRequest)
                else error.name.lower().replace(" ", "_")
            )
            return error_response(
                code,
                error.description,
                status=error.code or 500,
            )
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        db.session.rollback()
        app.logger.error(
            "Unhandled application error request_id=%s method=%s path=%s "
            "error_type=%s",
            g.get("request_id", ""),
            request.method,
            request.path,
            type(error).__name__,
        )
        return error_response(
            "internal_error", "服务器发生内部错误。", status=500
        )

    @app.errorhandler(DataProtectionError)
    def handle_data_protection_error(error: DataProtectionError):
        app.logger.error(
            "Data protection error request_id=%s method=%s path=%s error_type=%s",
            g.get("request_id", ""),
            request.method,
            request.path,
            type(error).__name__,
        )
        return error_response(
            "data_protection_error",
            str(error),
            status=500,
        )
