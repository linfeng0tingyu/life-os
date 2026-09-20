import { api, ApiError } from "../api/client.js";
import { DaySummary } from "../components/day-summary.js";
import { dateHeading, longDateLabel, toLocalDateString } from "../utils/date.js";

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
    this.summary = new DaySummary(root, {
      onTaskStatusChange: (task, status) => this.updateTaskStatus(task, status),
      onHabitStatusChange: (habit, log) => this.updateHabitStatus(habit, log),
    });
    this.today = toLocalDateString();
    this.dayRequest = null;
  }

  start() {
    this.root.querySelector('[data-action="retry-day"]').addEventListener("click", () => this.loadDay());
    this.heading.textContent = dateHeading(this.today);
    this.subtitle.textContent = longDateLabel(this.today);
    document.title = `${dateHeading(this.today)} · Life OS`;
    this.loadDay();
  }

  async loadDay() {
    this.dayRequest?.abort();
    const request = new AbortController();
    this.dayRequest = request;
    this.globalError.classList.add("is-hidden");
    this.summary.loading();
    try {
      const day = await api.get(`/api/day/${this.today}`, { signal: request.signal });
      if (this.dayRequest !== request) return;
      this.summary.ready(day);
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.dayRequest !== request) return;
      this.summary.error();
      this.globalErrorMessage.textContent = errorText(error);
      this.globalError.classList.remove("is-hidden");
    }
  }

  async updateTaskStatus(task, status) {
    try {
      await api.put(`/api/tasks/${task.id}`, { status });
      await this.loadDay();
    } catch (error) {
      this.showMutationError(error);
      throw error;
    }
  }

  async updateHabitStatus(habit, log) {
    try {
      await api.put(`/api/habits/${habit.id}/log/${this.today}`, {
        status: !log.status,
        value: log.value,
        value_unit: log.value_unit,
        note: log.note,
      });
      await this.loadDay();
    } catch (error) {
      this.showMutationError(error);
      throw error;
    }
  }

  showMutationError(error) {
    this.globalErrorMessage.textContent = errorText(error);
    this.globalError.classList.remove("is-hidden");
  }
}
