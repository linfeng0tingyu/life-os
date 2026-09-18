from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_os.runtime import initialize_runtime, resolve_runtime_paths
from life_os.settings import SettingsError, load_settings


def _initialized_settings(tmp_path: Path) -> Path:
    paths = resolve_runtime_paths(
        env={"LIFE_OS_HOME": str(tmp_path / "runtime")}
    )
    initialize_runtime(paths, "test-version")
    return paths.settings_file


def test_default_settings_are_valid(tmp_path: Path) -> None:
    settings = load_settings(_initialized_settings(tmp_path))
    assert settings.host == "127.0.0.1"
    assert settings.port == 5000
    assert settings.backup_retention_count == 30


def test_non_loopback_host_is_rejected(tmp_path: Path) -> None:
    path = _initialized_settings(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["server"]["host"] = "0.0.0.0"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(SettingsError, match="127.0.0.1"):
        load_settings(path)


def test_boolean_is_not_accepted_as_port(tmp_path: Path) -> None:
    path = _initialized_settings(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["server"]["port"] = True
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(SettingsError, match="port 必须是整数"):
        load_settings(path)

