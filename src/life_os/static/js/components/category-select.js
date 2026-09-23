import { api } from "../api/client.js";

export class CategorySelect {
  constructor(root, { scope, onError }) {
    this.root = root;
    this.scope = scope;
    this.onError = onError;
    this.select = root.querySelector("[data-category-select]");
    this.creator = root.querySelector("[data-category-creator]");
    this.input = root.querySelector("[data-category-name]");
    this.state = root.querySelector("[data-category-state]");
    this.categories = [];
    this.busy = false;
  }

  start() {
    this.root.querySelector('[data-action="show-category-creator"]').addEventListener("click", () => this.showCreator());
    this.root.querySelector('[data-action="cancel-category-creator"]').addEventListener("click", () => this.hideCreator());
    this.root.querySelector('[data-action="save-category"]').addEventListener("click", () => this.create());
    this.input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        this.create();
      }
      if (event.key === "Escape") this.hideCreator();
    });
    return this.load();
  }

  async load(selected = null) {
    this.setState("正在读取分类…");
    try {
      this.categories = await api.get(`/api/categories?scope=${this.scope}`);
      this.render(selected ?? this.select.value);
      this.setState(this.categories.length ? `${this.categories.length} 个分类` : "尚未创建分类");
    } catch (error) {
      this.setState("分类读取失败");
      this.onError(error);
    }
  }

  render(selected = "") {
    const options = [new Option("未分类", "")];
    for (const category of this.categories) options.push(new Option(category.name, category.name));
    this.select.replaceChildren(...options);
    this.setValue(selected);
  }

  setValue(value) {
    const normalized = value || "";
    if (normalized && ![...this.select.options].some((option) => option.value === normalized)) {
      this.select.add(new Option(normalized, normalized));
    }
    this.select.value = normalized;
  }

  showCreator() {
    this.creator.classList.remove("is-hidden");
    this.input.focus();
  }

  hideCreator() {
    if (this.busy) return;
    this.input.value = "";
    this.creator.classList.add("is-hidden");
  }

  async create() {
    const name = this.input.value.trim();
    if (!name || this.busy) return;
    this.busy = true;
    this.setCreatorDisabled(true);
    this.setState("正在创建分类…");
    try {
      const category = await api.post("/api/categories", { scope: this.scope, name });
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
    }
  }

  setCreatorDisabled(disabled) {
    for (const control of this.creator.querySelectorAll("input, button")) control.disabled = disabled;
  }

  setState(value) {
    this.state.textContent = value;
  }
}
