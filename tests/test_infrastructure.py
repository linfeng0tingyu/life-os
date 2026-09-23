from __future__ import annotations

import socket
from pathlib import Path

import pytest

from life_os import create_app
from life_os.instance_lock import InstanceLock, InstanceLockError
from life_os.network import PortUnavailableError, ensure_port_available


def test_health_endpoint_and_log_are_runtime_local(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime"
    app = create_app(runtime_home=runtime_home, testing=True)

    response = app.test_client().get("/api/system/health")

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "ok"
    assert (runtime_home / "logs" / "app.log").is_file()
    assert set(tmp_path.iterdir()) == {runtime_home}


def test_database_engine_points_inside_runtime_and_initializes_database(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime"
    app = create_app(runtime_home=runtime_home, testing=True)
    database_url = app.config["SQLALCHEMY_DATABASE_URI"]

    assert Path(database_url.database) == runtime_home / "database" / "life.db"
    assert (runtime_home / "database" / "life.db").is_file()


def test_api_404_uses_json_contract(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/api/not-found")

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_frontend_shell_supports_versioned_local_assets(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"
    assert '<meta name="life-os-version" content="0.1.0">' in html
    assert "/static/css/tokens.css?v=0.1.0" in html
    assert "/static/css/base.css?v=0.1.0" in html
    assert "/static/css/layout.css?v=0.1.0" in html
    assert "/static/css/components.css?v=0.1.0" in html
    assert "/static/css/pages/today.css?v=0.1.0" in html
    assert "/static/css/pages/calendar.css?v=0.1.0" in html
    assert "/static/css/themes.css?v=0.1.0" in html
    assert "/static/js/theme.js?v=0.1.0" in html
    assert 'type="module" src="/static/js/app.js?v=0.1.0"' in html
    assert 'data-page="today"' in html
    assert 'href="/calendar"' in html
    assert "data-calendar-grid" not in html
    assert "data-day-marker-form" not in html
    assert '<svg class="icon"' in html
    assert 'data-theme-select' in html
    assert 'images/life-os-logo.png?v=0.1.0' in html
    assert "http://" not in html
    assert "https://" not in html


def test_calendar_page_owns_history_and_day_markers(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/calendar")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"
    assert 'data-page="calendar"' in html
    assert "data-calendar-grid" in html
    assert "data-day-overview" in html
    assert "data-task-summary" in html
    assert "data-rhythm-summary" in html
    assert "data-habit-summary" in html
    assert "data-journal-summary" in html
    assert "data-finance-summary" in html
    assert "data-day-marker-form" in html
    assert "data-future-planner" in html
    assert "data-planner-form" in html
    assert "data-month-picker" in html
    assert "选择任意日期" in html
    assert 'href="/calendar" aria-current="page"' in html
    assert "http://" not in html
    assert "https://" not in html


def test_m5_task_and_habit_pages_expose_complete_management_controls(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()

    tasks = client.get("/tasks")
    habits = client.get("/habits")
    task_html = tasks.get_data(as_text=True)
    habit_html = habits.get_data(as_text=True)

    assert tasks.status_code == habits.status_code == 200
    assert 'data-page="tasks"' in task_html
    assert 'data-task-form' in task_html
    assert '<dialog class="editor-dialog" data-task-dialog' in task_html
    assert 'data-action="new-task" aria-haspopup="dialog"' in task_html
    assert 'name="category" data-category-select' in task_html
    assert 'data-action="show-category-creator"' in task_html
    assert 'data-task-list' in task_html
    assert 'name="scheduled_date"' in task_html
    assert 'name="due_date"' in task_html
    assert 'name="parent_id"' in task_html
    assert 'href="/tasks" aria-current="page"' in task_html
    assert 'data-page="habits"' in habit_html
    assert 'data-habit-form' in habit_html
    assert '<dialog class="editor-dialog" data-habit-dialog' in habit_html
    assert 'data-action="new-habit" aria-haspopup="dialog"' in habit_html
    assert 'name="category" data-category-select' in habit_html
    assert 'data-habit-check-list' in habit_html
    assert 'data-habit-list' in habit_html
    assert 'data-habit-date' in habit_html
    assert 'href="/habits" aria-current="page"' in habit_html
    assert "/static/css/pages/management.css?v=0.1.0" in task_html
    assert "http://" not in task_html + habit_html
    assert "https://" not in task_html + habit_html


def test_m5_frontend_guards_repeated_actions_and_uses_existing_apis(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    tasks_script = client.get("/static/js/pages/tasks.js").get_data(as_text=True)
    habits_script = client.get("/static/js/pages/habits.js").get_data(as_text=True)
    summary_script = client.get(
        "/static/js/components/day-summary.js"
    ).get_data(as_text=True)
    category_script = client.get(
        "/static/js/components/category-select.js"
    ).get_data(as_text=True)

    assert "this.pending = new Set()" in tasks_script
    assert "this.pending = new Set()" in habits_script
    assert 'api.post(`/api/tasks/${task.id}/restore`, {})' in tasks_script
    assert 'api.put(`/api/habits/${habit.id}/log/${this.selectedDate}`' in habits_script
    assert "value: log.value" in habits_script
    assert "onTaskStatusChange" in summary_script
    assert "onHabitStatusChange" in summary_script
    assert 'api.post("/api/categories"' in category_script
    assert "this.dialog.showModal()" in tasks_script
    assert "this.dialog.showModal()" in habits_script


def test_m6_pages_expose_health_journal_and_finance_closed_loops(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()

    health_html = client.get("/health?date=2026-09-18").get_data(as_text=True)
    journal_html = client.get("/journal?date=2026-09-18").get_data(as_text=True)
    finance_html = client.get("/finance?date=2026-09-18").get_data(as_text=True)

    assert 'data-page="health"' in health_html
    assert 'data-health-form' in health_html
    assert 'name="sleep_start"' in health_html
    assert 'data-manual-sleep' in health_html
    assert 'href="/health" aria-current="page"' in health_html
    assert 'data-page="journal"' in journal_html
    assert 'data-journal-content' in journal_html
    assert 'data-journal-saved-at' in journal_html
    assert 'data-action="insert-time"' in journal_html
    assert 'data-action="heading-1"' in journal_html
    assert 'data-action="insert-image"' in journal_html
    assert 'data-action="export-journal"' in journal_html
    assert 'data-journal-preview' in journal_html
    assert 'href="/journal" aria-current="page"' in journal_html
    assert 'data-page="finance"' in finance_html
    assert 'data-account-form' in finance_html
    assert 'data-transaction-form' in finance_html
    assert 'data-finance-category-control' in finance_html
    assert 'name="category" data-category-select' in finance_html
    assert 'data-show-inactive' not in finance_html
    assert 'data-finance-totals' in finance_html
    assert 'href="/finance" aria-current="page"' in finance_html
    assert "/static/css/pages/records.css?v=0.1.0" in finance_html


def test_m6_frontend_uses_debounced_saves_and_explicit_finance_submit(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    health_script = client.get("/static/js/pages/health.js").get_data(as_text=True)
    journal_script = client.get("/static/js/pages/journal.js").get_data(as_text=True)
    finance_script = client.get("/static/js/pages/finance.js").get_data(as_text=True)
    summary_script = client.get("/static/js/components/day-summary.js").get_data(as_text=True)

    assert "window.setTimeout(() => this.save(), 800)" in health_script
    assert "sleep_duration_minutes" in health_script
    assert "window.setTimeout(() => this.save(), 1200)" in journal_script
    assert 'window.addEventListener("beforeunload"' in journal_script
    assert "insertCurrentTime()" in journal_script
    assert "applyHeading(level)" in journal_script
    assert "api.upload(`/api/journal/${this.date}/assets`" in journal_script
    assert "renderMarkdownPreview" in journal_script
    assert 'this.accountForm.addEventListener("submit"' in finance_script
    assert 'this.transactionForm.addEventListener("submit"' in finance_script
    assert "this.setDisabled(this.transactionForm, true)" in finance_script
    assert 'scope: "finance"' in finance_script
    assert 'api.delete(`/api/finance/transactions/${transaction.id}`)' in finance_script
    assert '[this.nodes.healthLink, "/health"]' in summary_script
    assert '[this.nodes.journalLink, "/journal"]' in summary_script
    assert '[this.nodes.financeLink, "/finance"]' in summary_script


def test_calendar_go_today_awaits_month_and_day_refresh(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    html = client.get("/calendar").get_data(as_text=True)
    page_script = client.get("/static/js/pages/calendar.js").get_data(as_text=True)
    feature_script = client.get(
        "/static/js/features/calendar.js"
    ).get_data(as_text=True)

    assert '<a class="button button-secondary" href="/">' in html
    assert "回到今日" in html
    assert 'data-action="calendar-today"' in html
    assert "回到今天" in html
    assert 'data-action="go-today"' not in html
    assert "async focusCalendarToday()" in page_script
    assert "await this.selectDate(toLocalDateString()" in page_script
    assert "async setSelectedDate(value)" in feature_script
    assert "await this.loadMonth()" in feature_script


def test_calendar_renders_lunar_dates_and_official_day_badges(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    html = client.get("/calendar").get_data(as_text=True)
    feature_script = client.get(
        "/static/js/features/calendar.js"
    ).get_data(as_text=True)
    lunar_script = client.get("/static/js/utils/lunar.js").get_data(as_text=True)
    styles = client.get("/static/css/pages/calendar.css").get_data(as_text=True)

    assert "法定放假" in html
    assert "调休上班" in html
    assert 'import { lunarLabel } from "../utils/lunar.js"' in feature_script
    assert 'classes.push("is-official")' in feature_script
    assert 'classes.push("is-adjusted-workday")' in feature_script
    assert 'Intl.DateTimeFormat("zh-CN-u-ca-chinese"' in lunar_script
    assert ".calendar-cell .day-number" in styles
    assert "font-size: 1.28rem;" in styles
    assert ".calendar-cell .lunar-label" in styles


def test_theme_switcher_lists_all_visual_variants_without_business_calls(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    html = client.get("/").get_data(as_text=True)
    theme_script = client.get("/static/js/theme.js").get_data(as_text=True)
    theme_styles = client.get("/static/css/themes.css").get_data(as_text=True)

    expected_themes = {
        "default": "默认",
        "bamboo": "古风竹青",
        "indigo": "古风藏青",
        "water": "古风水色",
        "neumorphism": "新拟物派",
        "macos-glass": "macOS 毛玻璃",
        "ghibli": "吉卜力风格",
    }
    for value, label in expected_themes.items():
        assert f'<option value="{value}">{label}</option>' in html
        if value != "default":
            assert f'html[data-theme="{value}"]' in theme_styles

    assert 'const STORAGE_KEY = "life-os.theme"' in theme_script
    assert "window.localStorage" in theme_script
    assert "document.cookie" in theme_script
    assert "SameSite=Strict" in theme_script
    assert "fetch(" not in theme_script
    assert "/api/" not in theme_script
    assert "只改变外观，不改变数据" in html


def test_heritage_palettes_and_finance_semantic_colors_are_explicit(
    tmp_path: Path,
) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    themes = client.get("/static/css/themes.css").get_data(as_text=True)
    tokens = client.get("/static/css/tokens.css").get_data(as_text=True)
    layout = client.get("/static/css/layout.css").get_data(as_text=True)
    records = client.get("/static/css/pages/records.css").get_data(as_text=True)
    finance_script = client.get("/static/js/pages/finance.js").get_data(as_text=True)

    assert "--primary: #789262;" in themes
    assert "--primary: #2e4e7e;" in themes
    assert "--primary: #88ada6;" in themes
    assert "html[data-theme=\"indigo\"] .sidebar" in themes
    assert "--finance-asset:" in tokens
    assert "--finance-liability:" in tokens
    assert "--finance-income:" in tokens
    assert "--finance-expense:" in tokens
    assert "--finance-transfer:" in tokens
    assert "--finance-flow-surface:" in tokens
    assert "--finance-account-surface:" in tokens
    assert ".finance-totals .finance-asset" in records
    assert ".finance-transaction.transaction-expense" in records
    assert "linear-gradient" not in records
    assert "finance-account-${account.kind}" in finance_script
    assert "transaction-${item.type}" in finance_script
    assert "font-size: 1.02rem;" in layout
    assert "font-weight: 800;" in layout


def test_selected_logo_is_served_as_local_png(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get("/static/images/life-os-logo.png")

    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert response.data.startswith(b"\x89PNG\r\n\x1a\n")


def test_future_date_plan_is_visible_in_day_aggregation(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()

    category = client.post(
        "/api/categories", json={"scope": "task", "name": "规划"}
    )
    assert category.status_code == 201

    created = client.post(
        "/api/tasks",
        json={
            "title": "未来规划事项",
            "category": "规划",
            "priority": "high",
            "scheduled_date": "2030-10-08",
            "due_date": "2030-10-08",
        },
    )
    day = client.get("/api/day/2030-10-08")

    assert created.status_code == 201
    assert day.status_code == 200
    data = day.get_json()["data"]
    assert [item["title"] for item in data["tasks"]["scheduled"]] == [
        "未来规划事项"
    ]
    assert [item["title"] for item in data["tasks"]["due"]] == [
        "未来规划事项"
    ]


@pytest.mark.parametrize(
    "asset",
    [
        "css/tokens.css",
        "css/base.css",
        "css/layout.css",
        "css/components.css",
        "css/pages/today.css",
        "css/pages/calendar.css",
        "css/pages/management.css",
        "css/pages/records.css",
        "css/pages/settings.css",
        "css/themes.css",
        "images/life-os-logo.png",
        "js/app.js",
        "js/theme.js",
        "js/api/client.js",
        "js/components/dom.js",
        "js/components/category-select.js",
        "js/components/day-summary.js",
        "js/components/markdown-preview.js",
        "js/features/calendar.js",
        "js/pages/calendar.js",
        "js/pages/habits.js",
        "js/pages/health.js",
        "js/pages/journal.js",
        "js/pages/finance.js",
        "js/pages/tasks.js",
        "js/pages/today.js",
        "js/pages/settings.js",
        "js/utils/date.js",
        "js/utils/lunar.js",
    ],
)
def test_m4_local_frontend_assets_are_served(tmp_path: Path, asset: str) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    response = app.test_client().get(f"/static/{asset}")

    assert response.status_code == 200
    assert response.data


def test_settings_page_exposes_m7_data_protection_controls(tmp_path: Path) -> None:
    app = create_app(runtime_home=tmp_path / "runtime", testing=True)
    client = app.test_client()
    html = client.get("/settings").get_data(as_text=True)
    script = client.get("/static/js/pages/settings.js").get_data(as_text=True)
    styles = client.get("/static/css/pages/settings.css").get_data(as_text=True)

    assert "设置与数据" in html
    assert "立即备份" in html
    assert "导出全部数据" in html
    assert "安排下次启动恢复" in html
    assert 'api.post("/api/system/backup"' in script
    assert 'api.post("/api/system/export"' in script
    assert 'api.post("/api/system/restore"' in script
    assert ".settings-grid" in styles


def test_second_instance_cannot_take_same_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime" / "temp" / "life-os.lock"
    first = InstanceLock(lock_path)
    second = InstanceLock(lock_path)
    first.acquire()
    try:
        with pytest.raises(InstanceLockError):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()


def test_occupied_port_is_rejected() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        with pytest.raises(PortUnavailableError):
            ensure_port_available("127.0.0.1", port)
    finally:
        listener.close()
