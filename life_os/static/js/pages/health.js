import { api, ApiError } from "../api/client.js";
import { longDateLabel, normalizeDate, toLocalDateString } from "../utils/date.js";

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

function localInputValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function awareIso(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function optionalNumber(value) {
  return value === "" ? null : Number(value);
}

export class HealthPage {
  constructor(root) {
    this.root = root;
    this.form = root.querySelector("[data-health-form]");
    this.dateInput = root.querySelector("[data-record-date]");
    this.manualSleep = root.querySelector("[data-manual-sleep]");
    this.sleepHint = root.querySelector("[data-sleep-hint]");
    this.state = root.querySelector("[data-health-state]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.date = normalizeDate(new URLSearchParams(window.location.search).get("date"));
    this.timer = null;
    this.dirty = false;
    this.saving = false;
    this.request = null;
    this.revision = 0;
  }

  start() {
    const today = toLocalDateString();
    if (this.date > today) this.date = today;
    this.dateInput.max = today;
    this.dateInput.value = this.date;
    this.replaceUrl();
    this.dateInput.addEventListener("change", () => this.changeDate());
    this.manualSleep.addEventListener("change", () => {
      this.syncManualControl();
      this.markDirty();
    });
    this.form.addEventListener("input", (event) => {
      if (event.target === this.dateInput || event.target === this.manualSleep) return;
      this.markDirty();
    });
    this.form.addEventListener("change", (event) => {
      if (event.target === this.dateInput || event.target === this.manualSleep) return;
      this.markDirty();
    });
    this.form.addEventListener("focusout", () => {
      if (this.dirty) this.save();
    });
    this.root.querySelector('[data-action="retry-health"]').addEventListener("click", () => this.save());
    this.load();
  }

  async changeDate() {
    const nextDate = normalizeDate(this.dateInput.value, this.date);
    if (nextDate === this.date) return;
    if (this.dirty && !(await this.save())) {
      this.dateInput.value = this.date;
      return;
    }
    this.date = nextDate;
    this.replaceUrl();
    await this.load();
  }

  async load() {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.hideError();
    this.setState("saving", "正在读取");
    this.form.setAttribute("aria-busy", "true");
    try {
      const record = await api.get(`/api/health/${this.date}`, { signal: request.signal });
      if (this.request !== request) return;
      this.fill(record);
      this.dirty = false;
      this.setState("saved", record ? "已载入" : "尚无记录");
      document.title = `${longDateLabel(this.date)} · 生活节律 · Life OS`;
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.request !== request) return;
      this.setState("save-failed", "读取失败");
      this.showError(error);
    } finally {
      if (this.request === request) this.form.setAttribute("aria-busy", "false");
    }
  }

  fill(record) {
    const fields = this.form.elements;
    fields.weight_kg.value = record?.weight_kg ?? "";
    fields.sleep_start.value = localInputValue(record?.sleep_start);
    fields.sleep_end.value = localInputValue(record?.sleep_end);
    fields.sleep_duration_minutes.value = record?.sleep_duration_minutes ?? "";
    fields.sleep_quality.value = record?.sleep_quality ?? "";
    fields.energy_level.value = record?.energy_level ?? "";
    fields.mood_level.value = record?.mood_level ?? "";
    fields.body_status.value = record?.body_status ?? "";
    fields.exercise_minutes.value = record?.exercise_minutes ?? "";
    fields.note.value = record?.note ?? "";
    this.manualSleep.checked = Boolean(record?.sleep_duration_manual);
    this.syncManualControl(record?.sleep_duration_minutes);
  }

  syncManualControl(calculatedValue = null) {
    const duration = this.form.elements.sleep_duration_minutes;
    duration.disabled = !this.manualSleep.checked;
    if (!this.manualSleep.checked && calculatedValue != null) duration.value = calculatedValue;
    this.sleepHint.textContent = this.manualSleep.checked
      ? "当前时长由你手动指定；取消勾选后会根据起止时间重新计算。"
      : "填写起止时间后自动计算，支持跨午夜。";
  }

  markDirty() {
    this.dirty = true;
    this.revision += 1;
    this.setState("saving", "等待保存");
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.save(), 800);
  }

  payload() {
    const fields = this.form.elements;
    return {
      weight_kg: optionalNumber(fields.weight_kg.value),
      sleep_start: awareIso(fields.sleep_start.value),
      sleep_end: awareIso(fields.sleep_end.value),
      sleep_duration_minutes: this.manualSleep.checked ? optionalNumber(fields.sleep_duration_minutes.value) : null,
      sleep_quality: optionalNumber(fields.sleep_quality.value),
      energy_level: optionalNumber(fields.energy_level.value),
      mood_level: optionalNumber(fields.mood_level.value),
      body_status: fields.body_status.value.trim() || null,
      exercise_minutes: optionalNumber(fields.exercise_minutes.value),
      note: fields.note.value.trim() || null,
    };
  }

  async save() {
    window.clearTimeout(this.timer);
    if (this.saving) return false;
    if (!this.dirty) return true;
    if (!this.form.reportValidity()) {
      this.setState("save-failed", "请检查输入");
      return false;
    }
    if (this.manualSleep.checked && this.form.elements.sleep_duration_minutes.value === "") {
      this.form.elements.sleep_duration_minutes.setCustomValidity("请填写手动睡眠时长。");
      this.form.elements.sleep_duration_minutes.reportValidity();
      this.form.elements.sleep_duration_minutes.setCustomValidity("");
      this.setState("save-failed", "请填写睡眠时长");
      return false;
    }
    const date = this.date;
    const revision = this.revision;
    const payload = this.payload();
    let shouldResave = false;
    this.saving = true;
    this.setState("saving", "保存中");
    this.hideError();
    try {
      const record = await api.put(`/api/health/${date}`, payload);
      if (this.date !== date) return true;
      this.dirty = this.revision !== revision;
      if (!this.dirty) {
        this.fill(record);
        this.setState("saved", "已保存");
      } else {
        this.setState("saving", "有新修改");
        shouldResave = true;
      }
      return true;
    } catch (error) {
      this.setState("save-failed", "保存失败");
      this.showError(error);
      return false;
    } finally {
      this.saving = false;
      if (shouldResave) this.timer = window.setTimeout(() => this.save(), 800);
    }
  }

  setState(state, text) {
    this.state.dataset.state = state;
    this.state.textContent = text;
  }

  showError(error) {
    this.errorMessage.textContent = errorText(error);
    this.error.classList.remove("is-hidden");
  }

  hideError() {
    this.error.classList.add("is-hidden");
  }

  replaceUrl() {
    const url = new URL(window.location.href);
    url.searchParams.set("date", this.date);
    window.history.replaceState({}, "", url);
    this.dateInput.value = this.date;
  }
}
