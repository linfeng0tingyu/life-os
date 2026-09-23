import { api, ApiError } from "../api/client.js";
import { element, replace } from "../components/dom.js";
import { renderMarkdownPreview } from "../components/markdown-preview.js";
import {
  longDateLabel,
  mondayOffset,
  monthKey,
  monthLabel,
  normalizeDate,
  parseLocalDate,
  shiftMonth,
  toLocalDateString,
} from "../utils/date.js";

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

export class JournalPage {
  constructor(root) {
    this.root = root;
    this.dateInput = root.querySelector("[data-record-date]");
    this.content = root.querySelector("[data-journal-content]");
    this.state = root.querySelector("[data-journal-state]");
    this.dateLabel = root.querySelector("[data-journal-date-label]");
    this.editorTitle = root.querySelector("[data-journal-editor-title]");
    this.editorPane = root.querySelector("[data-journal-editor-pane]");
    this.workspace = root.querySelector(".journal-workspace");
    this.count = root.querySelector("[data-journal-count]");
    this.savedAt = root.querySelector("[data-journal-saved-at]");
    this.preview = root.querySelector("[data-journal-preview]");
    this.imageInput = root.querySelector("[data-journal-image]");
    this.editActions = [...root.querySelectorAll("[data-journal-edit-action]")];
    this.exportButton = root.querySelector('[data-action="export-journal"]');
    this.retryButton = root.querySelector('[data-action="retry-journal"]');
    this.calendar = root.querySelector("[data-journal-calendar]");
    this.monthLabel = root.querySelector("[data-journal-month-label]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.today = toLocalDateString();
    this.date = normalizeDate(new URLSearchParams(window.location.search).get("date"));
    this.visibleMonth = monthKey(this.date);
    this.timer = null;
    this.dirty = false;
    this.saving = false;
    this.request = null;
    this.calendarRequest = null;
    this.hasRecord = false;
  }

  start() {
    this.dateInput.value = this.date;
    this.replaceUrl();
    this.dateInput.addEventListener("change", () => this.selectDate(normalizeDate(this.dateInput.value, this.date)));
    this.content.addEventListener("input", () => this.markDirty());
    this.content.addEventListener("blur", () => {
      if (this.dirty) this.save();
    });
    this.retryButton.addEventListener("click", () => this.save());
    this.root.querySelector('[data-action="insert-time"]').addEventListener("click", () => this.insertCurrentTime());
    for (const level of [1, 2, 3]) {
      this.root.querySelector(`[data-action="heading-${level}"]`).addEventListener("click", () => this.applyHeading(level));
    }
    this.root.querySelector('[data-action="insert-image"]').addEventListener("click", () => this.imageInput.click());
    this.exportButton.addEventListener("click", () => this.exportJournal());
    this.imageInput.addEventListener("change", () => this.uploadImage());
    this.root.querySelector('[data-action="previous-journal-month"]').addEventListener("click", () => this.changeMonth(-1));
    this.root.querySelector('[data-action="next-journal-month"]').addEventListener("click", () => this.changeMonth(1));
    this.root.querySelector('[data-action="journal-today"]').addEventListener("click", () => this.selectDate(toLocalDateString()));
    window.addEventListener("beforeunload", (event) => {
      if (!this.dirty && !this.saving) return;
      event.preventDefault();
      event.returnValue = "";
    });
    window.addEventListener("focus", () => {
      const nextToday = toLocalDateString();
      if (nextToday === this.today) return;
      this.today = nextToday;
      this.applyMode();
      this.loadCalendar();
    });
    this.load();
    this.loadCalendar();
  }

  isEditable() {
    return this.date === this.today;
  }

  async selectDate(nextDate) {
    if (!nextDate || nextDate === this.date) return;
    if (this.dirty && !(await this.save())) {
      this.dateInput.value = this.date;
      return;
    }
    this.date = nextDate;
    this.visibleMonth = monthKey(nextDate);
    this.replaceUrl();
    await Promise.all([this.load(), this.loadCalendar()]);
  }

  changeMonth(amount) {
    this.visibleMonth = shiftMonth(this.visibleMonth, amount);
    this.loadCalendar();
  }

  async loadCalendar() {
    this.calendarRequest?.abort();
    const request = new AbortController();
    this.calendarRequest = request;
    this.monthLabel.textContent = monthLabel(this.visibleMonth);
    this.calendar.setAttribute("aria-busy", "true");
    try {
      const data = await api.get(`/api/journal/month/${this.visibleMonth}`, { signal: request.signal });
      if (this.calendarRequest !== request) return;
      this.renderCalendar(data.entries || []);
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.calendarRequest !== request) return;
      replace(this.calendar, element("p", { className: "empty-state journal-calendar-error", text: errorText(error) }));
    } finally {
      if (this.calendarRequest === request) this.calendar.setAttribute("aria-busy", "false");
    }
  }

  renderCalendar(entries) {
    const [year, month] = this.visibleMonth.split("-").map(Number);
    const days = new Date(year, month, 0).getDate();
    const recorded = new Set(entries.map((entry) => entry.date));
    const nodes = [];
    for (let index = 0; index < mondayOffset(this.visibleMonth); index += 1) {
      nodes.push(element("span", { className: "journal-calendar-blank", attrs: { "aria-hidden": "true" } }));
    }
    for (let day = 1; day <= days; day += 1) {
      const value = `${this.visibleMonth}-${String(day).padStart(2, "0")}`;
      const classes = ["journal-calendar-day"];
      if (value === this.date) classes.push("is-selected");
      if (value === this.today) classes.push("is-today");
      if (recorded.has(value)) classes.push("has-record");
      const button = element("button", {
        className: classes.join(" "),
        text: String(day),
        attrs: {
          type: "button",
          "aria-label": `${longDateLabel(value)}${recorded.has(value) ? "，有记录" : "，无记录"}`,
          "aria-pressed": String(value === this.date),
        },
      });
      button.addEventListener("click", () => this.selectDate(value));
      nodes.push(button);
    }
    replace(this.calendar, ...nodes);
  }

  async load() {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.hideError();
    this.setState("saving", "正在读取");
    this.content.disabled = true;
    try {
      const journal = await api.get(`/api/journal/${this.date}`, { signal: request.signal });
      if (this.request !== request) return;
      this.content.value = journal?.content || "";
      this.hasRecord = Boolean(journal);
      this.dirty = false;
      this.updateContext();
      this.setState("saved", journal ? "已载入" : this.isEditable() ? "尚无日记" : "只读 · 无记录");
      this.savedAt.textContent = journal?.updated_at ? `上次保存 ${this.timeLabel(journal.updated_at)}` : "尚未保存";
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.request !== request) return;
      this.setState("save-failed", "读取失败");
      this.showError(error);
    } finally {
      if (this.request === request) {
        this.content.disabled = false;
        this.applyMode();
        if (this.isEditable()) this.content.focus();
      }
    }
  }

  applyMode() {
    const editable = this.isEditable();
    this.content.readOnly = !editable;
    this.editActions.forEach((button) => { button.disabled = !editable; });
    this.retryButton.disabled = !editable;
    this.editorPane.classList.toggle("is-hidden", !editable);
    this.workspace.classList.toggle("is-readonly", !editable);
    this.editorTitle.textContent = editable ? "今日文字" : this.date < this.today ? "历史记录" : "未来日期";
    this.exportButton.disabled = !this.hasRecord && !editable;
  }

  markDirty() {
    if (!this.isEditable()) return;
    this.dirty = true;
    this.updateCount();
    this.setState("saving", "等待保存");
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.save(), 1200);
  }

  async save() {
    window.clearTimeout(this.timer);
    if (!this.isEditable()) return !this.dirty;
    if (this.saving) return false;
    if (!this.dirty) return true;
    const date = this.date;
    const content = this.content.value;
    let shouldResave = false;
    this.saving = true;
    this.setState("saving", "保存中");
    this.hideError();
    try {
      const journal = await api.put(`/api/journal/${date}`, { content });
      if (this.date !== date) return true;
      this.dirty = this.content.value !== content;
      shouldResave = this.dirty;
      this.savedAt.textContent = `已保存于 ${this.timeLabel(journal.updated_at)}`;
      this.hasRecord = true;
      this.applyMode();
      this.setState(this.dirty ? "saving" : "saved", this.dirty ? "有新修改" : "已保存");
      await this.loadCalendar();
      return true;
    } catch (error) {
      this.setState("save-failed", "保存失败");
      this.showError(error);
      return false;
    } finally {
      this.saving = false;
      if (shouldResave) this.timer = window.setTimeout(() => this.save(), 1200);
    }
  }

  updateContext() {
    const label = longDateLabel(this.date);
    this.dateLabel.textContent = label;
    document.title = `${label} · 日记 · Life OS`;
    this.updateCount();
    this.applyMode();
  }

  updateCount() {
    this.count.textContent = `${this.content.value.length} 字符`;
    renderMarkdownPreview(this.preview, this.content.value);
  }

  insertCurrentTime() {
    if (!this.isEditable()) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    this.insertText(time);
  }

  applyHeading(level) {
    if (!this.isEditable()) return;
    const start = this.content.selectionStart;
    const end = this.content.selectionEnd;
    const lineStart = this.content.value.lastIndexOf("\n", start - 1) + 1;
    const nextBreak = this.content.value.indexOf("\n", end);
    const lineEnd = nextBreak === -1 ? this.content.value.length : nextBreak;
    const selectedLines = this.content.value.slice(lineStart, lineEnd);
    const prefix = `${"#".repeat(level)} `;
    const replacement = selectedLines.split("\n").map((line) => `${prefix}${line.replace(/^#{1,6}\s*/, "")}`).join("\n");
    this.content.setRangeText(replacement, lineStart, lineEnd, "select");
    this.markDirty();
    this.content.focus();
  }

  insertText(text) {
    if (!this.isEditable()) return;
    const start = this.content.selectionStart;
    const end = this.content.selectionEnd;
    this.content.setRangeText(text, start, end, "end");
    this.markDirty();
    this.content.focus();
  }

  async uploadImage() {
    if (!this.isEditable()) return;
    const file = this.imageInput.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      this.showError(new Error("单张图片不能超过 5 MB。"));
      this.imageInput.value = "";
      return;
    }
    this.setState("saving", "图片上传中");
    this.hideError();
    try {
      const formData = new FormData();
      formData.append("image", file);
      const asset = await api.upload(`/api/journal/${this.date}/assets`, formData);
      const alt = asset.original_name.replace(/[\[\]]/g, "");
      const needsLeadingBreak = this.content.selectionStart > 0 && !this.content.value.slice(0, this.content.selectionStart).endsWith("\n");
      this.insertText(`${needsLeadingBreak ? "\n" : ""}![${alt}](${asset.url})\n`);
    } catch (error) {
      this.setState("save-failed", "图片插入失败");
      this.showError(error);
    } finally {
      this.imageInput.value = "";
    }
  }

  async exportJournal() {
    if (!this.hasRecord) {
      if (!this.isEditable()) return;
      this.dirty = true;
    }
    if (this.dirty && !(await this.save())) return;
    const link = document.createElement("a");
    link.href = `/api/journal/${this.date}/export`;
    link.download = `${this.date}.md`;
    document.body.append(link);
    link.click();
    link.remove();
    this.savedAt.textContent = "已导出至运行目录，并开始下载";
  }

  timeLabel(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "刚刚" : parsed.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
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
