from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
from pathlib import Path
import runpy
import tomllib
from urllib.parse import urlsplit
import zipfile

from flask.testing import FlaskClient

from life_os import __version__, create_app
from life_os.desktop.server import LocalWsgiServer


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_metadata_are_final() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))
    assert __version__ == "0.1.0"
    assert project["project"]["version"] == __version__
    assert project["project"]["license"] == "MIT"
    assert "dev" not in __version__.lower()

    license_text = (PROJECT_ROOT / "LICENSE").read_text("utf-8")
    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 linfeng0tingyu" in license_text
    assert "MIT License](LICENSE)" in (PROJECT_ROOT / "README.md").read_text("utf-8")
    assert 'copy /Y "LICENSE" "dist\\LifeOS\\LICENSE"' in (
        PROJECT_ROOT / "build_desktop.bat"
    ).read_text("utf-8")


def test_theme_preview_query_is_restricted_to_supported_themes() -> None:
    script = (PROJECT_ROOT / "life_os/static/js/theme.js").read_text("utf-8")
    assert 'new URLSearchParams(window.location.search).get("theme")' in script
    assert "if (THEMES.has(preview)) return preview;" in script


def test_github_readme_references_logo_and_all_theme_screenshots() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text("utf-8")
    assets = [
        "design-assets/logo-concepts/"
        "life-os-logo-02a-ref-a-full-landscape-contained.png",
        "docs/images/themes/default.png",
        "docs/images/themes/bamboo.png",
        "docs/images/themes/indigo.png",
        "docs/images/themes/water.png",
        "docs/images/themes/neumorphism.png",
        "docs/images/themes/macos-glass.png",
        "docs/images/themes/ghibli.png",
    ]
    for asset in assets:
        assert asset in readme
        assert (PROJECT_ROOT / asset).is_file()


def test_release_packager_creates_rooted_zip_and_checksum(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source = project / "dist" / "LifeOS"
    source.mkdir(parents=True)
    (source / "LifeOS.exe").write_bytes(b"portable-executable")
    (source / "LICENSE").write_text("MIT License", encoding="utf-8")
    (source / "README.md").write_text("Life OS", encoding="utf-8")
    package_release = runpy.run_path(
        str(PROJECT_ROOT / "scripts/package_release.py")
    )["package_release"]

    archive, checksum = package_release(project, "0.1.0")

    with zipfile.ZipFile(archive) as bundle:
        assert sorted(bundle.namelist()) == [
            "LifeOS/LICENSE",
            "LifeOS/LifeOS.exe",
            "LifeOS/README.md",
        ]
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert checksum.read_text("ascii") == f"{expected}  {archive.name}\n"


def test_waitress_serves_concurrent_loopback_requests(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    server = LocalWsgiServer(app, startup_timeout=3.0)
    server.start()
    parsed = urlsplit(server.url)

    def request_health(_index: int) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
        try:
            connection.request("GET", "/api/system/health")
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(request_health, range(24)))
    finally:
        server.stop()

    assert all(status == 200 for status, _body in results)
    assert all(b'"status":"ok"' in body for _status, body in results)


def test_m8_core_journey_reaches_backup_and_open_export(
    client: FlaskClient,
) -> None:
    task_category = client.post(
        "/api/categories", json={"scope": "task", "name": "发布"}
    )
    assert task_category.status_code == 201
    task = client.post(
        "/api/tasks",
        json={
            "title": "发布 v0.1",
            "category": "发布",
            "scheduled_date": "2026-09-23",
        },
    )
    assert task.status_code == 201

    habit = client.post("/api/habits", json={"name": "复盘"}).get_json()["data"]
    assert client.put(
        f"/api/habits/{habit['id']}/log/2026-09-23", json={"status": True}
    ).status_code == 200
    assert client.put(
        "/api/health/2026-09-23",
        json={"sleep_duration_minutes": 450, "energy_level": 4},
    ).status_code == 200
    assert client.put(
        "/api/journal/2026-09-23", json={"content": "# v0.1 发布日"}
    ).status_code == 200

    account = client.post(
        "/api/finance/accounts",
        json={
            "name": "银行卡",
            "kind": "asset",
            "account_type": "bank",
            "opening_balance": "100.00",
        },
    ).get_json()["data"]
    assert client.post(
        "/api/finance/transactions",
        json={
            "date": "2026-09-23",
            "type": "income",
            "amount": "50.00",
            "to_account_id": account["id"],
        },
    ).status_code == 201

    day = client.get("/api/day/2026-09-23").get_json()["data"]
    assert day["tasks"]["scheduled"][0]["title"] == "发布 v0.1"
    assert day["habits"][0]["log"]["status"] is True
    assert day["health"]["sleep_duration_minutes"] == 450
    assert day["journal"]["content"] == "# v0.1 发布日"
    assert day["finance"]["income"] == "50.00"

    assert client.post("/api/system/backup", json={}).status_code == 201
    exported = client.post("/api/system/export", json={"include_zip": True})
    assert exported.status_code == 201
    assert exported.get_json()["data"]["zip_relative_path"].endswith(".zip")
