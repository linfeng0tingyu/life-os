import { api } from "../api/client.js";
import { element, emptyMessage, replace } from "./dom.js";

function actionButton(label, action, className = "button button-quiet") {
  return element("button", {
    className,
    text: label,
    attrs: { type: "button", "data-action": action },
  });
}

export class ExerciseTypePicker {
  constructor(root, { onChange = () => {}, onError = () => {} } = {}) {
    this.root = root;
    this.onChange = onChange;
    this.onError = onError;
    this.options = root.querySelector("[data-exercise-type-options]");
    this.dropdown = root.querySelector("[data-exercise-type-dropdown]");
    this.state = root.querySelector("[data-exercise-type-state]");
    this.summary = root.querySelector("[data-exercise-type-summary]");
    this.creator = root.querySelector("[data-exercise-type-creator]");
    this.nameInput = root.querySelector("[data-exercise-type-name]");
    this.manager = root.querySelector("[data-exercise-type-manager]");
    this.search = root.querySelector("[data-exercise-type-search]");
    this.managerList = root.querySelector("[data-exercise-type-manager-list]");
    this.items = [];
    this.selected = new Set();
    this.busy = false;
  }

  start() {
    document.addEventListener("click", (event) => {
      if (this.dropdown?.open && !this.root.contains(event.target)) this.dropdown.open = false;
    });
    this.root.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && this.dropdown?.open) {
        this.dropdown.open = false;
        this.summary?.focus();
      }
    });
    if (this.creator && this.manager) {
      this.root.querySelector('[data-action="show-exercise-type-creator"]').addEventListener("click", () => this.showCreator());
      this.root.querySelector('[data-action="cancel-exercise-type-creator"]').addEventListener("click", () => this.hideCreator());
      this.root.querySelector('[data-action="save-exercise-type"]').addEventListener("click", () => this.create());
      this.root.querySelector('[data-action="show-exercise-type-manager"]').addEventListener("click", () => this.showManager());
      this.root.querySelector('[data-action="close-exercise-type-manager"]').addEventListener("click", () => this.hideManager());
      this.search.addEventListener("input", () => this.renderManager());
      this.nameInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          this.create();
        }
        if (event.key === "Escape") this.hideCreator();
      });
    }
    return this.load();
  }

  async load() {
    this.setState("正在读取运动种类…");
    try {
      this.items = await api.get("/api/exercise-types");
      this.render();
      this.setCountState();
    } catch (error) {
      this.setState("运动种类读取失败");
      this.onError(error);
    }
  }

  setValue(ids = []) {
    this.selected = new Set(ids.map(Number));
    this.renderOptions();
    this.renderSummary();
  }

  getValue() {
    return this.items
      .filter((item) => this.selected.has(item.id))
      .map((item) => item.id);
  }

  render() {
    this.renderOptions();
    this.renderSummary();
    if (this.manager) this.renderManager();
  }

  renderOptions() {
    if (!this.items.length) {
      replace(this.options, emptyMessage(this.creator
        ? "尚未创建运动种类，可先点击“新建”。"
        : "尚未创建运动种类，请前往“节律”页面新建。"));
      return;
    }
    replace(this.options, ...this.items.map((item) => {
      const input = element("input", {
        attrs: {
          type: "checkbox",
          value: String(item.id),
        },
      });
      input.checked = this.selected.has(item.id);
      input.addEventListener("change", () => {
        if (input.checked) this.selected.add(item.id);
        else this.selected.delete(item.id);
        this.renderSummary();
        this.onChange(this.getValue());
      });
      return element("label", { className: "exercise-type-option" }, [input, element("span", { text: item.name })]);
    }));
  }

  showCreator() {
    if (!this.creator || !this.manager) return;
    this.hideManager();
    this.creator.classList.remove("is-hidden");
    this.nameInput.focus();
  }

  hideCreator() {
    if (!this.creator) return;
    if (this.busy) return;
    this.nameInput.value = "";
    this.creator.classList.add("is-hidden");
  }

  showManager() {
    if (!this.manager || !this.search) return;
    this.hideCreator();
    this.search.value = "";
    this.renderManager();
    this.manager.classList.remove("is-hidden");
    this.search.focus();
  }

  hideManager() {
    if (!this.manager) return;
    if (this.busy) return;
    this.manager.classList.add("is-hidden");
  }

  renderManager() {
    if (!this.manager || !this.search || !this.managerList) return;
    const query = this.search.value.trim().toLocaleLowerCase("zh-CN");
    const visible = this.items.filter((item) => !query || item.name.toLocaleLowerCase("zh-CN").includes(query));
    if (!visible.length) {
      replace(this.managerList, emptyMessage(this.items.length ? "没有匹配的运动种类。" : "尚未创建运动种类。"));
      return;
    }
    replace(this.managerList, ...visible.map((item) => {
      const index = this.items.findIndex((candidate) => candidate.id === item.id);
      const up = actionButton("上移", "move-exercise-type-up");
      const down = actionButton("下移", "move-exercise-type-down");
      const remove = actionButton("删除", "delete-exercise-type", "button button-quiet category-delete");
      up.disabled = this.busy || index <= 0;
      down.disabled = this.busy || index >= this.items.length - 1;
      remove.disabled = this.busy;
      up.addEventListener("click", () => this.move(item.id, -1));
      down.addEventListener("click", () => this.move(item.id, 1));
      remove.addEventListener("click", () => this.remove(item));
      return element("div", { className: "category-manager-item" }, [
        element("strong", { className: "category-manager-name", text: item.name }),
        element("div", { className: "category-manager-actions" }, [up, down, remove]),
      ]);
    }));
  }

  async create() {
    const name = this.nameInput.value.trim();
    if (!name || this.busy) return;
    this.busy = true;
    this.setCreatorDisabled(true);
    this.setState("正在创建运动种类…");
    try {
      const item = await api.post("/api/exercise-types", { name });
      this.items.push(item);
      this.items.sort((left, right) => left.sort_order - right.sort_order || left.name.localeCompare(right.name, "zh-CN"));
      this.selected.add(item.id);
      this.nameInput.value = "";
      this.creator.classList.add("is-hidden");
      this.render();
      this.setState("运动种类已创建并选中");
      this.onChange(this.getValue());
    } catch (error) {
      this.setState("运动种类创建失败");
      this.onError(error);
    } finally {
      this.busy = false;
      this.setCreatorDisabled(false);
      this.renderManager();
    }
  }

  async move(itemId, direction) {
    if (this.busy) return;
    const index = this.items.findIndex((item) => item.id === itemId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= this.items.length) return;
    const previous = [...this.items];
    [this.items[index], this.items[target]] = [this.items[target], this.items[index]];
    this.busy = true;
    this.renderManager();
    this.setState("正在保存运动种类顺序…");
    try {
      this.items = await api.put("/api/exercise-types/order", {
        exercise_type_ids: this.items.map((item) => item.id),
      });
      this.render();
      this.setState("运动种类顺序已保存");
    } catch (error) {
      this.items = previous;
      this.render();
      this.setState("运动种类排序失败");
      this.onError(error);
    } finally {
      this.busy = false;
      this.renderManager();
    }
  }

  async remove(item) {
    if (this.busy || !window.confirm(`删除运动种类“${item.name}”？正在使用的种类会被系统阻止删除。`)) return;
    this.busy = true;
    this.renderManager();
    this.setState("正在删除运动种类…");
    try {
      await api.delete(`/api/exercise-types/${item.id}`);
      this.items = this.items.filter((candidate) => candidate.id !== item.id);
      this.selected.delete(item.id);
      this.render();
      this.setState("运动种类已删除");
    } catch (error) {
      this.setState("运动种类仍在使用或删除失败");
      this.onError(error);
    } finally {
      this.busy = false;
      this.renderManager();
    }
  }

  setCreatorDisabled(disabled) {
    if (!this.creator) return;
    for (const control of this.creator.querySelectorAll("input, button")) control.disabled = disabled;
  }

  renderSummary() {
    if (!this.summary) return;
    const names = this.items
      .filter((item) => this.selected.has(item.id))
      .map((item) => item.name);
    this.summary.textContent = names.length === 0
      ? "选择运动种类"
      : names.length <= 2 ? names.join("、") : `已选择 ${names.length} 项`;
  }

  setCountState() {
    this.setState(this.items.length ? `${this.items.length} 个运动种类` : "尚未创建运动种类");
  }

  setState(value) {
    if (this.state) this.state.textContent = value;
    if (this.summary && !this.items.length) this.summary.textContent = value;
  }
}
