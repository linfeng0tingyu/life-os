from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_os.runtime import (
    RUNTIME_DIRECTORY_NAMES,
    RuntimeSetupError,
    initialize_runtime,
    resolve_runtime_paths,
)


def test_custom_home_initializes_only_inside_runtime(tmp_path: Path) -> None:
    home = tmp_path / "portable-data"
    paths = resolve_runtime_paths(env={"LIFE_OS_HOME": str(home)})

    initialize_runtime(paths, "test-version")

    assert {item.name for item in home.iterdir()} == {
        *RUNTIME_DIRECTORY_NAMES,
        "metadata.json",
    }
    assert paths.settings_file.is_file()
    assert paths.metadata_file.is_file()
    assert paths.webview_cache_dir.is_dir()
    assert set(tmp_path.iterdir()) == {home}

    settings = json.loads(paths.settings_file.read_text(encoding="utf-8"))
    metadata = json.loads(paths.metadata_file.read_text(encoding="utf-8"))
    assert settings["server"]["host"] == "127.0.0.1"
    assert metadata["runtime_format_version"] == 1


def test_default_home_is_project_local(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(project_root=tmp_path, env={})
    assert paths.home == (tmp_path / "life-os-data").resolve()


def test_explicit_home_must_be_absolute() -> None:
    with pytest.raises(RuntimeSetupError, match="绝对路径"):
        resolve_runtime_paths(env={"LIFE_OS_HOME": "relative-data"})


def test_home_cannot_be_an_existing_file(tmp_path: Path) -> None:
    home = tmp_path / "not-a-directory"
    home.write_text("occupied", encoding="utf-8")
    paths = resolve_runtime_paths(env={"LIFE_OS_HOME": str(home)})

    with pytest.raises(RuntimeSetupError, match="不是目录"):
        initialize_runtime(paths, "test-version")


def test_invalid_existing_metadata_stops_startup(tmp_path: Path) -> None:
    home = tmp_path / "runtime"
    paths = resolve_runtime_paths(env={"LIFE_OS_HOME": str(home)})
    initialize_runtime(paths, "test-version")
    paths.metadata_file.write_text(
        '{"runtime_format_version": 999}\n', encoding="utf-8"
    )

    with pytest.raises(RuntimeSetupError, match="不兼容"):
        initialize_runtime(paths, "test-version")
