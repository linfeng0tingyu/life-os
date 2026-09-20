import { api, ApiError } from "../api/client.js";
import { element, emptyMessage, replace } from "../components/dom.js";

const STATUS_LABELS = { todo: "待办", doing: "进行中", done: "已完成", cancelled: "已取消" };
const PRIORITY_LABELS = { low: "低", normal: "普通", high: "重要", urgent: "紧急" };

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

function actionButton(label, className = "button button-quiet") {
  return element("button", { className, text: label, attrs: { type: "button" } });
}

export class TasksPage {
  constructor(root) {
    this.root = root;
    this.form = root.querySelector("[data-task-form]");
    this.formTitle = root.querySelector("[data-task-form-title]");
    this.formState = root.querySelector("[data-task-form-state]");
    this.cancelEdit = root.querySelector('[data-action="cancel-task-edit"]');
    this.parentSelect = root.querySelector("[data-task-parent]");
    this.list = root.querySelector("[data-task-list]");
    this.listState = root.querySelector("[data-task-list-state]");
    this.search = root.querySelector("[data-task-search]");
    this.statusFilter = root.querySelector("[data-task-status-filter]");
    this.dateFilter = root.querySelector("[data-task-date-filter]");
    this.showArchived = root.querySelector("[data-task-show-archived]");
    this.globalError = root.querySelector("[data-global-error]");
    this.globalErrorMessage = root.querySelector("[data-global-error-message]");
    this.tasks = [];
    this.editingId = null;
    this.pending = new Set();
    this.request = null;
    this.formBusy = false;
  }

  start() {
    this.root.querySelector('[data-action="new-task"]').addEventListener("click", () => this.resetForm(true));
    this.root.querySelector('[data-action="retry-tasks"]').addEventListener("click", () => this.loadTasks());
    this.cancelEdit.addEventListener("click", () => this.resetForm(true));
    this.form.addEventListener("submit", (event) => {
      event.preventDefault();
      this.saveTask();
    });
    for (const control of [this.search, this.statusFilter, this.dateFilter, this.showArchived]) {
      control.addEventListener(control === this.search ? "input" : "change", () => this.render());
    }
    this.loadTasks();
  }

  async loadTasks(announcement = "") {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.hideError();
    this.list.setAttribute("aria-busy", "true");
    this.listState.textContent = "加载中";
    try {
      const tasks = await api.get("/api/tasks?include_archived=true", { signal: request.signal });
      if (this.request !== request) return;
      this.tasks = tasks;
      this.updateParentOptions(this.editingId);
      this.render();
      if (announcement) this.listState.textContent = announcement;
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.request !== request) return;
      this.listState.textContent = "读取失败";
      replace(this.list, emptyMessage("暂时无法读取任务，请重试。"));
      this.showError(error);
    } finally {
      if (this.request === request) this.list.setAttribute("aria-busy", "false");
    }
  }

  filteredTasks() {
    const query = this.search.value.trim().toLocaleLowerCase("zh-CN");
    const status = this.statusFilter.value;
    const date = this.dateFilter.value;
    return this.tasks
      .filter((task) => this.showArchived.checked || !task.archived_at)
      .filter((task) => status === "all" || task.status === status)
      .filter((task) => {
        if (!date) return true;
        return task.scheduled_date === date || task.due_date === date
          || (task.due_date && task.due_date < date && !["done", "cancelled"].includes(task.status));
      })
      .filter((task) => !query || [task.title, task.category, task.description]
        .filter(Boolean).some((value) => value.toLocaleLowerCase("zh-CN").includes(query)))
      .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id);
  }

  render() {
    const tasks = this.filteredTasks();
    this.listState.textContent = `${tasks.length} 项`;
    if (!tasks.length) {
      replace(this.list, emptyMessage("当前筛选条件下没有任务。"));
      this.list.setAttribute("aria-busy", "false");
      return;
    }
    const names = new Map(this.tasks.map((task) => [task.id, task.title]));
    replace(this.list, element("ul", { className: "management-items" }, tasks.map((task) => {
      const item = element("li", {
        className: `management-item${task.archived_at ? " is-archived" : ""}`,
        attrs: { "data-id": task.id, "aria-busy": this.pending.has(task.id) ? "true" : "false" },
      });
      const details = [
        task.category || "未分类",
        task.scheduled_date ? `计划 ${task.scheduled_date}` : "无计划日期",
        task.due_date ? `截止 ${task.due_date}` : "无截止日期",
        task.parent_id ? `属于：${names.get(task.parent_id) || `任务 #${task.parent_id}`}` : null,
      ].filter(Boolean).map((text) => element("span", { text }));
      const badges = [
        element("span", { className: `tag status-${task.status}`, text: STATUS_LABELS[task.status] }),
        element("span", { className: `tag priority-${task.priority}`, text: `${PRIORITY_LABELS[task.priority]}优先级` }),
        task.archived_at ? element("span", { className: "tag", text: "已归档" }) : null,
      ].filter(Boolean);
      const copy = element("div", {}, [
        element("h3", { text: task.title }),
        task.description ? element("p", { text: task.description }) : null,
        element("div", { className: "item-details" }, details),
        element("div", { className: "item-badges" }, badges),
      ].filter(Boolean));
      item.append(copy, this.taskActions(task));
      return item;
    })));
    this.list.setAttribute("aria-busy", "false");
  }

  taskActions(task) {
    const actions = element("div", { className: "item-actions" });
    const add = (label, handler, className) => {
      const button = actionButton(label, className);
      button.disabled = this.pending.has(task.id);
      button.addEventListener("click", handler);
      actions.append(button);
    };
    if (task.archived_at) {
      add("恢复", () => this.runMutation(task.id, () => api.post(`/api/tasks/${task.id}/restore`, {}), "已恢复"), "button button-secondary");
      return actions;
    }
    if (task.status === "todo") add("开始", () => this.setStatus(task.id, "doing"));
    if (!["done", "cancelled"].includes(task.status)) add("完成", () => this.setStatus(task.id, "done"), "button button-primary");
    if (task.status === "doing") add("退回待办", () => this.setStatus(task.id, "todo"));
    if (["done", "cancelled"].includes(task.status)) add("重新打开", () => this.setStatus(task.id, "todo"));
    if (!["done", "cancelled"].includes(task.status)) add("取消", () => this.setStatus(task.id, "cancelled"));
    add("编辑", () => this.editTask(task));
    add("上移", () => this.moveTask(task, -1));
    add("下移", () => this.moveTask(task, 1));
    add("归档", () => this.runMutation(task.id, () => api.delete(`/api/tasks/${task.id}`), "已归档"));
    return actions;
  }

  async setStatus(taskId, status) {
    await this.runMutation(taskId, () => api.put(`/api/tasks/${taskId}`, { status }), "状态已保存");
  }

  async moveTask(task, direction) {
    const active = this.tasks.filter((item) => !item.archived_at)
      .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id);
    const index = active.findIndex((item) => item.id === task.id);
    const neighbor = active[index + direction];
    if (!neighbor) return;
    const sortOrder = direction < 0 ? neighbor.sort_order - 1 : neighbor.sort_order + 1;
    await this.runMutation(task.id, () => api.put(`/api/tasks/${task.id}`, { sort_order: sortOrder }), "顺序已保存");
  }

  editTask(task) {
    this.editingId = task.id;
    this.updateParentOptions(task.id);
    const fields = this.form.elements;
    fields.task_id.value = String(task.id);
    fields.title.value = task.title;
    fields.description.value = task.description || "";
    fields.status.value = task.status;
    fields.priority.value = task.priority;
    fields.category.value = task.category || "";
    fields.scheduled_date.value = task.scheduled_date || "";
    fields.due_date.value = task.due_date || "";
    fields.parent_id.value = task.parent_id == null ? "" : String(task.parent_id);
    this.formTitle.textContent = "编辑任务";
    this.formState.textContent = "正在编辑";
    this.cancelEdit.classList.remove("is-hidden");
    fields.title.focus();
  }

  resetForm(focus = false) {
    this.editingId = null;
    this.form.reset();
    this.form.elements.task_id.value = "";
    this.form.elements.status.value = "todo";
    this.form.elements.priority.value = "normal";
    this.updateParentOptions();
    this.formTitle.textContent = "新建任务";
    this.formState.textContent = "可编辑";
    this.formState.dataset.state = "ready";
    this.cancelEdit.classList.add("is-hidden");
    if (focus) this.form.elements.title.focus();
  }

  updateParentOptions(excludedId = null) {
    const current = this.parentSelect.value;
    const options = [element("option", { text: "无父任务", attrs: { value: "" } })];
    for (const task of this.tasks.filter((item) => !item.archived_at && item.id !== excludedId)) {
      options.push(element("option", { text: task.title, attrs: { value: task.id } }));
    }
    replace(this.parentSelect, ...options);
    if ([...this.parentSelect.options].some((option) => option.value === current)) this.parentSelect.value = current;
  }

  async saveTask() {
    if (this.formBusy || !this.form.reportValidity()) return;
    const fields = this.form.elements;
    const payload = {
      title: fields.title.value.trim(),
      description: fields.description.value.trim() || null,
      status: fields.status.value,
      priority: fields.priority.value,
      category: fields.category.value.trim() || null,
      scheduled_date: fields.scheduled_date.value || null,
      due_date: fields.due_date.value || null,
      parent_id: fields.parent_id.value ? Number(fields.parent_id.value) : null,
    };
    this.formBusy = true;
    this.setFormDisabled(true);
    this.formState.textContent = "保存中";
    this.formState.dataset.state = "saving";
    this.hideError();
    try {
      if (this.editingId == null) await api.post("/api/tasks", payload);
      else await api.put(`/api/tasks/${this.editingId}`, payload);
      this.resetForm();
      this.formState.textContent = "已保存";
      this.formState.dataset.state = "saved";
      await this.loadTasks("已保存");
    } catch (error) {
      this.formState.textContent = "保存失败";
      this.formState.dataset.state = "save-failed";
      this.showError(error);
    } finally {
      this.formBusy = false;
      this.setFormDisabled(false);
    }
  }

  setFormDisabled(disabled) {
    for (const control of this.form.elements) control.disabled = disabled;
  }

  async runMutation(taskId, action, announcement) {
    if (this.pending.has(taskId)) return;
    this.pending.add(taskId);
    this.hideError();
    this.render();
    try {
      await action();
      await this.loadTasks(announcement);
    } catch (error) {
      this.showError(error);
    } finally {
      this.pending.delete(taskId);
      this.render();
    }
  }

  showError(error) {
    this.globalErrorMessage.textContent = errorText(error);
    this.globalError.classList.remove("is-hidden");
  }

  hideError() {
    this.globalError.classList.add("is-hidden");
  }
}
