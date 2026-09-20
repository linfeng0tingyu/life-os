import { api, ApiError } from "../api/client.js";
import { DaySummary } from "../components/day-summary.js";
import { CalendarFeature } from "../features/calendar.js";
import { longDateLabel, normalizeDate, toLocalDateString } from "../utils/date.js";

function errorText(error) {
  const suffix = error.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error.message}${suffix}`;
}

export class CalendarPage {
  constructor(root) {
    this.root = root;
    this.globalError = root.querySelector("[data-global-error]");
    this.globalErrorMessage = root.querySelector("[data-global-error-message]");
    this.summary = new DaySummary(root);
    this.subtitle = root.querySelector("[data-calendar-subtitle]");
    this.detailKicker = root.querySelector("[data-detail-kicker]");
    this.detailHeading = root.querySelector("[data-detail-heading]");
    this.detailDescription = root.querySelector("[data-detail-description]");
    this.planner = root.querySelector("[data-future-planner]");
    this.plannerHeading = root.querySelector("[data-planner-heading]");
    this.plannerState = root.querySelector("[data-planner-state]");
    this.plannerForm = root.querySelector("[data-planner-form]");
    this.dayRequest = null;
    this.requestSequence = 0;
    const query = new URLSearchParams(window.location.search);
    this.selectedDate = normalizeDate(query.get("date"));
    this.calendar = new CalendarFeature(root, {
      onSelect: (date) => this.selectDate(date, { updateHistory: true }),
      onCalendarChange: () => this.loadDay({ preserveEditor: true }),
    });
  }

  start() {
    this.root.querySelector('[data-action="go-today"]').addEventListener("click", () => this.selectDate(toLocalDateString(), { updateHistory: true }));
    this.root.querySelector('[data-action="retry-day"]').addEventListener("click", () => this.loadDay());
    this.plannerForm.addEventListener("submit", (event) => {
      event.preventDefault();
      this.savePlan();
    });
    window.addEventListener("popstate", () => {
      const value = new URLSearchParams(window.location.search).get("date");
      this.selectDate(normalizeDate(value), { updateHistory: false });
    });
    this.replaceUrlIfInvalid();
    this.updateDateContext();
    this.calendar.initialize(this.selectedDate);
    this.loadDay();
  }

  selectDate(value, { updateHistory }) {
    const normalized = normalizeDate(value, this.selectedDate);
    if (updateHistory && normalized !== this.selectedDate) {
      const url = new URL(window.location.href);
      url.searchParams.set("date", normalized);
      window.history.pushState({}, "", url);
    }
    this.selectedDate = normalized;
    this.updateDateContext();
    this.calendar.setSelectedDate(normalized);
    this.calendar.setEditorLoading();
    this.loadDay();
  }

  async loadDay({ preserveEditor = false } = {}) {
    this.dayRequest?.abort();
    const request = new AbortController();
    this.dayRequest = request;
    const sequence = ++this.requestSequence;
    this.globalError.classList.add("is-hidden");
    this.summary.loading();
    try {
      const day = await api.get(`/api/day/${this.selectedDate}`, { signal: request.signal });
      if (sequence !== this.requestSequence) return;
      this.summary.ready(day);
      if (!preserveEditor) this.calendar.setSelectedDay(day.calendar_day);
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (sequence !== this.requestSequence) return;
      this.summary.error();
      this.calendar.setEditorError();
      this.globalErrorMessage.textContent = errorText(error);
      this.globalError.classList.remove("is-hidden");
    }
  }

  updateDateContext() {
    const today = toLocalDateString();
    const isFuture = this.selectedDate > today;
    const isPast = this.selectedDate < today;
    const label = longDateLabel(this.selectedDate);
    this.detailHeading.textContent = label;
    this.detailKicker.textContent = isFuture ? "未来规划" : isPast ? "历史回顾" : "今天";
    this.detailDescription.textContent = isFuture
      ? "查看这一天已经安排的事项和习惯，并继续补充未来计划。睡眠、日记与财务会在产生记录后显示。"
      : isPast
        ? "完整回看这一天的事项、习惯、睡眠、日记和财务记录。"
        : "完整呈现今天的事项、习惯、睡眠、日记和财务情况。";
    this.subtitle.textContent = isFuture
      ? `正在规划 ${label}。`
      : isPast
        ? `正在回看 ${label} 的生活记录。`
        : "查看今天的完整记录，或选择其他日期。";
    this.planner.classList.toggle("is-hidden", !isFuture);
    if (isFuture) {
      this.plannerHeading.textContent = `安排 ${label}`;
      this.setPlannerState("ready", "可规划");
    }
  }

  async savePlan() {
    const plannedDate = this.selectedDate;
    if (plannedDate <= toLocalDateString()) return;
    const data = new FormData(this.plannerForm);
    const title = String(data.get("title") || "").trim();
    if (!title) return;
    const payload = {
      title,
      priority: String(data.get("priority") || "normal"),
      scheduled_date: plannedDate,
    };
    const category = String(data.get("category") || "").trim();
    if (category) payload.category = category;
    if (data.get("due_on_date")) payload.due_date = plannedDate;
    this.setPlannerDisabled(true);
    this.setPlannerState("saving", "保存中");
    try {
      await api.post("/api/tasks", payload);
      this.plannerForm.reset();
      this.setPlannerState("saved", "已加入计划");
      if (this.selectedDate === plannedDate) {
        await Promise.all([
          this.loadDay({ preserveEditor: true }),
          this.calendar.loadMonth(),
        ]);
      }
    } catch (error) {
      this.setPlannerState("save-failed", `保存失败：${errorText(error)}`);
    } finally {
      this.setPlannerDisabled(false);
    }
  }

  setPlannerDisabled(disabled) {
    for (const control of this.plannerForm.elements) control.disabled = disabled;
  }

  setPlannerState(state, value) {
    this.plannerState.dataset.state = state;
    this.plannerState.textContent = value;
  }

  replaceUrlIfInvalid() {
    const raw = new URLSearchParams(window.location.search).get("date");
    if (raw === this.selectedDate) return;
    const url = new URL(window.location.href);
    url.searchParams.set("date", this.selectedDate);
    window.history.replaceState({}, "", url);
  }
}
