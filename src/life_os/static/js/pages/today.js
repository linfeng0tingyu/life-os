import { api, ApiError } from "../api/client.js";
import { DaySummary } from "../components/day-summary.js";
import { ExerciseTypePicker } from "../components/exercise-type-picker.js";
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
      hideClosedTasks: true,
    });
    this.today = toLocalDateString();
    this.dayRequest = null;
    this.healthForm = root.querySelector("[data-today-health-form]");
    this.healthState = root.querySelector("[data-today-health-save-state]");
    this.healthDirty = false;
    this.healthSaving = false;
    this.healthRevision = 0;
    this.healthTimer = null;
    this.exerciseTypes = new ExerciseTypePicker(root.querySelector("[data-exercise-type-control]"), {
      onChange: () => this.markHealthDirty(),
      onError: (error) => this.showMutationError(error),
    });
  }

  start() {
    this.root.querySelector('[data-action="retry-day"]').addEventListener("click", () => this.loadDay());
    this.heading.textContent = dateHeading(this.today);
    this.subtitle.textContent = longDateLabel(this.today);
    document.title = `${dateHeading(this.today)} · Life OS`;
    this.healthForm.addEventListener("input", () => this.markHealthDirty());
    this.healthForm.addEventListener("change", () => this.markHealthDirty());
    this.healthForm.addEventListener("focusout", () => {
      if (this.healthDirty) this.saveHealth();
    });
    this.exerciseTypes.start();
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
      if (!this.healthDirty) {
        this.fillHealth(day.health);
        this.setHealthState("ready", "可编辑");
      }
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.dayRequest !== request) return;
      this.summary.error();
      this.globalErrorMessage.textContent = errorText(error);
      this.globalError.classList.remove("is-hidden");
    }
  }

  fillHealth(record) {
    const fields = this.healthForm.elements;
    fields.sleep_status.value = record?.sleep_status ?? "";
    fields.energy_level.value = record?.energy_level ?? "";
    fields.mood_level.value = record?.mood_level ?? "";
    this.exerciseTypes.setValue((record?.exercise_types || []).map((item) => item.id));
  }

  markHealthDirty() {
    this.healthDirty = true;
    this.healthRevision += 1;
    this.setHealthState("dirty", "待保存");
    window.clearTimeout(this.healthTimer);
    this.healthTimer = window.setTimeout(() => this.saveHealth(), 800);
  }

  healthPayload() {
    const fields = this.healthForm.elements;
    const optionalNumber = (value) => value === "" ? null : Number(value);
    return {
      sleep_status: fields.sleep_status.value || null,
      exercise_type_ids: this.exerciseTypes.getValue(),
      energy_level: optionalNumber(fields.energy_level.value),
      mood_level: optionalNumber(fields.mood_level.value),
    };
  }

  async saveHealth() {
    window.clearTimeout(this.healthTimer);
    if (this.healthSaving || !this.healthDirty) return;
    if (!this.healthForm.reportValidity()) {
      this.setHealthState("invalid", "请检查输入");
      return;
    }
    const revision = this.healthRevision;
    this.healthSaving = true;
    this.setHealthState("saving", "保存中");
    try {
      const record = await api.put(`/api/health/${this.today}`, this.healthPayload());
      this.healthDirty = this.healthRevision !== revision;
      if (this.healthDirty) {
        this.setHealthState("dirty", "有新修改");
        this.healthTimer = window.setTimeout(() => this.saveHealth(), 800);
      } else {
        this.fillHealth(record);
        this.setHealthState("saved", "已保存");
      }
    } catch (error) {
      this.healthDirty = true;
      this.setHealthState("error", "保存失败");
      this.showMutationError(error);
    } finally {
      this.healthSaving = false;
    }
  }

  setHealthState(state, text) {
    if (!this.healthState) return;
    this.healthState.dataset.state = state;
    this.healthState.textContent = text;
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
