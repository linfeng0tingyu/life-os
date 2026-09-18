from __future__ import annotations

import sqlite3

from flask import Flask
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import SchemaMeta


SCHEMA_VERSION = 1


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
                if stored_version != str(SCHEMA_VERSION):
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
