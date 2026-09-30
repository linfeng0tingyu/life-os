import { element, emptyMessage, replace } from "./dom.js";
import { api } from "../api/client.js";

let pickerSequence = 0;

function actionButton(label, action, className = "button button-quiet") {
  return element("button", {
    className,
    text: label,
    attrs: { type: "button", "data-action": action },
  });
}

export class CategorySelect {
  constructor(root, { scope, onError }) {
    this.root = root;
    this.scope = scope;
    this.onError = onError;
    this.select = root.querySelector("[data-category-select]");
    this.creator = root.querySelector("[data-category-creator]");
    this.input = root.querySelector("[data-category-name]");
    this.state = root.querySelector("[data-category-state]");
    this.manager = root.querySelector("[data-category-manager]");
    this.managerSearch = root.querySelector("[data-category-manager-search]");
    this.managerList = root.querySelector("[data-category-manager-list]");
    this.references = root.querySelector("[data-category-references]");
    this.categories = [];
    this.busy = false;
    this.loadRevision = 0;
    this.setupPicker();
  }

  setupPicker() {
    const listId = `category-options-${this.scope}-${++pickerSequence}`;
    this.select.classList.add("category-native-select");
    this.select.tabIndex = -1;
    this.select.setAttribute("aria-hidden", "true");
    this.trigger = actionButton("未分类", "toggle-category-picker", "category-picker-trigger");
    this.trigger.setAttribute("aria-haspopup", "listbox");
    this.trigger.setAttribute("aria-expanded", "false");
    this.trigger.setAttribute("aria-controls", listId);
    this.pickerSearch = element("input", {
      className: "category-picker-search",
      attrs: { type: "search", placeholder: "搜索分类", "aria-label": "搜索分类" },
    });
    this.optionList = element("div", {
      className: "category-option-list",
      attrs: { id: listId, role: "listbox", "aria-label": "分类选项" },
    });
    this.pickerPanel = element("div", { className: "category-picker-panel is-hidden" }, [
      this.pickerSearch,
      this.optionList,
    ]);
    this.picker = element("div", { className: "category-picker" }, [this.trigger, this.pickerPanel]);
    this.select.insertAdjacentElement("afterend", this.picker);
  }

  start() {
    this.root.querySelector('[data-action="show-category-creator"]').addEventListener("click", () => this.showCreator());
    this.root.querySelector('[data-action="cancel-category-creator"]').addEventListener("click", () => this.hideCreator());
    this.root.querySelector('[data-action="save-category"]').addEventListener("click", () => this.create());
    this.root.querySelector('[data-action="show-category-manager"]').addEventListener("click", () => this.showManager());
    this.root.querySelector('[data-action="close-category-manager"]').addEventListener("click", () => this.hideManager());
    this.trigger.addEventListener("click", () => this.togglePicker());
    this.pickerSearch.addEventListener("input", () => this.renderPickerOptions());
    this.managerSearch.addEventListener("input", () => this.renderManager());
    this.input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        this.create();
      }
      if (event.key === "Escape") this.hideCreator();
    });
    this.pickerSearch.addEventListener("keydown", (event) => {
      if (event.key === "Escape") this.closePicker();
    });
    document.addEventListener("click", (event) => {
      if (!this.root.contains(event.target)) this.closePicker();
    });
    return this.load();
  }

  async load(selected = null) {
    const revision = ++this.loadRevision;
    this.setState("正在读取分类…");
    try {
      const categories = await api.get(`/api/categories?scope=${this.scope}`);
      if (revision !== this.loadRevision) return;
      this.categories = categories;
      this.clearReferences();
      this.render(selected ?? this.select.value);
      this.setCountState();
    } catch (error) {
      if (revision !== this.loadRevision) return;
      this.setState("分类读取失败");
      this.onError(error);
    }
  }

  render(selected = "") {
    const options = [new Option("未分类", "")];
    for (const category of this.categories) options.push(new Option(category.name, category.name));
    this.select.replaceChildren(...options);
    this.setValue(selected);
    this.renderManager();
  }

  setValue(value, announce = false) {
    const normalized = value || "";
    if (normalized && ![...this.select.options].some((option) => option.value === normalized)) {
      this.select.add(new Option(normalized, normalized));
    }
    this.select.value = normalized;
    this.trigger.textContent = normalized || "未分类";
    this.renderPickerOptions();
    if (announce) this.select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  renderPickerOptions() {
    const query = this.pickerSearch.value.trim().toLocaleLowerCase("zh-CN");
    const current = this.select.value;
    const categories = this.categories.filter((category) => (
      !query || category.name.toLocaleLowerCase("zh-CN").includes(query)
    ));
    const choices = [];
    if (!query || "未分类".includes(query)) choices.push({ name: "未分类", value: "" });
    choices.push(...categories.map((category) => ({ name: category.name, value: category.name })));
    if (current && !this.categories.some((category) => category.name === current)
      && (!query || current.toLocaleLowerCase("zh-CN").includes(query))) {
      choices.push({ name: `${current}（旧分类）`, value: current });
    }
    if (!choices.length) {
      replace(this.optionList, emptyMessage("没有匹配的分类。"));
      return;
    }
    replace(this.optionList, ...choices.map((choice) => {
      const option = actionButton(choice.name, "select-category", "category-option");
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(choice.value === current));
      option.addEventListener("click", () => {
        this.setValue(choice.value, true);
        this.closePicker();
      });
      return option;
    }));
  }

  togglePicker() {
    if (this.pickerPanel.classList.contains("is-hidden")) this.openPicker();
    else this.closePicker();
  }

  openPicker() {
    this.hideCreator();
    this.hideManager();
    this.pickerSearch.value = "";
    this.renderPickerOptions();
    this.pickerPanel.classList.remove("is-hidden");
    this.trigger.setAttribute("aria-expanded", "true");
    this.pickerSearch.focus();
  }

  closePicker() {
    this.pickerPanel.classList.add("is-hidden");
    this.trigger.setAttribute("aria-expanded", "false");
  }

  showCreator() {
    this.closePicker();
    this.hideManager();
    this.creator.classList.remove("is-hidden");
    this.input.focus();
  }

  hideCreator() {
    if (this.busy) return;
    this.input.value = "";
    this.creator.classList.add("is-hidden");
  }

  showManager() {
    this.closePicker();
    this.hideCreator();
    this.managerSearch.value = "";
    this.clearReferences();
    this.renderManager();
    this.manager.classList.remove("is-hidden");
    this.managerSearch.focus();
  }

  hideManager() {
    if (this.busy) return;
    this.manager.classList.add("is-hidden");
  }

  renderManager() {
    const query = this.managerSearch.value.trim().toLocaleLowerCase("zh-CN");
    const visible = this.categories.filter((category) => (
      !query || category.name.toLocaleLowerCase("zh-CN").includes(query)
    ));
    if (!visible.length) {
      replace(this.managerList, emptyMessage(this.categories.length ? "没有匹配的分类。" : "尚未创建分类。"));
      return;
    }
    replace(this.managerList, ...visible.map((category) => {
      const index = this.categories.findIndex((item) => item.id === category.id);
      const choose = actionButton(category.name, "choose-managed-category", "category-manager-name");
      choose.addEventListener("click", () => this.setValue(category.name, true));
      const up = actionButton("上移", "move-category-up");
      const down = actionButton("下移", "move-category-down");
      const remove = actionButton("删除", "delete-category", "button button-quiet category-delete");
      up.disabled = this.busy || index <= 0;
      down.disabled = this.busy || index >= this.categories.length - 1;
      remove.disabled = this.busy;
      up.addEventListener("click", () => this.move(category.id, -1));
      down.addEventListener("click", () => this.move(category.id, 1));
      remove.addEventListener("click", () => this.remove(category));
      return element("div", { className: "category-manager-item" }, [
        choose,
        element("div", { className: "category-manager-actions" }, [up, down, remove]),
      ]);
    }));
  }

  async create() {
    const name = this.input.value.trim();
    if (!name || this.busy) return;
    this.busy = true;
    this.setCreatorDisabled(true);
    this.setState("正在创建分类…");
    try {
      const category = await api.post("/api/categories", { scope: this.scope, name });
      this.loadRevision += 1;
      this.categories.push(category);
      this.categories.sort((left, right) => left.sort_order - right.sort_order || left.name.localeCompare(right.name, "zh-CN"));
      this.render(category.name);
      this.input.value = "";
      this.creator.classList.add("is-hidden");
      this.setState("分类已创建");
    } catch (error) {
      this.setState("分类创建失败");
      this.onError(error);
    } finally {
      this.busy = false;
      this.setCreatorDisabled(false);
      this.renderManager();
    }
  }

  async move(categoryId, direction) {
    if (this.busy) return;
    const index = this.categories.findIndex((category) => category.id === categoryId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= this.categories.length) return;
    const previous = [...this.categories];
    this.categories[index] = this.categories[target];
    this.categories[target] = previous[index];
    this.busy = true;
    this.renderManager();
    this.setState("正在保存分类顺序…");
    try {
      this.categories = await api.put("/api/categories/order", {
        scope: this.scope,
        category_ids: this.categories.map((category) => category.id),
      });
      this.render(this.select.value);
      this.setState("分类顺序已保存");
    } catch (error) {
      this.categories = previous;
      this.render(this.select.value);
      this.setState("分类排序失败");
      this.onError(error);
    } finally {
      this.busy = false;
      this.renderManager();
    }
  }

  async remove(category) {
    if (this.busy || !window.confirm(`删除分类“${category.name}”？正在使用的分类会被系统阻止删除。`)) return;
    this.busy = true;
    this.renderManager();
    this.setState("正在删除分类…");
    try {
      await api.delete(`/api/categories/${category.id}`);
      this.clearReferences();
      this.categories = this.categories.filter((item) => item.id !== category.id);
      const selected = this.select.value === category.name ? "" : this.select.value;
      this.render(selected);
      this.setState("分类已删除");
    } catch (error) {
      this.setState("分类仍在使用或删除失败");
      if (error?.status === 409 && Array.isArray(error?.details?.references)) {
        this.renderReferences(category, error.details);
      }
      this.onError(error);
    } finally {
      this.busy = false;
      this.renderManager();
    }
  }

  clearReferences() {
    if (!this.references) return;
    this.references.replaceChildren();
    this.references.classList.add("is-hidden");
  }

  renderReferences(category, details) {
    if (!this.references) return;
    const rows = details.references.map((reference) => {
      let summary = reference.label || `记录 #${reference.id}`;
      let href = null;
      let action = "查看引用项";
      if (reference.kind === "finance_transaction") {
        const type = { income: "收入", expense: "支出", transfer: "转账" }[reference.status] || "流水";
        const description = reference.label && reference.label !== type ? ` · ${reference.label}` : "";
        summary = `${reference.date} · ${type} ¥${reference.amount}${description}${reference.archived ? " · 已归档" : ""}`;
        const params = new URLSearchParams({
          date: reference.date,
          category: category.name,
          include_archived: "1",
          focus_transaction: String(reference.id),
        });
        href = `/finance?${params}`;
        action = reference.archived ? "定位并恢复流水" : "定位流水";
      } else if (reference.kind === "task") {
        summary = `${reference.label}${reference.date ? ` · ${reference.date}` : ""}${reference.archived ? " · 已归档" : ""}`;
        href = `/tasks?include_archived=1&focus_task=${reference.id}`;
        action = "查看任务";
      } else if (reference.kind === "habit") {
        summary = `${reference.label} · ${reference.status === "active" ? "使用中" : "已停用"}`;
        href = `/habits?focus_habit=${reference.id}`;
        action = "查看习惯";
      }
      const children = [element("span", { text: summary })];
      if (href) children.push(element("a", { className: "text-button category-reference-link", text: action, attrs: { href } }));
      return element("li", { className: "category-reference-item" }, children);
    });
    const title = `“${category.name}”仍被 ${details.usage_count} 项记录使用`;
    const note = details.references_truncated
      ? element("p", { text: "这里只显示部分引用项，请处理后再次尝试删除。" })
      : element("p", { text: "请先修改引用项的分类；已归档流水需要先恢复，再编辑分类。" });
    replace(this.references,
      element("strong", { text: title }),
      note,
      element("ul", { className: "category-reference-list" }, rows),
    );
    this.references.classList.remove("is-hidden");
  }

  setCreatorDisabled(disabled) {
    for (const control of this.creator.querySelectorAll("input, button")) control.disabled = disabled;
  }

  setCountState() {
    this.setState(this.categories.length ? `${this.categories.length} 个分类` : "尚未创建分类");
  }

  setState(value) {
    this.state.textContent = value;
  }
}
