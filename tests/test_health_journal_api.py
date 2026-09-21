from __future__ import annotations

import base64
from io import BytesIO

from flask.testing import FlaskClient

from life_os.extensions import db


def test_health_get_and_partial_upsert(client: FlaskClient) -> None:
    path = "/api/health/2026-09-18"
    assert client.get(path).get_json()["data"] is None
    first = client.put(path, json={"weight_kg": 65.5, "energy_level": 4})
    assert first.status_code == 200
    record_id = first.get_json()["data"]["id"]
    second = client.put(path, json={"mood_level": 5, "weight_kg": None})
    data = second.get_json()["data"]
    assert data["id"] == record_id
    assert data["weight_kg"] is None
    assert data["energy_level"] == 4
    assert data["mood_level"] == 5


def test_health_sleep_calculation_and_manual_override(client: FlaskClient) -> None:
    path = "/api/health/2026-09-18"
    calculated = client.put(
        path,
        json={
            "sleep_start": "2026-09-17T23:30:00+08:00",
            "sleep_end": "2026-09-18T07:00:00+08:00",
        },
    ).get_json()["data"]
    assert calculated["sleep_duration_minutes"] == 450
    assert calculated["sleep_duration_manual"] is False

    manual = client.put(path, json={"sleep_duration_minutes": 420}).get_json()[
        "data"
    ]
    assert manual["sleep_duration_minutes"] == 420
    assert manual["sleep_duration_manual"] is True


def test_health_validation(client: FlaskClient) -> None:
    assert client.put("/api/health/2026-09-18", json={}).status_code == 400
    assert (
        client.put(
            "/api/health/2026-09-18", json={"sleep_quality": 6}
        ).status_code
        == 400
    )
    assert (
        client.put("/api/health/2026-09-18", json={"weight_kg": 0}).status_code
        == 400
    )
    assert (
        client.put(
            "/api/health/2026-09-18", json={"exercise_minutes": -1}
        ).status_code
        == 400
    )


def test_journal_unicode_markdown_round_trip_and_upsert(client: FlaskClient) -> None:
    path = "/api/journal/2026-09-18"
    assert client.get(path).get_json()["data"] is None
    content = "# 今日\n\n- 完成 API 🎉\n**保留 Markdown**"
    first = client.put(path, json={"content": content})
    assert first.status_code == 200
    record_id = first.get_json()["data"]["id"]
    assert client.get(path).get_json()["data"]["content"] == content

    cleared = client.put(path, json={"content": ""})
    assert cleared.get_json()["data"]["id"] == record_id
    assert cleared.get_json()["data"]["content"] == ""
    assert client.put(path, json={}).status_code == 400


def test_journal_unexpected_failure_rolls_back_and_hides_content(
    client: FlaskClient, monkeypatch, caplog
) -> None:
    from life_os.routes.journal import JournalService

    path = "/api/journal/2026-09-18"
    client.put(path, json={"content": "Original"})
    original_upsert = JournalService.upsert

    def fail_after_flush(value_date, content):
        journal = JournalService.get(value_date)
        journal.content = content
        db.session.flush()
        raise RuntimeError(content)

    monkeypatch.setattr(JournalService, "upsert", fail_after_flush)
    secret_content = "Private diary content must not enter logs"
    failed = client.put(path, json={"content": secret_content})
    assert failed.status_code == 500
    assert secret_content not in failed.get_data(as_text=True)
    assert secret_content not in caplog.text

    monkeypatch.setattr(JournalService, "upsert", original_upsert)
    assert client.get(path).get_json()["data"]["content"] == "Original"


def test_journal_image_upload_preview_asset_and_self_contained_export(
    client: FlaskClient, app
) -> None:
    image = b"\x89PNG\r\n\x1a\n" + b"test-image"
    uploaded = client.post(
        "/api/journal/2026-09-21/assets",
        data={"image": (BytesIO(image), "示例.png")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201
    asset = uploaded.get_json()["data"]
    assert asset["mime_type"] == "image/png"
    assert asset["url"].startswith("/api/journal/assets/2026-09-21/")
    fetched = client.get(asset["url"])
    assert fetched.status_code == 200
    assert fetched.data == image

    content = f"# 图文日记\n\n![示例]({asset['url']})"
    client.put("/api/journal/2026-09-21", json={"content": content})
    exported = client.get("/api/journal/2026-09-21/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["Content-Disposition"]
    expected_data = base64.b64encode(image).decode("ascii")
    assert f"data:image/png;base64,{expected_data}" in exported.get_data(as_text=True)
    paths = app.extensions["life_os_runtime"]
    assert (paths.exports_dir / "journal" / "2026-09-21.md").is_file()
    assert (paths.attachments_dir / "journal" / "2026-09-21" / asset["filename"]).is_file()


def test_journal_image_upload_validation_and_missing_export(client: FlaskClient) -> None:
    invalid = client.post(
        "/api/journal/2026-09-21/assets",
        data={"image": (BytesIO(b"not-an-image"), "bad.txt")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert client.get("/api/journal/2026-09-22/export").status_code == 404
