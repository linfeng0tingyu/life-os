import { api, ApiError } from "../api/client.js";
import { element, replace } from "../components/dom.js";

function errorText(error) {
  const suffix = error.requestId ? `（请求编号：${error.requestId}）` : "";
  return `${error instanceof ApiError ? error.message : "操作未能完成。"}${suffix}`;
}

function sizeLabel(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

export class SettingsPage {
  constructor(root) {
    this.root = root;
    this.errorNotice = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.systemState = root.querySelector("[data-system-state]");
    this.backupState = root.querySelector("[data-backup-state]");
    this.exportState = root.querySelector("[data-export-state]");
    this.restoreState = root.querySelector("[data-restore-state]");
    this.backupList = root.querySelector("[data-backup-list]");
    this.restoreSelect = root.querySelector("[data-restore-backup]");
    this.exportResult = root.querySelector("[data-export-result]");
    this.restoreResult = root.querySelector("[data-restore-result]");
    this.cancelRestoreButton = root.querySelector('[data-action="cancel-restore"]');
    this.backups = [];
  }

  async start() {
    this.root.querySelector('[data-action="retry-settings"]').addEventListener("click", () => this.load());
    this.root.querySelector('[data-action="copy-runtime"]').addEventListener("click", () => this.copyRuntime());
    this.root.querySelector('[data-action="save-retention"]').addEventListener("click", () => this.saveRetention());
    this.root.querySelector('[data-action="create-backup"]').addEventListener("click", () => this.createBackup());
    this.root.querySelector('[data-action="export-all"]').addEventListener("click", () => this.exportAll());
    this.root.querySelector('[data-action="schedule-restore"]').addEventListener("click", () => this.scheduleRestore());
    this.cancelRestoreButton.addEventListener("click", () => this.cancelRestore());
    await this.load();
  }

  async load() {
    this.hideError();
    this.systemState.textContent = "加载中";
    this.backupState.textContent = "加载中";
    try {
      const [info, backups] = await Promise.all([
        api.get("/api/system/info"),
        api.get("/api/system/backups"),
      ]);
      this.renderInfo(info);
      this.backups = backups.items;
      this.renderBackups();
      this.systemState.textContent = "已载入";
      this.backupState.textContent = `${this.backups.length} 份`;
    } catch (error) {
      this.systemState.textContent = "读取失败";
      this.backupState.textContent = "读取失败";
      this.showError(error);
    }
  }

  renderInfo(info) {
    this.root.querySelector("[data-app-version]").textContent = info.version;
    this.root.querySelector("[data-schema-version]").textContent = `v${info.schema_version}`;
    this.root.querySelector("[data-runtime-home]").textContent = info.runtime.home;
    this.root.querySelector("[data-retention-count]").value = info.backup.retention_count;
    const restore = info.restore;
    if (restore.pending) {
      this.restoreState.textContent = "等待重启";
      this.cancelRestoreButton.classList.remove("is-hidden");
      this.showResult(this.restoreResult, `已安排恢复 ${restore.pending.backup_file}，请正常关闭并重新打开 Life OS。`);
    } else if (restore.last_result?.status === "restored") {
      this.cancelRestoreButton.classList.add("is-hidden");
      this.restoreState.textContent = "最近恢复成功";
      this.showResult(this.restoreResult, `已从 ${restore.last_result.backup_file} 恢复；恢复前副本位于 ${restore.last_result.safety_copy || "未生成"}。`);
    } else if (restore.last_result?.status === "failed") {
      this.cancelRestoreButton.classList.add("is-hidden");
      this.restoreState.textContent = "最近恢复失败";
      this.showResult(this.restoreResult, restore.last_result.message || "恢复未能完成，原数据库保持不变。");
    } else {
      this.cancelRestoreButton.classList.add("is-hidden");
      this.restoreState.textContent = "未安排";
    }
  }

  renderBackups() {
    if (!this.backups.length) {
      replace(this.backupList, element("p", { className: "empty-state", text: "还没有可用备份。" }));
      replace(this.restoreSelect, element("option", { text: "暂无备份", attrs: { value: "" } }));
      return;
    }
    const items = this.backups.slice(0, 8).map((item) => element("li", {}, [
      element("div", {}, [
        element("strong", { text: item.filename }),
        element("small", { text: `${item.kind === "auto" ? "每日自动" : "手动"} · ${item.created_at}` }),
      ]),
      element("span", { className: "tag", text: sizeLabel(item.size_bytes) }),
    ]));
    replace(this.backupList, element("ul", { className: "backup-list" }, items));
    replace(this.restoreSelect, element("option", { text: "请选择备份", attrs: { value: "" } }), ...this.backups.map((item) => element("option", { text: item.filename, attrs: { value: item.filename } })));
  }

  async saveRetention() {
    const input = this.root.querySelector("[data-retention-count]");
    const value = Number(input.value);
    this.backupState.textContent = "保存中";
    try {
      const result = await api.put("/api/system/settings/backup", { retention_count: value });
      input.value = result.retention_count;
      this.backupState.textContent = "已保存";
    } catch (error) {
      this.backupState.textContent = "保存失败";
      this.showError(error);
    }
  }

  async createBackup() {
    const button = this.root.querySelector('[data-action="create-backup"]');
    button.disabled = true;
    this.backupState.textContent = "备份中";
    try {
      const result = await api.post("/api/system/backup", {});
      this.backupState.textContent = "备份完成";
      await this.load();
      this.backupState.textContent = `已创建 ${result.filename}`;
    } catch (error) {
      this.backupState.textContent = "备份失败";
      this.showError(error);
    } finally {
      button.disabled = false;
    }
  }

  async exportAll() {
    const button = this.root.querySelector('[data-action="export-all"]');
    button.disabled = true;
    this.exportState.textContent = "导出中";
    this.exportResult.classList.add("is-hidden");
    try {
      const includeZip = this.root.querySelector("[data-include-zip]").checked;
      const result = await api.post("/api/system/export", { include_zip: includeZip }, { timeout: 60000 });
      const path = result.zip_relative_path || result.relative_path;
      this.exportState.textContent = "导出完成";
      this.showResult(this.exportResult, `已生成 ${result.file_count} 个文件：${path}`);
    } catch (error) {
      this.exportState.textContent = "导出失败";
      this.showError(error);
    } finally {
      button.disabled = false;
    }
  }

  async scheduleRestore() {
    const backupFile = this.restoreSelect.value;
    const confirmation = this.root.querySelector("[data-restore-confirmation]").value.trim();
    const button = this.root.querySelector('[data-action="schedule-restore"]');
    button.disabled = true;
    this.restoreState.textContent = "校验中";
    try {
      const result = await api.post("/api/system/restore", { backup_file: backupFile, confirmation });
      this.restoreState.textContent = "等待重启";
      this.cancelRestoreButton.classList.remove("is-hidden");
      this.showResult(this.restoreResult, `备份 ${result.backup_file} 已通过校验。请正常关闭并重新打开 Life OS。`);
    } catch (error) {
      this.restoreState.textContent = "安排失败";
      this.showError(error);
    } finally {
      button.disabled = false;
    }
  }

  async cancelRestore() {
    this.cancelRestoreButton.disabled = true;
    try {
      const result = await api.delete("/api/system/restore");
      this.restoreState.textContent = result.cancelled ? "已取消" : "未安排";
      this.cancelRestoreButton.classList.add("is-hidden");
      this.showResult(this.restoreResult, result.cancelled ? "待恢复计划已取消，当前数据库不会在下次启动时被替换。" : "当前没有待恢复计划。");
    } catch (error) {
      this.restoreState.textContent = "取消失败";
      this.showError(error);
    } finally {
      this.cancelRestoreButton.disabled = false;
    }
  }

  async copyRuntime() {
    const value = this.root.querySelector("[data-runtime-home]").textContent;
    try {
      await navigator.clipboard.writeText(value);
      this.systemState.textContent = "路径已复制";
    } catch (_error) {
      this.systemState.textContent = "复制失败，请手动选择路径";
    }
  }

  showResult(container, text) {
    replace(container, element("p", { text }));
    container.classList.remove("is-hidden");
  }

  showError(error) {
    this.errorMessage.textContent = errorText(error);
    this.errorNotice.classList.remove("is-hidden");
  }

  hideError() {
    this.errorNotice.classList.add("is-hidden");
  }
}
