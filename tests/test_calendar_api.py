from __future__ import annotations

from flask.testing import FlaskClient


def test_month_returns_every_day_with_weekday_inference(client: FlaskClient) -> None:
    response = client.get("/api/calendar/month/2026-09")
    assert response.status_code == 200
    days = response.get_json()["data"]["days"]
    assert len(days) == 30
    assert [day["date"] for day in days] == sorted(day["date"] for day in days)
    assert days[0]["day_type"] == "workday"
    assert days[0]["explicit"] is False
    assert next(day for day in days if day["date"] == "2026-09-05")[
        "day_type"
    ] == "rest_day"


def test_calendar_override_update_and_clear(client: FlaskClient) -> None:
    created = client.put(
        "/api/calendar/days/2026-09-05",
        json={
            "day_type": "workday",
            "holiday_name": "调休",
            "custom_label": "项目冲刺",
            "note": "上午工作",
        },
    )
    assert created.status_code == 200
    assert created.get_json()["data"]["explicit"] is True

    updated = client.put(
        "/api/calendar/days/2026-09-05",
        json={"day_type": "rest_day", "custom_label": "家庭日"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["custom_label"] == "家庭日"

    month_day = next(
        day
        for day in client.get("/api/calendar/month/2026-09").get_json()["data"][
            "days"
        ]
        if day["date"] == "2026-09-05"
    )
    assert month_day["explicit"] is True
    assert month_day["source"] == "manual"

    cleared = client.delete("/api/calendar/days/2026-09-05")
    assert cleared.status_code == 200
    inferred = cleared.get_json()["data"]["calendar_day"]
    assert inferred["explicit"] is False
    assert inferred["day_type"] == "rest_day"
    assert client.delete("/api/calendar/days/2026-09-05").status_code == 404


def test_calendar_validates_month_and_payload(client: FlaskClient) -> None:
    assert client.get("/api/calendar/month/2026-13").status_code == 400
    assert client.get("/api/calendar/month/2026-9").status_code == 400
    assert (
        client.put(
            "/api/calendar/days/2026-09-01", json={"day_type": "holiday"}
        ).status_code
        == 400
    )
