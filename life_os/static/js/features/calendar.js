import { api, ApiError } from "../api/client.js";
import { element, replace } from "../components/dom.js";
import { mondayOffset, monthKey, monthLabel, shiftMonth, toLocalDateString } from "../utils/date.js";
import { lunarLabel } from "../utils/lunar.js";

function errorText(error) {
  const suffix = error.requestId ? `（请求编号：${error.requestId}）` : "";
  return `${error.message}${suffix}`;
}

export class CalendarFeature {
  constructor(root, { onSelect, onCalendarChange }) {
    this.root = root;
    this.onSelect = onSelect;
    this.onCalendarChange = onCalendarChange;
    this.grid = root.querySelector("[data-calendar-grid]");
    this.heading = root.querySelector("[data-month-heading]");
    this.monthPicker = root.querySelector("[data-month-picker]");
    this.error = root.querySelector("[data-calendar-error]");
    this.errorMessage = root.querySelector("[data-calendar-error-message]");
    this.form = root.querySelector("[data-day-marker-form]");
    this.saveState = root.querySelector("[data-save-state]");
    this.clearButton = root.querySelector('[data-action="clear-marker"]');
    this.selectedDate = toLocalDateString();
    this.visibleMonth = monthKey(this.selectedDate);
    this.selectedDay = null;
    this.monthRequest = null;
    this.days = [];
    this.bind();
  }

  bind() {
    this.root.querySelector('[data-action="previous-month"]').addEventListener("click", () => {
      this.visibleMonth = shiftMonth(this.visibleMonth, -1);
      this.loadMonth();
    });
    this.root.querySelector('[data-action="next-month"]').addEventListener("click", () => {
      this.visibleMonth = shiftMonth(this.visibleMonth, 1);
      this.loadMonth();
    });
    this.root.querySelector('[data-action="retry-month"]').addEventListener("click", () => this.loadMonth());
    this.monthPicker?.addEventListener("change", () => {
      if (!/^\d{4}-\d{2}$/.test(this.monthPicker.value)) return;
      this.visibleMonth = this.monthPicker.value;
      this.loadMonth();
    });
    this.grid.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-date]");
      if (button) this.onSelect(button.dataset.date);
    });
    this.form.addEventListener("input", () => this.setSaveState("dirty", "有未保存修改"));
    this.form.addEventListener("submit", (event) => {
      event.preventDefault();
      this.saveMarker();
    });
    this.clearButton.addEventListener("click", () => this.clearMarker());
  }

  initialize(selectedDate) {
    this.selectedDate = selectedDate;
    this.visibleMonth = monthKey(selectedDate);
    this.setEditorLoading();
    return this.loadMonth();
  }

  async setSelectedDate(value) {
    const nextMonth = monthKey(value);
    this.selectedDate = value;
    if (nextMonth !== this.visibleMonth) {
      this.visibleMonth = nextMonth;
      await this.loadMonth();
      return;
    }
    this.render();
  }

  async loadMonth() {
    this.monthRequest?.abort();
    const request = new AbortController();
    this.monthRequest = request;
    this.grid.setAttribute("aria-busy", "true");
    this.error.classList.add("is-hidden");
    this.heading.textContent = monthLabel(this.visibleMonth);
    if (this.monthPicker) this.monthPicker.value = this.visibleMonth;
    try {
      const data = await api.get(`/api/calendar/month/${this.visibleMonth}`, { signal: request.signal });
      if (this.monthRequest !== request) return;
      this.days = data.days;
      this.render();
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      this.days = [];
      replace(this.grid, element("p", { className: "empty-state", text: "月历暂时无法显示。" }));
      this.errorMessage.textContent = errorText(error);
      this.error.classList.remove("is-hidden");
    } finally {
      if (this.monthRequest === request) {
        this.grid.setAttribute("aria-busy", "false");
      }
    }
  }

  render() {
    if (!this.days.length) return;
    const cells = [];
    for (let index = 0; index < mondayOffset(this.visibleMonth); index += 1) {
      cells.push(element("span", { className: "calendar-blank", attrs: { "aria-hidden": "true" } }));
    }
    const today = toLocalDateString();
    for (const day of this.days) {
      const number = String(Number(day.date.slice(-2)));
      const label = day.holiday_name || day.custom_label || "";
      const classes = ["calendar-cell"];
      if (day.day_type === "rest_day") classes.push("is-rest");
      if (day.date === today) classes.push("is-today");
      if (day.date === this.selectedDate) classes.push("is-selected");
      if (day.has_data) classes.push("has-data");
      if (day.source === "official") classes.push("is-official");
      if (day.source === "official" && day.day_type === "workday") classes.push("is-adjusted-workday");
      const habit = day.habit_summary;
      const lunar = lunarLabel(day.date);
      const accessible = [day.date, lunar ? `农历${lunar}` : "", day.day_type === "rest_day" ? "休息日" : "工作日", label, day.source === "official" ? "法定节假日预置" : ""]
        .filter(Boolean)
        .join("，");
      const children = [element("span", { className: "day-number", text: number })];
      if (lunar) children.push(element("span", { className: "lunar-label", text: lunar }));
      if (label) children.push(element("span", { className: "calendar-label", text: label }));
      if (habit.total) children.push(element("span", { className: "habit-mini", text: `${habit.completed}/${habit.total}` }));
      cells.push(element("button", {
        className: classes.join(" "),
        attrs: {
          type: "button",
          "data-date": day.date,
          "aria-label": accessible,
          "aria-pressed": day.date === this.selectedDate ? "true" : "false",
          role: "gridcell",
        },
      }, children));
    }
    replace(this.grid, ...cells);
  }

  setEditorLoading() {
    this.selectedDay = null;
    this.form.setAttribute("aria-busy", "true");
    this.setDisabled(true);
    this.clearButton.classList.add("is-hidden");
    this.setSaveState("loading", "读取中");
  }

  setSelectedDay(day) {
    this.selectedDay = day;
    this.form.elements.day_type.value = day.day_type;
    this.form.elements.holiday_name.value = day.holiday_name || "";
    this.form.elements.custom_label.value = day.custom_label || "";
    this.form.elements.note.value = day.note || "";
    this.form.setAttribute("aria-busy", "false");
    this.setDisabled(false);
    this.clearButton.classList.toggle("is-hidden", !day.explicit);
    this.setSaveState("ready", day.explicit ? "已应用自定义标记" : day.source === "official" ? "使用法定节假日预置" : "使用星期默认值");
  }

  setEditorError() {
    this.form.setAttribute("aria-busy", "false");
    this.setDisabled(true);
    this.setSaveState("save-failed", "日期数据读取失败");
  }

  async saveMarker() {
    if (!this.selectedDay) return;
    const data = new FormData(this.form);
    const payload = {
      day_type: data.get("day_type"),
      holiday_name: String(data.get("holiday_name") || "").trim() || null,
      custom_label: String(data.get("custom_label") || "").trim() || null,
      note: String(data.get("note") || "").trim() || null,
    };
    this.setDisabled(true);
    this.setSaveState("saving", "保存中");
    try {
      const updated = await api.put(`/api/calendar/days/${this.selectedDate}`, payload);
      this.setSelectedDay(updated);
      this.setSaveState("saved", "已保存");
      await this.loadMonth();
      await this.onCalendarChange(updated);
    } catch (error) {
      this.setDisabled(false);
      this.setSaveState("save-failed", `保存失败：${errorText(error)}`);
    }
  }

  async clearMarker() {
    if (!this.selectedDay?.explicit) return;
    this.setDisabled(true);
    this.setSaveState("saving", "恢复中");
    try {
      const result = await api.delete(`/api/calendar/days/${this.selectedDate}`);
      this.setSelectedDay(result.calendar_day);
      this.setSaveState("saved", result.calendar_day.source === "official" ? "已恢复法定节假日预置" : "已恢复星期默认值");
      await this.loadMonth();
      await this.onCalendarChange(result.calendar_day);
    } catch (error) {
      this.setDisabled(false);
      this.setSaveState("save-failed", `恢复失败：${errorText(error)}`);
    }
  }

  setDisabled(disabled) {
    for (const control of this.form.elements) control.disabled = disabled;
  }

  setSaveState(state, text) {
    this.saveState.dataset.state = state;
    this.saveState.textContent = text;
  }
}
