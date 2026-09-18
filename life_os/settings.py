from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SettingsError(RuntimeError):
    """Raised when settings.json violates the supported schema."""


@dataclass(frozen=True, slots=True)
class AppSettings:
    host: str
    port: int
    debug: bool
    open_browser: bool
    backup_retention_count: int
    log_level: str
    log_max_bytes: int
    log_backup_count: int


def load_settings(path: Path) -> AppSettings:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsError(f"无法读取配置文件：{path}") from exc

    if not isinstance(document, dict):
        raise SettingsError("settings.json 顶层必须是 JSON 对象。")
    if document.get("settings_version") != 1:
        raise SettingsError("不支持的 settings_version。")

    server = _section(document, "server")
    backup = _section(document, "backup")
    logging = _section(document, "logging")

    host = server.get("host")
    if host != "127.0.0.1":
        raise SettingsError("v0.1 的 server.host 必须为 127.0.0.1。")

    port = _integer(server, "port", minimum=1024, maximum=65535)
    debug = _boolean(server, "debug")
    open_browser = _boolean(server, "open_browser")
    retention = _integer(backup, "retention_count", minimum=1, maximum=3650)

    level = logging.get("level")
    allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level not in allowed_levels:
        raise SettingsError(
            "logging.level 必须是 DEBUG、INFO、WARNING、ERROR 或 CRITICAL。"
        )

    return AppSettings(
        host=host,
        port=port,
        debug=debug,
        open_browser=open_browser,
        backup_retention_count=retention,
        log_level=level,
        log_max_bytes=_integer(
            logging, "max_bytes", minimum=65_536, maximum=104_857_600
        ),
        log_backup_count=_integer(
            logging, "backup_count", minimum=1, maximum=100
        ),
    )


def _section(document: dict[str, Any], name: str) -> dict[str, Any]:
    value = document.get(name)
    if not isinstance(value, dict):
        raise SettingsError(f"settings.json 缺少对象：{name}")
    return value


def _integer(
    section: dict[str, Any], key: str, minimum: int, maximum: int
) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"{key} 必须是整数。")
    if not minimum <= value <= maximum:
        raise SettingsError(f"{key} 必须在 {minimum} 到 {maximum} 之间。")
    return value


def _boolean(section: dict[str, Any], key: str) -> bool:
    value = section.get(key)
    if not isinstance(value, bool):
        raise SettingsError(f"{key} 必须是布尔值。")
    return value

