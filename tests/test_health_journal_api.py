from __future__ import annotations

import base64
from datetime import date
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


def test_health_accepts_sleep_status_and_managed_exercise_types(
    client: FlaskClient,
) -> None:
    path = "/api/health/2026-09-18"
    strength = client.post("/api/exercise-types", json={"name": "力量训练"})
    walking = client.post("/api/exercise-types", json={"name": "步行"})
    strength_id = strength.get_json()["data"]["id"]
    walking_id = walking.get_json()["data"]["id"]
    recorded = client.put(
        path,
        json={
            "sleep_status": "between_6_7_5",
            "exercise_minutes": 45,
            "exercise_type_ids": [strength_id, walking_id],
        },
    ).get_json()["data"]
    assert recorded["sleep_status"] == "between_6_7_5"
    assert [item["name"] for item in recorded["exercise_types"]] == ["力量训练", "步行"]
    assert client.delete(f"/api/exercise-types/{strength_id}").status_code == 409

    updated = client.put(path, json={"exercise_type_ids": [walking_id]}).get_json()["data"]
    assert [item["id"] for item in updated["exercise_types"]] == [walking_id]
    assert client.delete(f"/api/exercise-types/{strength_id}").status_code == 200


def test_today_health_fields_partially_update_without_erasing_details(
    client: FlaskClient,
) -> None:
    exercise = client.post(
        "/api/exercise-types", json={"name": "骑行"}
    ).get_json()["data"]
    path = "/api/health/2026-09-18"
    client.put(
        path,
        json={
            "weight_kg": 66.2,
            "exercise_minutes": 35,
            "body_status": "状态稳定",
        },
    )

    response = client.put(
        path,
        json={
            "sleep_status": "between_6_7_5",
            "exercise_type_ids": [exercise["id"]],
            "energy_level": 4,
            "mood_level": 5,
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["sleep_status"] == "between_6_7_5"
    assert data["energy_level"] == 4
    assert data["mood_level"] == 5
    assert [item["id"] for item in data["exercise_types"]] == [exercise["id"]]
    assert data["weight_kg"] == 66.2
    assert data["exercise_minutes"] == 35
    assert data["body_status"] == "状态稳定"


def test_health_validation(client: FlaskClient) -> None:
    assert client.put("/api/health/2026-09-18", json={}).status_code == 400
    assert (
        client.put(
            "/api/health/2026-09-18", json={"sleep_status": "unknown"}
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
    assert (
        client.put(
            "/api/health/2026-09-18",
            json={"sleep_start": "2026-09-17T23:00:00+08:00"},
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/api/health/2026-09-18",
            json={"sleep_end": "2026-09-18T07:00:00+08:00"},
        ).status_code
        == 400
    )
    assert client.put(
        "/api/health/2026-09-18", json={"exercise_type_ids": [999999]}
    ).status_code == 400
    assert client.put(
        "/api/health/2026-09-18", json={"exercise_type_ids": [1, 1]}
    ).status_code == 400


def test_journal_unicode_markdown_round_trip_and_upsert(client: FlaskClient, monkeypatch) -> None:
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 18))
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
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 18))
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
    client: FlaskClient, app, monkeypatch
) -> None:
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 21))
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


def test_journal_image_upload_validation_and_missing_export(client: FlaskClient, monkeypatch) -> None:
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 21))
    invalid = client.post(
        "/api/journal/2026-09-21/assets",
        data={"image": (BytesIO(b"not-an-image"), "bad.txt")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert client.get("/api/journal/2026-09-22/export").status_code == 404


def test_journal_month_index_and_non_today_writes_are_blocked(
    client: FlaskClient, monkeypatch
) -> None:
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 21))
    assert client.put("/api/journal/2026-09-21", json={"content": "历史内容"}).status_code == 200
    monkeypatch.setattr("life_os.routes.journal.local_today", lambda: date(2026, 9, 23))

    month = client.get("/api/journal/month/2026-09")
    assert month.status_code == 200
    assert [item["date"] for item in month.get_json()["data"]["entries"]] == ["2026-09-21"]
    assert client.put("/api/journal/2026-09-21", json={"content": "试图修改"}).status_code == 409
    assert client.put("/api/journal/2026-09-24", json={"content": "未来规划"}).status_code == 409
    assert client.post("/api/journal/2026-09-21/assets", data={}).status_code == 409
    assert client.get("/api/journal/2026-09-21").get_json()["data"]["content"] == "历史内容"
