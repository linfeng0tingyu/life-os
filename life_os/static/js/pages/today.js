import { api, ApiError } from "../api/client.js";
import { DaySummary } from "../components/day-summary.js";
import { CalendarFeature } from "../features/calendar.js";
import { dateHeading, longDateLabel, normalizeDate, toLocalDateString } from "../utils/date.js";

function errorText(error) {
  const suffix = error.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error.message}${suffix}`;
}

export class TodayPage {
  constructor(root) {
    this.root = root;
    this.heading = root.querySelector("[data-date-heading]");
    this.subtitle = root.querySelector("[data-date-subtitle]");
    this.globalError = root.querySelector("[data-global-error]");
    this.globalErrorMessage = root.querySelector("[data-global-error-message]");
    this.summary = new DaySummary(root);
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
    this.root.querySelector('[data-action="go-today"]').addEventListener("click", () => {
      this.selectDate(toLocalDateString(), { updateHistory: true });
    });
    this.root.querySelector('[data-action="retry-day"]').addEventListener("click", () => this.loadDay());
    window.addEventListener("popstate", () => {
      const value = new URLSearchParams(window.location.search).get("date");
      this.selectDate(normalizeDate(value), { updateHistory: false });
    });
    this.updateHeading();
    this.replaceUrlIfInvalid();
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
    this.updateHeading();
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

  updateHeading() {
    this.heading.textContent = dateHeading(this.selectedDate);
    this.subtitle.textContent = longDateLabel(this.selectedDate);
    document.title = `${dateHeading(this.selectedDate)} · Life OS`;
  }

  replaceUrlIfInvalid() {
    const raw = new URLSearchParams(window.location.search).get("date");
    if (raw === this.selectedDate) return;
    const url = new URL(window.location.href);
    url.searchParams.set("date", this.selectedDate);
    window.history.replaceState({}, "", url);
  }
}
