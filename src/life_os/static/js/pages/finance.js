import { api } from "../api/client.js";
import { element, emptyMessage, replace } from "../components/dom.js";
import { CategorySelect } from "../components/category-select.js";
import { normalizeDate, toLocalDateString } from "../utils/date.js";

const TYPE_LABELS = { income: "收入", expense: "支出", transfer: "转账" };
const KIND_LABELS = { asset: "资产", liability: "负债" };
const ACCOUNT_TYPE_LABELS = { cash: "现金", bank: "银行卡", credit: "信用卡", investment: "投资", other: "其他" };

function errorText(error) {
  const suffix = error?.requestId ? ` 请求编号：${error.requestId}` : "";
  return `${error?.message || "请求未能完成。"}${suffix}`;
}

function money(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" }).format(number);
}

function button(label, handler, className = "button button-quiet") {
  const node = element("button", { className, text: label, attrs: { type: "button" } });
  node.addEventListener("click", handler);
  return node;
}

export class FinancePage {
  constructor(root) {
    this.root = root;
    this.state = root.querySelector("[data-finance-state]");
    this.totals = root.querySelector("[data-finance-totals]");
    this.balanceList = root.querySelector("[data-account-balances]");
    this.accountList = root.querySelector("[data-account-list]");
    this.creditCycleList = root.querySelector("[data-credit-card-cycles]");
    this.creditCycleState = root.querySelector("[data-credit-cycle-state]");
    this.transactionList = root.querySelector("[data-transaction-list]");
    this.transactionState = root.querySelector("[data-transaction-state]");
    this.dateFilter = root.querySelector("[data-transaction-date]");
    this.typeFilter = root.querySelector("[data-transaction-type-filter]");
    this.summaryFrom = root.querySelector("[data-summary-from]");
    this.summaryTo = root.querySelector("[data-summary-to]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.accountDialog = root.querySelector("[data-account-dialog]");
    this.accountForm = root.querySelector("[data-account-form]");
    this.accountFormTitle = root.querySelector("[data-account-form-title]");
    this.transactionDialog = root.querySelector("[data-transaction-dialog]");
    this.transactionForm = root.querySelector("[data-transaction-form]");
    this.transactionFormTitle = root.querySelector("[data-transaction-form-title]");
    this.date = normalizeDate(new URLSearchParams(window.location.search).get("date"));
    this.accounts = [];
    this.transactions = [];
    this.creditCycles = [];
    this.editingAccountId = null;
    this.editingTransactionId = null;
    this.accountBusy = false;
    this.transactionBusy = false;
    this.categoryControl = new CategorySelect(root.querySelector("[data-finance-category-control]"), {
      scope: "finance",
      onError: (error) => this.showError(error),
    });
  }

  start() {
    this.dateFilter.value = this.date;
    this.summaryFrom.value = `${this.date.slice(0, 7)}-01`;
    this.summaryTo.value = this.date;
    this.replaceUrl();
    this.root.querySelector('[data-action="new-account"]').addEventListener("click", () => this.openAccount());
    this.root.querySelector('[data-action="new-transaction"]').addEventListener("click", () => this.openTransaction());
    this.root.querySelector('[data-action="retry-finance"]').addEventListener("click", () => this.loadAll());
    this.root.querySelector('[data-action="apply-period"]').addEventListener("click", () => this.loadSummary());
    this.root.querySelector('[data-action="close-account"]').addEventListener("click", () => this.closeAccount());
    this.root.querySelector('[data-action="cancel-account"]').addEventListener("click", () => this.closeAccount());
    this.root.querySelector('[data-action="close-transaction"]').addEventListener("click", () => this.closeTransaction());
    this.root.querySelector('[data-action="cancel-transaction"]').addEventListener("click", () => this.closeTransaction());
    this.accountDialog.addEventListener("cancel", (event) => this.accountBusy ? event.preventDefault() : this.resetAccountForm());
    this.transactionDialog.addEventListener("cancel", (event) => this.transactionBusy ? event.preventDefault() : this.resetTransactionForm());
    this.accountForm.addEventListener("submit", (event) => { event.preventDefault(); this.saveAccount(); });
    this.accountForm.elements.account_type.addEventListener("change", () => this.syncAccountTypeFields());
    this.transactionForm.addEventListener("submit", (event) => { event.preventDefault(); this.saveTransaction(); });
    this.transactionForm.elements.type.addEventListener("change", () => this.syncAccountFields());
    this.dateFilter.addEventListener("change", () => {
      this.date = normalizeDate(this.dateFilter.value, this.date);
      this.replaceUrl();
      Promise.all([this.loadTransactions(), this.loadCreditCardCycles()]);
    });
    this.typeFilter.addEventListener("change", () => this.loadTransactions());
    this.categoryControl.start();
    this.loadAll();
  }

  async loadAll() {
    this.hideError();
    this.state.textContent = "加载中";
    try {
      await this.loadAccounts();
      await Promise.all([this.loadSummary(), this.loadTransactions(), this.loadCreditCardCycles()]);
      this.state.textContent = "已更新";
    } catch (error) {
      this.state.textContent = "读取失败";
      this.showError(error);
    }
  }

  async loadAccounts() {
    this.accountList.setAttribute("aria-busy", "true");
    this.accounts = await api.get("/api/finance/accounts?include_inactive=true");
    this.renderAccounts();
    this.accountList.setAttribute("aria-busy", "false");
  }

  renderAccounts() {
    const accounts = this.accounts;
    if (!accounts.length) {
      replace(this.accountList, emptyMessage("还没有可用账户。请先新建现金、银行卡或负债账户。"));
      return;
    }
    replace(this.accountList, element("ul", { className: "management-items compact-items" }, accounts.map((account) => {
      const actions = element("div", { className: "item-actions" }, [
        button("编辑", () => this.openAccount(account)),
        button(account.active ? "停用" : "启用", () => this.toggleAccount(account), account.active ? "button button-quiet" : "button button-secondary"),
      ]);
      return element("li", { className: `management-item finance-account finance-account-${account.kind}${account.active ? "" : " is-inactive"}` }, [
        element("div", {}, [
          element("h3", { text: account.name }),
          element("div", { className: "item-details" }, [
            element("span", { text: KIND_LABELS[account.kind] }),
            element("span", { text: ACCOUNT_TYPE_LABELS[account.account_type] }),
            account.account_type === "credit" ? element("span", { text: `每月 ${account.billing_day || 18} 日账单` }) : null,
            element("span", { text: `期初 ${money(account.opening_balance)}` }),
            !account.active ? element("span", { className: "tag", text: "已停用" }) : null,
          ].filter(Boolean)),
        ]),
        actions,
      ]);
    })));
  }

  async loadCreditCardCycles() {
    const cards = this.accounts.filter((account) => account.account_type === "credit");
    this.creditCycleList.setAttribute("aria-busy", "true");
    this.creditCycleState.textContent = "加载中";
    try {
      this.creditCycles = await Promise.all(cards.map((account) => api.get(
        `/api/finance/credit-cards/${account.id}/cycle?as_of=${encodeURIComponent(this.date)}`,
      )));
      this.renderCreditCardCycles();
      this.creditCycleState.textContent = cards.length ? `${cards.length} 张` : "暂无信用卡";
    } catch (error) {
      replace(this.creditCycleList, emptyMessage("暂时无法读取信用卡账期。"));
      this.creditCycleState.textContent = "读取失败";
      this.showError(error);
      throw error;
    } finally {
      this.creditCycleList.setAttribute("aria-busy", "false");
    }
  }

  renderCreditCardCycles() {
    if (!this.creditCycles.length) {
      replace(this.creditCycleList, emptyMessage("还没有信用卡账户。新建账户并选择“信用卡”，即可按月查看账期。"));
      return;
    }
    replace(this.creditCycleList, ...this.creditCycles.map((cycle) => {
      const hasStatement = Number(cycle.statement_amount) > 0;
      const paid = cycle.status === "paid";
      const statusText = hasStatement ? (paid ? "上期已还清" : `待还 ${money(cycle.amount_due)}`) : "上期无待还";
      const repaymentAmount = Number(cycle.amount_due) > 0 ? cycle.amount_due : cycle.outstanding_balance;
      return element("article", { className: "credit-cycle-card" }, [
        element("div", { className: "credit-cycle-head" }, [
          element("div", {}, [
            element("h3", { text: cycle.account.name }),
            element("p", { className: "credit-cycle-period", text: `每月 ${cycle.billing_day} 日账单 · 截至 ${cycle.as_of}` }),
          ]),
          element("span", { className: `credit-cycle-status${paid ? " is-paid" : ""}`, text: statusText }),
        ]),
        element("div", { className: "credit-cycle-metrics" }, [
          this.creditMetric("本账期消费", cycle.current_spending),
          this.creditMetric("上期账单", cycle.statement_amount),
          this.creditMetric("本期已还", cycle.repayments),
          this.creditMetric("当前总欠款", cycle.outstanding_balance),
        ]),
        element("p", { className: "credit-cycle-period", text: `当前账期 ${cycle.cycle_start} — ${cycle.cycle_end}；${cycle.next_cycle_start} 自动进入下一账期。` }),
        cycle.account.active
          ? element("div", { className: "credit-cycle-actions" }, [
            button("记录消费", () => this.openTransaction(null, {
              type: "expense", from_account_id: cycle.account.id, date: this.date,
            }), "button button-secondary"),
            button("信用卡还款", () => this.openTransaction(null, {
              type: "transfer", to_account_id: cycle.account.id, amount: Number(repaymentAmount) > 0 ? repaymentAmount : "", date: this.date, description: "信用卡还款",
            }), "button button-primary"),
          ])
          : element("p", { className: "credit-cycle-period", text: "账户已停用；历史账期保留为只读。" }),
      ]);
    }));
  }

  creditMetric(label, value) {
    return element("div", { className: "credit-cycle-metric" }, [
      element("span", { text: label }),
      element("strong", { text: money(value) }),
    ]);
  }

  async loadTransactions() {
    this.transactionList.setAttribute("aria-busy", "true");
    this.transactionState.textContent = "加载中";
    const params = new URLSearchParams({ date: this.date });
    if (this.typeFilter.value) params.set("type", this.typeFilter.value);
    try {
      this.transactions = await api.get(`/api/finance/transactions?${params}`);
      this.renderTransactions();
      this.transactionState.textContent = `${this.transactions.length} 笔`;
    } catch (error) {
      replace(this.transactionList, emptyMessage("暂时无法读取流水。"));
      this.transactionState.textContent = "读取失败";
      this.showError(error);
      throw error;
    } finally {
      this.transactionList.setAttribute("aria-busy", "false");
    }
  }

  renderTransactions() {
    if (!this.transactions.length) {
      replace(this.transactionList, emptyMessage("这一天还没有流水。点击“记一笔”开始记录。"));
      return;
    }
    const accountNames = new Map(this.accounts.map((item) => [item.id, item.name]));
    replace(this.transactionList, element("ul", { className: "management-items" }, this.transactions.map((item) => {
      const route = item.type === "income"
        ? `进入 ${accountNames.get(item.to_account_id) || "账户"}`
        : item.type === "expense"
          ? `来自 ${accountNames.get(item.from_account_id) || "账户"}`
          : `${accountNames.get(item.from_account_id) || "账户"} → ${accountNames.get(item.to_account_id) || "账户"}`;
      const amountClass = item.type === "income" ? "money-positive" : item.type === "expense" ? "money-negative" : "";
      return element("li", { className: `management-item finance-transaction transaction-${item.type}` }, [
        element("div", {}, [
          element("h3", { text: item.description || item.category || TYPE_LABELS[item.type] }),
          element("div", { className: "item-details" }, [
            element("span", { className: `finance-value ${amountClass}`, text: `${item.type === "income" ? "+" : item.type === "expense" ? "−" : ""}${money(item.amount)}` }),
            element("span", { className: `finance-type finance-type-${item.type}`, text: TYPE_LABELS[item.type] }),
            element("span", { text: route }),
            item.category ? element("span", { text: item.category }) : null,
          ].filter(Boolean)),
          item.note ? element("p", { text: item.note }) : null,
        ].filter(Boolean)),
        element("div", { className: "item-actions" }, [
          button("编辑", () => this.openTransaction(item)),
          button("归档", () => this.archiveTransaction(item)),
        ]),
      ]);
    })));
  }

  async loadSummary() {
    const from = this.summaryFrom.value;
    const to = this.summaryTo.value;
    if (from && to && from > to) {
      this.summaryTo.setCustomValidity("统计结束日期不能早于开始日期。");
      this.summaryTo.reportValidity();
      this.summaryTo.setCustomValidity("");
      return;
    }
    this.totals.setAttribute("aria-busy", "true");
    const params = new URLSearchParams();
    if (from) params.set("date_from", from);
    if (to) params.set("date_to", to);
    try {
      const summary = await api.get(`/api/finance/summary?${params}`);
      const totals = [
        [summary.total_assets, "总资产", "finance-asset"], [summary.total_liabilities, "总负债", "finance-liability"], [summary.net_worth, "净资产", "finance-net"],
        [summary.income, "期间收入", "finance-income"], [summary.expense, "期间支出", "finance-expense"], [summary.net_cashflow, "期间净现金流", "finance-cashflow"],
      ];
      replace(this.totals, ...totals.map(([value, label, tone]) => element("div", { className: `metric ${tone}` }, [element("strong", { text: money(value) }), element("span", { text: label })])));
      const activeBalances = summary.accounts.filter((account) => account.active || Number(account.balance) !== 0);
      replace(this.balanceList, activeBalances.length
        ? element("ul", { className: "balance-items" }, activeBalances.map((account) => element("li", { className: `finance-account-${account.kind}` }, [
          element("span", { text: account.name }),
          element("span", { className: "muted", text: `${KIND_LABELS[account.kind]} · ${account.active ? "使用中" : "已停用"}` }),
          element("strong", { text: money(account.balance) }),
        ])))
        : emptyMessage("暂无账户余额。"));
    } catch (error) {
      replace(this.totals, emptyMessage("统计暂时不可用。"));
      this.showError(error);
      throw error;
    } finally {
      this.totals.setAttribute("aria-busy", "false");
    }
  }

  openAccount(account = null) {
    this.resetAccountForm();
    if (account) {
      this.editingAccountId = account.id;
      this.accountFormTitle.textContent = "编辑账户";
      const fields = this.accountForm.elements;
      fields.name.value = account.name;
      fields.kind.value = account.kind;
      fields.account_type.value = account.account_type;
      fields.billing_day.value = account.billing_day || 18;
      fields.opening_balance.value = account.opening_balance;
    }
    this.syncAccountTypeFields();
    this.accountDialog.showModal();
    this.accountForm.elements.name.focus();
  }

  resetAccountForm() {
    this.editingAccountId = null;
    this.accountForm.reset();
    this.accountForm.elements.opening_balance.value = "0.00";
    this.syncAccountTypeFields();
    this.accountFormTitle.textContent = "新建账户";
  }

  closeAccount() {
    if (this.accountBusy) return;
    this.accountDialog.close();
    this.resetAccountForm();
  }

  async saveAccount() {
    if (this.accountBusy || !this.accountForm.reportValidity()) return;
    const fields = this.accountForm.elements;
    const payload = {
      name: fields.name.value.trim(),
      kind: fields.kind.value,
      account_type: fields.account_type.value,
      billing_day: fields.account_type.value === "credit" ? Number(fields.billing_day.value) : null,
      opening_balance: fields.opening_balance.value,
    };
    this.accountBusy = true;
    this.setDisabled(this.accountForm, true);
    this.hideError();
    try {
      if (this.editingAccountId == null) await api.post("/api/finance/accounts", payload);
      else await api.put(`/api/finance/accounts/${this.editingAccountId}`, payload);
      this.accountDialog.close();
      this.resetAccountForm();
      await this.loadAll();
    } catch (error) {
      this.showError(error);
    } finally {
      this.accountBusy = false;
      this.setDisabled(this.accountForm, false);
    }
  }

  async toggleAccount(account) {
    this.hideError();
    try {
      await api.put(`/api/finance/accounts/${account.id}`, { active: !account.active });
      await this.loadAll();
    } catch (error) {
      this.showError(error);
    }
  }

  syncAccountTypeFields() {
    const fields = this.accountForm.elements;
    const isCredit = fields.account_type.value === "credit";
    this.root.querySelector("[data-billing-day-field]").classList.toggle("is-hidden", !isCredit);
    fields.billing_day.required = isCredit;
    if (isCredit) {
      fields.kind.value = "liability";
      if (!fields.billing_day.value) fields.billing_day.value = "18";
    } else {
      fields.billing_day.value = "";
    }
  }

  openTransaction(transaction = null, preset = {}) {
    this.resetTransactionForm();
    this.editingTransactionId = transaction?.id ?? null;
    this.transactionFormTitle.textContent = transaction ? "编辑流水" : "记一笔";
    const fields = this.transactionForm.elements;
    fields.date.value = preset.date || transaction?.date || this.date;
    fields.type.value = preset.type || transaction?.type || "expense";
    fields.amount.value = preset.amount || transaction?.amount || "";
    this.categoryControl.setValue(transaction?.category || "");
    fields.description.value = preset.description || transaction?.description || "";
    fields.note.value = transaction?.note || "";
    this.fillAccountOptions(transaction);
    const fromAccountId = preset.from_account_id ?? transaction?.from_account_id;
    const toAccountId = preset.to_account_id ?? transaction?.to_account_id;
    fields.from_account_id.value = fromAccountId == null ? "" : String(fromAccountId);
    fields.to_account_id.value = toAccountId == null ? "" : String(toAccountId);
    this.syncAccountFields();
    this.transactionDialog.showModal();
    fields.amount.focus();
  }

  fillAccountOptions(transaction = null) {
    const referenced = new Set([transaction?.from_account_id, transaction?.to_account_id].filter(Boolean));
    const accounts = this.accounts.filter((item) => item.active || referenced.has(item.id));
    for (const select of [this.transactionForm.elements.from_account_id, this.transactionForm.elements.to_account_id]) {
      replace(select, element("option", { text: "请选择账户", attrs: { value: "" } }), ...accounts.map((account) => element("option", { text: `${account.name}${account.active ? "" : "（已停用）"}`, attrs: { value: account.id } })));
    }
  }

  syncAccountFields() {
    const type = this.transactionForm.elements.type.value;
    const fromField = this.root.querySelector("[data-from-account-field]");
    const toField = this.root.querySelector("[data-to-account-field]");
    const from = this.transactionForm.elements.from_account_id;
    const to = this.transactionForm.elements.to_account_id;
    fromField.classList.toggle("is-hidden", type === "income");
    toField.classList.toggle("is-hidden", type === "expense");
    from.required = type !== "income";
    to.required = type !== "expense";
    if (type === "income") from.value = "";
    if (type === "expense") to.value = "";
  }

  resetTransactionForm() {
    this.editingTransactionId = null;
    this.transactionForm.reset();
    this.transactionForm.elements.type.value = "expense";
    this.transactionForm.elements.date.value = this.date;
    this.transactionFormTitle.textContent = "记一笔";
    this.categoryControl.setValue("");
    this.fillAccountOptions();
    this.syncAccountFields();
  }

  closeTransaction() {
    if (this.transactionBusy) return;
    this.transactionDialog.close();
    this.resetTransactionForm();
  }

  async saveTransaction() {
    if (this.transactionBusy || !this.transactionForm.reportValidity()) return;
    const fields = this.transactionForm.elements;
    if (fields.type.value === "transfer" && fields.from_account_id.value === fields.to_account_id.value) {
      fields.to_account_id.setCustomValidity("转出与转入账户不能相同。");
      fields.to_account_id.reportValidity();
      fields.to_account_id.setCustomValidity("");
      return;
    }
    const payload = {
      date: fields.date.value,
      type: fields.type.value,
      amount: fields.amount.value,
      from_account_id: fields.from_account_id.value ? Number(fields.from_account_id.value) : null,
      to_account_id: fields.to_account_id.value ? Number(fields.to_account_id.value) : null,
      category: fields.category.value.trim() || null,
      description: fields.description.value.trim() || null,
      note: fields.note.value.trim() || null,
    };
    this.transactionBusy = true;
    this.setDisabled(this.transactionForm, true);
    this.hideError();
    try {
      if (this.editingTransactionId == null) await api.post("/api/finance/transactions", payload);
      else await api.put(`/api/finance/transactions/${this.editingTransactionId}`, payload);
      this.date = payload.date;
      this.dateFilter.value = this.date;
      this.replaceUrl();
      this.transactionDialog.close();
      this.resetTransactionForm();
      await this.loadAll();
    } catch (error) {
      this.showError(error);
    } finally {
      this.transactionBusy = false;
      this.setDisabled(this.transactionForm, false);
    }
  }

  async archiveTransaction(transaction) {
    if (!window.confirm(`归档“${transaction.description || transaction.category || TYPE_LABELS[transaction.type]}”这笔流水？`)) return;
    this.hideError();
    try {
      await api.delete(`/api/finance/transactions/${transaction.id}`);
      await this.loadAll();
    } catch (error) {
      this.showError(error);
    }
  }

  setDisabled(form, disabled) {
    for (const control of form.elements) control.disabled = disabled;
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
  }
}
