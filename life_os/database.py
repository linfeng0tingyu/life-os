from __future__ import annotations

import sqlite3

from flask import Flask
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import SchemaMeta
from .models.base import now_iso


SCHEMA_VERSION = 3
MINIMUM_MIGRATABLE_VERSION = 1


class DatabaseInitializationError(RuntimeError):
    """Raised when the SQLite database cannot be initialized safely."""


class DatabaseVersionError(DatabaseInitializationError):
    """Raised when the on-disk schema is incompatible with this application."""


@event.listens_for(Engine, "connect")
def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
    finally:
        cursor.close()


def initialize_database(app: Flask) -> None:
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            has_schema_meta = "schema_meta" in existing_tables
            if existing_tables and not has_schema_meta:
                raise DatabaseVersionError(
                    "现有数据库缺少 schema_meta，无法确认兼容性，已停止写入。"
                )
            stored_version_number: int | None = None
            if has_schema_meta:
                stored_version = db.session.execute(
                    text(
                        "SELECT value FROM schema_meta "
                        "WHERE key = 'schema_version'"
                    )
                ).scalar_one_or_none()
                if stored_version is None:
                    raise DatabaseVersionError(
                        "数据库缺少 schema_version，已停止写入。"
                    )
                try:
                    stored_version_number = int(stored_version)
                except ValueError as exc:
                    raise DatabaseVersionError(
                        "数据库 schema_version 不是有效整数，已停止写入。"
                    ) from exc
                if not MINIMUM_MIGRATABLE_VERSION <= stored_version_number <= SCHEMA_VERSION:
                    raise DatabaseVersionError(
                        "数据库 schema 版本不兼容："
                        f"磁盘版本 {stored_version}，程序版本 {SCHEMA_VERSION}。"
                    )

            db.create_all()
            if not has_schema_meta:
                db.session.add(
                    SchemaMeta(key="schema_version", value=str(SCHEMA_VERSION))
                )
                db.session.commit()
            elif stored_version_number is not None and stored_version_number < SCHEMA_VERSION:
                if stored_version_number < 3:
                    _migrate_categories()
                version_record = db.session.get(SchemaMeta, "schema_version")
                if version_record is None:
                    raise DatabaseVersionError(
                        "数据库缺少 schema_version，已停止写入。"
                    )
                version_record.value = str(SCHEMA_VERSION)
                db.session.commit()

            integrity_result = db.session.execute(
                text("PRAGMA integrity_check")
            ).scalar_one()
            if integrity_result != "ok":
                raise DatabaseInitializationError(
                    f"SQLite 完整性检查失败：{integrity_result}"
                )
            app.extensions["life_os_schema_version"] = SCHEMA_VERSION
        except DatabaseInitializationError:
            db.session.rollback()
            raise
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise DatabaseInitializationError("SQLite 初始化失败。") from exc


def _migrate_categories() -> None:
    timestamp = now_iso()
    for scope, table in (("task", "tasks"), ("habit", "habits")):
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO categories "
                "(scope, name, sort_order, created_at, updated_at) "
                f"SELECT :scope, category, 0, :timestamp, :timestamp FROM {table} "
                "WHERE category IS NOT NULL AND trim(category) != '' "
                "GROUP BY category"
            ),
            {"scope": scope, "timestamp": timestamp},
        )


def checkpoint_database(app: Flask) -> None:
    with app.app_context():
        try:
            db.session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise DatabaseInitializationError(
                "SQLite WAL checkpoint 失败。"
            ) from exc
        finally:
            db.session.remove()
            db.engine.dispose()
