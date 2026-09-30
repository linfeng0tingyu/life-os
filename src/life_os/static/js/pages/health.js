import { api, ApiError } from "../api/client.js";
import { element, emptyMessage, replace } from "../components/dom.js";
import { ExerciseTypePicker } from "../components/exercise-type-picker.js";
import { longDateLabel, normalizeDate, toLocalDateString } from "../utils/date.js";
import { formatDuration, PERIOD_LABELS, reportRangeLabel, shiftReportAnchor } from "../components/reporting.js";

const SLEEP_STATUS_LABELS = {
  under_4_5: "小于4.5小时",
  between_4_5_6: "4.5-6小时",
  between_6_7_5: "6-7.5小时",
  over_7_5: "大于7.5小时",
  over_9: "大于9小时",
};

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

function optionalNumber(value) {
  return value === "" ? null : Number(value);
}

function displayNumber(value, suffix = "") {
  return value == null ? "—" : `${value}${suffix}`;
}

function selectedRadio(form, name) {
  return form.querySelector(`input[name="${name}"]:checked`)?.value || null;
}

function setRadio(form, name, value) {
  for (const input of form.querySelectorAll(`input[name="${name}"]`)) {
    input.checked = input.value === (value || "");
  }
}

function sleepStatusSummary(counts = {}) {
  const entries = Object.entries(counts).filter(([, count]) => count > 0);
  if (!entries.length) return "未记录";
  return entries.map(([status, count]) => `${SLEEP_STATUS_LABELS[status] || status} ${count}天`).join("；");
}

function exerciseTypeSummary(counts = {}) {
  const entries = Object.entries(counts).filter(([, count]) => count > 0);
  if (!entries.length) return "未记录";
  return entries.map(([name, count]) => `${name} ${count}天`).join("；");
}

export class HealthPage {
  constructor(root) {
    this.root = root;
    this.form = root.querySelector("[data-health-form]");
    this.dateInput = root.querySelector("[data-record-date]");
    this.state = root.querySelector("[data-health-state]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.reportBody = root.querySelector("[data-health-report-body]");
    this.reportRange = root.querySelector("[data-health-report-range]");
    this.reportState = root.querySelector("[data-health-report-state]");
    this.exerciseTypes = new ExerciseTypePicker(root.querySelector("[data-exercise-type-control]"), {
      onChange: () => this.markDirty(),
      onError: (error) => this.showError(error),
    });
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
      if (event.target !== this.dateInput) this.markDirty();
    });
    this.form.addEventListener("change", (event) => {
      if (event.target !== this.dateInput) this.markDirty();
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
    this.exerciseTypes.start();
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
    fields.energy_level.value = record?.energy_level ?? "";
    fields.mood_level.value = record?.mood_level ?? "";
    fields.body_status.value = record?.body_status ?? "";
    fields.exercise_minutes.value = record?.exercise_minutes ?? "";
    fields.note.value = record?.note ?? "";
    setRadio(this.form, "sleep_status", record?.sleep_status);
    this.exerciseTypes.setValue((record?.exercise_types || []).map((item) => item.id));
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
      sleep_status: selectedRadio(this.form, "sleep_status"),
      energy_level: optionalNumber(fields.energy_level.value),
      mood_level: optionalNumber(fields.mood_level.value),
      body_status: fields.body_status.value.trim() || null,
      exercise_minutes: optionalNumber(fields.exercise_minutes.value),
      exercise_type_ids: this.exerciseTypes.getValue(),
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
      ["记录天数", `${summary.recorded_days} 天`],
      ["睡眠情况", `${summary.sleep_status.recorded_days} 天已记录`],
      ["运动总量", formatDuration(summary.exercise.total_minutes)],
      ["运动种类", `${summary.exercise_types.recorded_days} 天已选择`],
      ["体重变化", displayNumber(summary.weight.change_kg, " kg")],
      ["平均精力", displayNumber(summary.energy.average)],
      ["平均情绪", displayNumber(summary.mood.average)],
    ].forEach(([label, value]) => summaryGrid.append(element("div", { className: "report-summary-item" }, [element("span", { text: label }), element("strong", { text: value })])));

    const series = report.series;
    const exerciseValues = series.map((item) => item.exercise_minutes ?? 0);
    const maxValue = Math.max(1, ...exerciseValues);
    const chart = element("div", { className: "report-chart", attrs: { role: "img", "aria-label": "运动时长趋势" } });
    series.forEach((item, index) => {
      const label = item.date?.slice(5) || item.month?.slice(5) || "";
      const exercise = exerciseValues[index];
      chart.append(element("div", { className: "report-bar-group", attrs: { title: `${label}：运动 ${formatDuration(exercise)}` } }, [
        element("div", { className: "report-bars" }, [
          element("i", { className: "report-bar report-bar-accent", attrs: { style: `--report-value:${exercise > 0 ? Math.max(2, exercise / maxValue * 100) : 0}%` } }),
        ]),
        element("span", { text: label }),
      ]));
    });

    const table = element("table", { className: "report-table" });
    table.append(element("thead", {}, [element("tr", {}, ["日期", "睡眠情况", "体重", "运动", "运动种类", "精力", "情绪", "身体状态"].map((label) => element("th", { text: label }))) ]));
    const tbody = element("tbody");
    series.filter((item) => item.recorded || item.recorded_days).forEach((item) => tbody.append(element("tr", {}, [
      item.date || item.month,
      item.date ? (SLEEP_STATUS_LABELS[item.sleep_status] || "—") : sleepStatusSummary(item.sleep_status_counts),
      displayNumber(item.weight_kg ?? item.last_weight_kg ?? item.average_weight_kg, " kg"),
      formatDuration(item.exercise_minutes),
      item.date ? (item.exercise_types?.join("、") || "—") : exerciseTypeSummary(item.exercise_type_counts),
      displayNumber(item.energy_level ?? item.average_energy),
      displayNumber(item.mood_level ?? item.average_mood),
      item.date ? (item.body_status || "—") : (item.body_status_days ? `${item.body_status_days} 天有记录` : "—"),
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
      element("p", { className: "report-note", text: `睡眠情况分布：${sleepStatusSummary(summary.sleep_status.counts)}` }),
      element("p", { className: "report-note", text: `运动种类分布：${exerciseTypeSummary(summary.exercise_types.counts)}` }),
      element("div", { className: "report-legend" }, [element("span", { className: "legend-accent", text: "运动" })]),
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
