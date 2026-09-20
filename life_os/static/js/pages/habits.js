import { api, ApiError } from "../api/client.js";
import { element, emptyMessage, replace } from "../components/dom.js";
import { normalizeDate, toLocalDateString } from "../utils/date.js";

const ICON_LABELS = { book: "阅读", exercise: "运动", water: "饮水", sleep: "睡眠", health: "健康" };

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

function actionButton(label, className = "button button-quiet") {
  return element("button", { className, text: label, attrs: { type: "button" } });
}

export class HabitsPage {
  constructor(root) {
    this.root = root;
    this.form = root.querySelector("[data-habit-form]");
    this.formTitle = root.querySelector("[data-habit-form-title]");
    this.formState = root.querySelector("[data-habit-form-state]");
    this.cancelEdit = root.querySelector('[data-action="cancel-habit-edit"]');
    this.dateInput = root.querySelector("[data-habit-date]");
    this.checkList = root.querySelector("[data-habit-check-list]");
    this.list = root.querySelector("[data-habit-list]");
    this.listState = root.querySelector("[data-habit-list-state]");
    this.search = root.querySelector("[data-habit-search]");
    this.showInactive = root.querySelector("[data-habit-show-inactive]");
    this.globalError = root.querySelector("[data-global-error]");
    this.globalErrorMessage = root.querySelector("[data-global-error-message]");
    this.today = toLocalDateString();
    this.selectedDate = this.today;
    this.habits = [];
    this.day = null;
    this.editingId = null;
    this.pending = new Set();
    this.request = null;
    this.formBusy = false;
  }

  start() {
    this.dateInput.value = this.today;
    this.dateInput.max = this.today;
    this.root.querySelector('[data-action="new-habit"]').addEventListener("click", () => this.resetForm(true));
    this.root.querySelector('[data-action="retry-habits"]').addEventListener("click", () => this.load());
    this.cancelEdit.addEventListener("click", () => this.resetForm(true));
    this.form.addEventListener("submit", (event) => {
      event.preventDefault();
      this.saveHabit();
    });
    this.dateInput.addEventListener("change", () => {
      const value = normalizeDate(this.dateInput.value, this.today);
      this.selectedDate = value > this.today ? this.today : value;
      this.dateInput.value = this.selectedDate;
      this.load();
    });
    this.search.addEventListener("input", () => this.renderList());
    this.showInactive.addEventListener("change", () => this.renderList());
    this.load();
  }

  async load(announcement = "") {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.hideError();
    this.checkList.setAttribute("aria-busy", "true");
    this.list.setAttribute("aria-busy", "true");
    this.listState.textContent = "加载中";
    try {
      const [habits, day] = await Promise.all([
        api.get("/api/habits?include_inactive=true", { signal: request.signal }),
        api.get(`/api/day/${this.selectedDate}`, { signal: request.signal }),
      ]);
      if (this.request !== request) return;
      this.habits = habits;
      this.day = day;
      this.renderChecks();
      this.renderList();
      if (announcement) this.listState.textContent = announcement;
    } catch (error) {
      if (error instanceof ApiError && error.code === "cancelled") return;
      if (this.request !== request) return;
      replace(this.checkList, emptyMessage("暂时无法读取完成状态。"));
      replace(this.list, emptyMessage("暂时无法读取习惯。"));
      this.listState.textContent = "读取失败";
      this.showError(error);
    } finally {
      if (this.request === request) {
        this.checkList.setAttribute("aria-busy", "false");
        this.list.setAttribute("aria-busy", "false");
      }
    }
  }

  logsByHabit() {
    return new Map((this.day?.habits || []).map((entry) => [entry.habit.id, entry.log]));
  }

  renderChecks() {
    const active = this.habits.filter((habit) => habit.active)
      .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id);
    if (!active.length) {
      replace(this.checkList, emptyMessage("还没有启用的习惯，请先创建或恢复一个习惯。"));
      return;
    }
    const logs = this.logsByHabit();
    replace(this.checkList, element("ul", { className: "management-items" }, active.map((habit) => {
      const log = logs.get(habit.id) || { status: false, value: null, value_unit: null, note: null };
      const busyKey = `log-${habit.id}`;
      const button = actionButton(log.status ? "撤销完成" : "标记完成", "button button-secondary");
      button.setAttribute("aria-pressed", String(Boolean(log.status)));
      button.disabled = this.pending.has(busyKey);
      button.addEventListener("click", () => this.toggleLog(habit, log));
      return element("li", {
        className: "management-item habit-check-row",
        attrs: { "data-id": habit.id, "aria-busy": this.pending.has(busyKey) ? "true" : "false" },
      }, [
        element("div", {}, [
          element("h3", { text: habit.name }),
          element("p", { text: habit.category || habit.description || "日常习惯" }),
        ]),
        element("div", { className: "item-actions" }, [
          element("span", { className: `tag status-${log.status ? "done" : "todo"}`, text: log.status ? "已完成" : "待完成" }),
          button,
        ]),
      ]);
    })));
  }

  renderList() {
    const query = this.search.value.trim().toLocaleLowerCase("zh-CN");
    const habits = this.habits
      .filter((habit) => this.showInactive.checked || habit.active)
      .filter((habit) => !query || [habit.name, habit.category, habit.description]
        .filter(Boolean).some((value) => value.toLocaleLowerCase("zh-CN").includes(query)))
      .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id);
    this.listState.textContent = `${habits.length} 项`;
    if (!habits.length) {
      replace(this.list, emptyMessage("当前筛选条件下没有习惯。"));
      return;
    }
    replace(this.list, element("ul", { className: "management-items" }, habits.map((habit) => {
      const copy = element("div", {}, [
        element("h3", { text: habit.name }),
        habit.description ? element("p", { text: habit.description }) : null,
        element("div", { className: "item-details" }, [
          element("span", { text: habit.category || "未分类" }),
          element("span", { text: ICON_LABELS[habit.icon] || "通用图标" }),
          element("span", { text: habit.active ? "启用中" : "已停用" }),
        ]),
      ].filter(Boolean));
      return element("li", {
        className: `management-item${habit.active ? "" : " is-inactive"}`,
        attrs: { "data-id": habit.id, "aria-busy": this.pending.has(habit.id) ? "true" : "false" },
      }, [copy, this.habitActions(habit)]);
    })));
  }

  habitActions(habit) {
    const actions = element("div", { className: "item-actions" });
    const add = (label, handler, className) => {
      const button = actionButton(label, className);
      button.disabled = this.pending.has(habit.id);
      button.addEventListener("click", handler);
      actions.append(button);
    };
    if (habit.active) {
      add("编辑", () => this.editHabit(habit));
      add("上移", () => this.moveHabit(habit, -1));
      add("下移", () => this.moveHabit(habit, 1));
      add("停用", () => this.runMutation(habit.id, () => api.put(`/api/habits/${habit.id}`, { active: false }), "已停用"));
    } else {
      add("恢复", () => this.runMutation(habit.id, () => api.put(`/api/habits/${habit.id}`, { active: true }), "已恢复"), "button button-secondary");
      add("编辑", () => this.editHabit(habit));
    }
    return actions;
  }

  async toggleLog(habit, log) {
    const key = `log-${habit.id}`;
    if (this.pending.has(key)) return;
    this.pending.add(key);
    this.hideError();
    this.renderChecks();
    try {
      await api.put(`/api/habits/${habit.id}/log/${this.selectedDate}`, {
        status: !log.status,
        value: log.value,
        value_unit: log.value_unit,
        note: log.note,
      });
      await this.load("完成状态已保存");
    } catch (error) {
      this.showError(error);
    } finally {
      this.pending.delete(key);
      this.renderChecks();
    }
  }

  async moveHabit(habit, direction) {
    const active = this.habits.filter((item) => item.active)
      .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id);
    const index = active.findIndex((item) => item.id === habit.id);
    const neighbor = active[index + direction];
    if (!neighbor) return;
    const sortOrder = direction < 0 ? neighbor.sort_order - 1 : neighbor.sort_order + 1;
    await this.runMutation(habit.id, () => api.put(`/api/habits/${habit.id}`, { sort_order: sortOrder }), "顺序已保存");
  }

  editHabit(habit) {
    this.editingId = habit.id;
    const fields = this.form.elements;
    fields.habit_id.value = String(habit.id);
    fields.name.value = habit.name;
    fields.description.value = habit.description || "";
    fields.category.value = habit.category || "";
    fields.icon.value = habit.icon || "";
    this.formTitle.textContent = "编辑习惯";
    this.formState.textContent = habit.active ? "正在编辑" : "正在编辑停用项";
    this.cancelEdit.classList.remove("is-hidden");
    fields.name.focus();
  }

  resetForm(focus = false) {
    this.editingId = null;
    this.form.reset();
    this.form.elements.habit_id.value = "";
    this.formTitle.textContent = "新建习惯";
    this.formState.textContent = "可编辑";
    this.formState.dataset.state = "ready";
    this.cancelEdit.classList.add("is-hidden");
    if (focus) this.form.elements.name.focus();
  }

  async saveHabit() {
    if (this.formBusy || !this.form.reportValidity()) return;
    const fields = this.form.elements;
    const payload = {
      name: fields.name.value.trim(),
      description: fields.description.value.trim() || null,
      category: fields.category.value.trim() || null,
      icon: fields.icon.value || null,
    };
    this.formBusy = true;
    this.setFormDisabled(true);
    this.formState.textContent = "保存中";
    this.formState.dataset.state = "saving";
    this.hideError();
    try {
      if (this.editingId == null) await api.post("/api/habits", payload);
      else await api.put(`/api/habits/${this.editingId}`, payload);
      this.resetForm();
      this.formState.textContent = "已保存";
      this.formState.dataset.state = "saved";
      await this.load("已保存");
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

  async runMutation(habitId, action, announcement) {
    if (this.pending.has(habitId)) return;
    this.pending.add(habitId);
    this.hideError();
    this.renderList();
    try {
      await action();
      await this.load(announcement);
    } catch (error) {
      this.showError(error);
    } finally {
      this.pending.delete(habitId);
      this.renderList();
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
