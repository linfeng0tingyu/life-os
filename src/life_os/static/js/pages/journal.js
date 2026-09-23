import { api, ApiError } from "../api/client.js";
import { longDateLabel, normalizeDate, toLocalDateString } from "../utils/date.js";
import { renderMarkdownPreview } from "../components/markdown-preview.js";

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
    this.count = root.querySelector("[data-journal-count]");
    this.savedAt = root.querySelector("[data-journal-saved-at]");
    this.preview = root.querySelector("[data-journal-preview]");
    this.imageInput = root.querySelector("[data-journal-image]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.date = normalizeDate(new URLSearchParams(window.location.search).get("date"));
    this.timer = null;
    this.dirty = false;
    this.saving = false;
    this.request = null;
    this.hasRecord = false;
  }

  start() {
    const today = toLocalDateString();
    if (this.date > today) this.date = today;
    this.dateInput.max = today;
    this.dateInput.value = this.date;
    this.replaceUrl();
    this.dateInput.addEventListener("change", () => this.changeDate());
    this.content.addEventListener("input", () => this.markDirty());
    this.content.addEventListener("blur", () => {
      if (this.dirty) this.save();
    });
    this.root.querySelector('[data-action="retry-journal"]').addEventListener("click", () => this.save());
    this.root.querySelector('[data-action="insert-time"]').addEventListener("click", () => this.insertCurrentTime());
    for (const level of [1, 2, 3]) {
      this.root.querySelector(`[data-action="heading-${level}"]`).addEventListener("click", () => this.applyHeading(level));
    }
    this.root.querySelector('[data-action="insert-image"]').addEventListener("click", () => this.imageInput.click());
    this.root.querySelector('[data-action="export-journal"]').addEventListener("click", () => this.exportJournal());
    this.imageInput.addEventListener("change", () => this.uploadImage());
    window.addEventListener("beforeunload", (event) => {
      if (!this.dirty && !this.saving) return;
      event.preventDefault();
      event.returnValue = "";
    });
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
    this.content.disabled = true;
    try {
      const journal = await api.get(`/api/journal/${this.date}`, { signal: request.signal });
      if (this.request !== request) return;
      this.content.value = journal?.content || "";
      this.hasRecord = Boolean(journal);
      this.dirty = false;
      this.updateContext();
      this.setState("saved", journal ? "已载入" : "尚无日记");
      this.savedAt.textContent = journal?.updated_at ? `上次保存 ${this.timeLabel(journal.updated_at)}` : "尚未保存";
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.request !== request) return;
      this.setState("save-failed", "读取失败");
      this.showError(error);
    } finally {
      if (this.request === request) {
        this.content.disabled = false;
        this.content.focus();
      }
    }
  }

  markDirty() {
    this.dirty = true;
    this.updateCount();
    this.setState("saving", "等待保存");
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.save(), 1200);
  }

  async save() {
    window.clearTimeout(this.timer);
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
      this.setState(this.dirty ? "saving" : "saved", this.dirty ? "有新修改" : "已保存");
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
  }

  updateCount() {
    this.count.textContent = `${this.content.value.length} 字符`;
    renderMarkdownPreview(this.preview, this.content.value);
  }

  insertCurrentTime() {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    this.insertText(time);
  }

  applyHeading(level) {
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
    const start = this.content.selectionStart;
    const end = this.content.selectionEnd;
    this.content.setRangeText(text, start, end, "end");
    this.markDirty();
    this.content.focus();
  }

  async uploadImage() {
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
    if (!this.hasRecord) this.dirty = true;
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
