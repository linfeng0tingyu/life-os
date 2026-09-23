import { api, ApiError } from "../api/client.js";
import { element, emptyMessage, replace } from "../components/dom.js";
import { longDateLabel, normalizeDate, parseLocalDate, toLocalDateString } from "../utils/date.js";
import { formatDuration, PERIOD_LABELS, reportRangeLabel, shiftReportAnchor } from "../components/reporting.js";

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

function timeInputValue(value) {
  if (!value) return "";
  const match = String(value).match(/T(\d{2}:\d{2})/);
  if (match) return match[1];
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return `${String(parsed.getHours()).padStart(2, "0")}:${String(parsed.getMinutes()).padStart(2, "0")}`;
}

function optionalNumber(value) {
  return value === "" ? null : Number(value);
}

function previousDaySleepTimestamp(recordDate, start) {
  if (!start) return null;
  const base = parseLocalDate(recordDate);
  const [hours, minutes] = start.split(":").map(Number);
  base.setDate(base.getDate() - 1);
  base.setHours(hours, minutes, 0, 0);
  const pad = (value) => String(value).padStart(2, "0");
  const offsetMinutes = -base.getTimezoneOffset();
  const offsetSign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteOffset = Math.abs(offsetMinutes);
  const offset = `${offsetSign}${pad(Math.floor(absoluteOffset / 60))}:${pad(absoluteOffset % 60)}`;
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}T${start}:00${offset}`;
}

function displayNumber(value, suffix = "") {
  return value == null ? "—" : `${value}${suffix}`;
}

export class HealthPage {
  constructor(root) {
    this.root = root;
    this.form = root.querySelector("[data-health-form]");
    this.dateInput = root.querySelector("[data-record-date]");
    this.durationDisplay = root.querySelector("[data-sleep-duration-display]");
    this.state = root.querySelector("[data-health-state]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.reportBody = root.querySelector("[data-health-report-body]");
    this.reportRange = root.querySelector("[data-health-report-range]");
    this.reportState = root.querySelector("[data-health-report-state]");
    this.date = normalizeDate(new URLSearchParams(window.location.search).get("date"));
    this.reportPeriod = "week";
    this.reportAnchor = toLocalDateString();
    this.timer = null;
    this.dirty = false;
    this.saving = false;
    this.request = null;
    this.reportRequest = null;
    this.revision = 0;
  }

  start() {
    const today = toLocalDateString();
    if (this.date > today) this.date = today;
    this.dateInput.max = today;
    this.dateInput.value = this.date;
    this.replaceUrl();
    this.dateInput.addEventListener("change", () => this.changeDate());
    this.form.addEventListener("input", (event) => {
      if (event.target === this.dateInput) return;
      if (["sleep_duration_hours", "sleep_duration_remainder"].includes(event.target.name)) this.updateDurationDisplay();
      this.markDirty();
    });
    this.form.addEventListener("change", (event) => {
      if (event.target === this.dateInput) return;
      this.markDirty();
    });
    this.form.addEventListener("focusout", () => {
      if (this.dirty) this.save();
    });
    this.root.querySelector('[data-action="retry-health"]').addEventListener("click", () => this.save());
    this.root.querySelectorAll("[data-report-period]").forEach((button) => {
      button.addEventListener("click", () => this.setReportPeriod(button.dataset.reportPeriod));
    });
    this.root.querySelector('[data-action="previous-health-report"]').addEventListener("click", () => this.moveReport(-1));
    this.root.querySelector('[data-action="current-health-report"]').addEventListener("click", () => {
      this.reportAnchor = toLocalDateString();
      this.loadReport();
    });
    this.root.querySelector('[data-action="next-health-report"]').addEventListener("click", () => this.moveReport(1));
    this.load();
    this.loadReport();
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
    fields.sleep_start.value = timeInputValue(record?.sleep_start);
    const duration = record?.sleep_duration_minutes;
    fields.sleep_duration_hours.value = duration == null ? "" : Math.floor(duration / 60);
    fields.sleep_duration_remainder.value = duration == null ? "" : duration % 60;
    fields.sleep_quality.value = record?.sleep_quality ?? "";
    fields.energy_level.value = record?.energy_level ?? "";
    fields.mood_level.value = record?.mood_level ?? "";
    fields.body_status.value = record?.body_status ?? "";
    fields.exercise_minutes.value = record?.exercise_minutes ?? "";
    fields.note.value = record?.note ?? "";
    this.updateDurationDisplay();
  }

  currentDuration() {
    const fields = this.form.elements;
    const hours = optionalNumber(fields.sleep_duration_hours.value);
    const minutes = optionalNumber(fields.sleep_duration_remainder.value);
    if (hours == null && minutes == null) return null;
    return (hours || 0) * 60 + (minutes || 0);
  }

  updateDurationDisplay() {
    const duration = this.currentDuration();
    this.durationDisplay.textContent = duration == null ? "尚未记录睡眠时长" : `睡眠时长：${formatDuration(duration)}`;
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
      sleep_start: previousDaySleepTimestamp(this.date, fields.sleep_start.value),
      sleep_duration_minutes: this.currentDuration(),
      sleep_quality: optionalNumber(fields.sleep_quality.value),
      energy_level: optionalNumber(fields.energy_level.value),
      mood_level: optionalNumber(fields.mood_level.value),
      body_status: fields.body_status.value.trim() || null,
      exercise_minutes: optionalNumber(fields.exercise_minutes.value),
      note: fields.note.value.trim() || null,
    };
  }

  validDuration() {
    const fields = this.form.elements;
    if (this.currentDuration() > 1440) {
      fields.sleep_duration_hours.setCustomValidity("睡眠时长不能超过 24 小时。");
      fields.sleep_duration_hours.reportValidity();
      fields.sleep_duration_hours.setCustomValidity("");
      return false;
    }
    return true;
  }

  async save() {
    window.clearTimeout(this.timer);
    if (this.saving) return false;
    if (!this.dirty) return true;
    if (!this.form.reportValidity() || !this.validDuration()) {
      this.setState("save-failed", "请检查输入");
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
        this.loadReport();
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

  setReportPeriod(period) {
    if (!PERIOD_LABELS[period] || period === this.reportPeriod) return;
    this.reportPeriod = period;
    this.reportAnchor = toLocalDateString();
    this.root.querySelectorAll("[data-report-period]").forEach((button) => {
      const selected = button.dataset.reportPeriod === period;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("button-secondary", selected);
      button.classList.toggle("button-quiet", !selected);
    });
    this.loadReport();
  }

  moveReport(amount) {
    this.reportAnchor = shiftReportAnchor(this.reportAnchor, this.reportPeriod, amount);
    this.loadReport();
  }

  async loadReport() {
    this.reportRequest?.abort();
    const request = new AbortController();
    this.reportRequest = request;
    this.reportState.textContent = "加载中";
    this.reportBody.setAttribute("aria-busy", "true");
    try {
      const report = await api.get(`/api/health/statistics?period=${this.reportPeriod}&anchor=${this.reportAnchor}`, { signal: request.signal });
      if (this.reportRequest !== request) return;
      this.renderReport(report);
      this.reportState.textContent = `${PERIOD_LABELS[this.reportPeriod]}报表已更新`;
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.reportRequest !== request) return;
      replace(this.reportBody, emptyMessage(errorText(error)));
      this.reportState.textContent = "加载失败";
    } finally {
      if (this.reportRequest === request) this.reportBody.setAttribute("aria-busy", "false");
    }
  }

  renderReport(report) {
    this.reportRange.textContent = `${reportRangeLabel(report)} · 仅统计已发生日期，空缺日不补值`;
    const summary = report.summary;
    const summaryGrid = element("div", { className: "report-summary" });
    [
      ["平均睡眠", formatDuration(summary.sleep.average_minutes)],
      ["运动总量", formatDuration(summary.exercise.total_minutes)],
      ["最新体重", displayNumber(summary.weight.last_kg, " kg")],
      ["体重变化", summary.weight.change_kg == null ? "—" : `${summary.weight.change_kg > 0 ? "+" : ""}${summary.weight.change_kg} kg`],
      ["记录天数", `${summary.recorded_days} 天`],
      ["身体记录", `${summary.body_status.recorded_days} 天`],
    ].forEach(([label, value]) => summaryGrid.append(element("div", { className: "report-stat" }, [
      element("span", { text: label }),
      element("strong", { text: value }),
    ])));

    const series = report.series || [];
    const sleepValues = series.map((item) => item.sleep_minutes ?? item.average_sleep_minutes ?? 0);
    const exerciseValues = series.map((item) => item.exercise_minutes ?? 0);
    const maxValue = Math.max(1, ...sleepValues, ...exerciseValues);
    const chart = element("div", { className: "report-chart", attrs: { role: "img", "aria-label": "睡眠与运动趋势" } });
    series.forEach((item, index) => {
      const label = item.date?.slice(5) || item.month?.slice(5) || "";
      const sleep = sleepValues[index];
      const exercise = exerciseValues[index];
      chart.append(element("div", { className: "report-bar-group", attrs: { title: `${label}：睡眠 ${formatDuration(sleep)}，运动 ${formatDuration(exercise)}` } }, [
        element("div", { className: "report-bars" }, [
          element("i", { className: "report-bar report-bar-primary", attrs: { style: `--report-value:${sleep > 0 ? Math.max(2, sleep / maxValue * 100) : 0}%` } }),
          element("i", { className: "report-bar report-bar-accent", attrs: { style: `--report-value:${exercise > 0 ? Math.max(2, exercise / maxValue * 100) : 0}%` } }),
        ]),
        element("small", { text: label }),
      ]));
    });

    const table = element("table", { className: "report-table" });
    table.append(element("thead", {}, [element("tr", {}, ["日期", "睡眠", "睡眠质量", "体重", "运动", "精力", "情绪"].map((label) => element("th", { text: label }))) ]));
    const tbody = element("tbody");
    series.forEach((item) => tbody.append(element("tr", {}, [
      item.date || item.month,
      formatDuration(item.sleep_minutes ?? item.average_sleep_minutes),
      displayNumber(item.sleep_quality ?? item.average_sleep_quality),
      displayNumber(item.weight_kg ?? item.last_weight_kg ?? item.average_weight_kg, " kg"),
      formatDuration(item.exercise_minutes),
      displayNumber(item.energy_level ?? item.average_energy),
      displayNumber(item.mood_level ?? item.average_mood),
    ].map((value) => element("td", { text: value })))));
    table.append(tbody);

    const recentBody = summary.body_status.recent.length
      ? element("div", { className: "report-recent" }, [
          element("h3", { text: "近期身体健康记录" }),
          element("ul", {}, summary.body_status.recent.map((item) => element("li", {}, [
            element("time", { text: item.date, attrs: { datetime: item.date } }),
            element("span", { text: item.text }),
          ]))),
        ])
      : element("p", { className: "report-note", text: "本期没有身体健康文字记录。" });
    replace(this.reportBody, element("div", { className: "report-content" }, [
      summaryGrid,
      element("div", { className: "report-legend" }, [element("span", { className: "legend-primary", text: "睡眠" }), element("span", { className: "legend-accent", text: "运动" })]),
      chart,
      element("div", { className: "report-table-wrap" }, [table]),
      recentBody,
    ]));
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
