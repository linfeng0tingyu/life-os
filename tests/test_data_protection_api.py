from __future__ import annotations

import json
from pathlib import Path

from flask.testing import FlaskClient


def test_system_info_exposes_portable_data_protection_capabilities(
    client: FlaskClient, app
) -> None:
    response = client.get("/api/system/info")
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert data["runtime"]["home"] == str(
        app.extensions["life_os_runtime"].home
    )
    assert data["capabilities"] == {
        "backup": True,
        "export": True,
        "restore_on_restart": True,
    }
    assert data["backup"]["retention_count"] == 30


def test_manual_backup_list_and_retention_settings(
    client: FlaskClient, app
) -> None:
    updated = client.put(
        "/api/system/settings/backup", json={"retention_count": 5}
    )
    created = client.post("/api/system/backup", json={})
    listed = client.get("/api/system/backups")

    assert updated.status_code == 200
    assert updated.get_json()["data"]["retention_count"] == 5
    assert created.status_code == 201
    backup = created.get_json()["data"]
    assert backup["relative_path"].startswith("backups/")
    assert listed.get_json()["data"]["items"][0]["filename"] == backup["filename"]
    settings = json.loads(
        app.extensions["life_os_runtime"].settings_file.read_text(encoding="utf-8")
    )
    assert settings["backup"]["retention_count"] == 5


def test_full_export_and_restore_schedule_contract(client: FlaskClient, app) -> None:
    backup = client.post("/api/system/backup", json={}).get_json()["data"]
    invalid = client.post(
        "/api/system/restore",
        json={"backup_file": backup["filename"], "confirmation": "不确认"},
    )
    scheduled = client.post(
        "/api/system/restore",
        json={"backup_file": backup["filename"], "confirmation": "恢复此备份"},
    )
    exported = client.post("/api/system/export", json={"include_zip": True})

    assert invalid.status_code == 400
    assert scheduled.status_code == 202
    assert scheduled.get_json()["data"]["status"] == "pending_restart"
    cancelled = client.delete("/api/system/restore")
    assert cancelled.status_code == 200
    assert cancelled.get_json()["data"]["cancelled"] is True
    assert exported.status_code == 201
    export_data = exported.get_json()["data"]
    paths = app.extensions["life_os_runtime"]
    assert (paths.home / export_data["relative_path"] / "manifest.json").is_file()
    assert (paths.home / export_data["zip_relative_path"]).is_file()


def test_backup_settings_reject_boolean_and_unknown_backup(
    client: FlaskClient,
) -> None:
    invalid_setting = client.put(
        "/api/system/settings/backup", json={"retention_count": True}
    )
    missing_backup = client.post(
        "/api/system/restore",
        json={
            "backup_file": "life-os-20260922-120000-000000-manual.db",
            "confirmation": "恢复此备份",
        },
    )

    assert invalid_setting.status_code == 400
    assert missing_backup.status_code == 404
