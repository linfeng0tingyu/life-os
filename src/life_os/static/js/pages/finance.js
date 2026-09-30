import { api } from "../api/client.js";
import { element, emptyMessage, replace } from "../components/dom.js";
import { CategorySelect } from "../components/category-select.js";
import { normalizeDate, toLocalDateString } from "../utils/date.js";

const TYPE_LABELS = { income: "收入", expense: "支出", transfer: "转账", adjustment: "余额调整" };
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

function reportTable(headers, rows) {
  return element("div", { className: "report-table-wrap finance-report-table-wrap" }, [
    element("table", { className: "report-table" }, [
      element("thead", {}, [
        element("tr", {}, headers.map((header) => element("th", { text: header, attrs: { scope: "col" } }))),
      ]),
      element("tbody", {}, rows.map((row) => element("tr", {}, row.map((value) => element("td", { text: value }))))),
    ]),
  ]);
}

function reportDetails(summary, table) {
  return element("details", { className: "finance-report-details" }, [
    element("summary", { text: summary }),
    table,
  ]);
}

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

function compactMoney(value) {
  const formatted = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    currencyDisplay: "narrowSymbol",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value || 0));
  return formatted;
}

function renderLineChart(container, dates, series, label, emptyText = "请选择至少一个纵轴指标。") {
  if (!dates.length || !series.length) {
    replace(container, emptyMessage(emptyText));
    return;
  }
  const width = 760;
  const height = 300;
  const margin = { top: 24, right: 18, bottom: 46, left: 66 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = series.flatMap((item) => item.values.map(Number));
  let minimum = Math.min(0, ...values);
  let maximum = Math.max(0, ...values);
  if (minimum === maximum) maximum = minimum + 1;
  const padding = (maximum - minimum) * 0.08;
  minimum -= padding;
  maximum += padding;
  const x = (index) => margin.left + (dates.length === 1 ? plotWidth / 2 : index * plotWidth / (dates.length - 1));
  const y = (value) => margin.top + (maximum - Number(value)) * plotHeight / (maximum - minimum);
  const svg = svgElement("svg", {
    class: "finance-chart-svg",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": label,
    preserveAspectRatio: "xMidYMid meet",
  });
  const title = svgElement("title");
  title.textContent = label;
  svg.append(title);
  for (let index = 0; index <= 4; index += 1) {
    const value = maximum - (maximum - minimum) * index / 4;
    const lineY = margin.top + plotHeight * index / 4;
    svg.append(svgElement("line", { class: "finance-chart-grid", x1: margin.left, y1: lineY, x2: width - margin.right, y2: lineY }));
    const tick = svgElement("text", { class: "finance-chart-axis-label", x: margin.left - 10, y: lineY + 4, "text-anchor": "end" });
    tick.textContent = compactMoney(value);
    svg.append(tick);
  }
  const labelIndexes = [...new Set([0, 1, 2, 3, 4].map((step) => Math.round((dates.length - 1) * step / 4)))];
  for (const index of labelIndexes) {
    const tick = svgElement("text", { class: "finance-chart-axis-label", x: x(index), y: height - 18, "text-anchor": "middle" });
    tick.textContent = dates[index].slice(5);
    svg.append(tick);
  }
  series.forEach((item, seriesIndex) => {
    const points = item.values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
    svg.append(svgElement("polyline", { class: `finance-chart-line series-${seriesIndex % 8}`, points }));
    if (dates.length <= 62) {
      item.values.forEach((value, index) => {
        const point = svgElement("circle", { class: `finance-chart-point series-${seriesIndex % 8}`, cx: x(index), cy: y(value), r: 3.2, tabindex: 0 });
        const pointTitle = svgElement("title");
        pointTitle.textContent = `${dates[index]} · ${item.label}：${money(value)}`;
        point.append(pointTitle);
        svg.append(point);
      });
    }
  });
  const legend = element("div", { className: "finance-chart-legend" }, series.map((item, index) => element("span", {}, [
    element("i", { className: `finance-chart-swatch series-${index % 8}`, attrs: { "aria-hidden": "true" } }),
    document.createTextNode(item.label),
  ])));
  replace(container, svg, legend);
}

function renderBarChart(container, dates, series, label, emptyText = "请选择至少一个纵轴指标。") {
  if (!dates.length || !series.length) {
    replace(container, emptyMessage(emptyText));
    return;
  }
  const width = 760;
  const height = 300;
  const margin = { top: 24, right: 18, bottom: 46, left: 66 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = series.flatMap((item) => item.values.map(Number));
  let minimum = Math.min(0, ...values);
  let maximum = Math.max(0, ...values);
  if (minimum === maximum) maximum = minimum + 1;
  const padding = (maximum - minimum) * 0.08;
  minimum -= padding;
  maximum += padding;
  const y = (value) => margin.top + (maximum - Number(value)) * plotHeight / (maximum - minimum);
  const zeroY = y(0);
  const groupWidth = plotWidth / dates.length;
  const availableWidth = groupWidth * 0.82;
  const barWidth = Math.max(1, Math.min(20, availableWidth / series.length));
  const groupBarsWidth = barWidth * series.length;
  const groupStart = (index) => margin.left + index * groupWidth + (groupWidth - groupBarsWidth) / 2;
  const groupCenter = (index) => margin.left + (index + 0.5) * groupWidth;
  const svg = svgElement("svg", {
    class: "finance-chart-svg",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": label,
    preserveAspectRatio: "xMidYMid meet",
  });
  const title = svgElement("title");
  title.textContent = label;
  svg.append(title);
  for (let index = 0; index <= 4; index += 1) {
    const value = maximum - (maximum - minimum) * index / 4;
    const lineY = margin.top + plotHeight * index / 4;
    svg.append(svgElement("line", { class: "finance-chart-grid", x1: margin.left, y1: lineY, x2: width - margin.right, y2: lineY }));
    const tick = svgElement("text", { class: "finance-chart-axis-label", x: margin.left - 10, y: lineY + 4, "text-anchor": "end" });
    tick.textContent = compactMoney(value);
    svg.append(tick);
  }
  svg.append(svgElement("line", { class: "finance-chart-zero", x1: margin.left, y1: zeroY, x2: width - margin.right, y2: zeroY }));
  const labelIndexes = [...new Set([0, 1, 2, 3, 4].map((step) => Math.round((dates.length - 1) * step / 4)))];
  for (const index of labelIndexes) {
    const tick = svgElement("text", { class: "finance-chart-axis-label", x: groupCenter(index), y: height - 18, "text-anchor": "middle" });
    tick.textContent = dates[index].slice(5);
    svg.append(tick);
  }
  series.forEach((item, seriesIndex) => {
    item.values.forEach((value, index) => {
      const valueY = y(value);
      const bar = svgElement("rect", {
        class: `finance-chart-bar series-${seriesIndex % 8}`,
        x: groupStart(index) + seriesIndex * barWidth,
        y: Math.min(valueY, zeroY),
        width: barWidth,
        height: Math.max(1, Math.abs(zeroY - valueY)),
        tabindex: 0,
      });
      const barTitle = svgElement("title");
      barTitle.textContent = `${dates[index]} · ${item.label}：${money(value)}`;
      bar.append(barTitle);
      svg.append(bar);
    });
  });
  const legend = element("div", { className: "finance-chart-legend" }, series.map((item, index) => element("span", {}, [
    element("i", { className: `finance-chart-swatch series-${index % 8}`, attrs: { "aria-hidden": "true" } }),
    document.createTextNode(item.label),
  ])));
  replace(container, svg, legend);
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
    this.categoryFilter = root.querySelector("[data-transaction-category-filter]");
    this.allDatesFilter = root.querySelector("[data-transaction-all-dates]");
    this.includeArchivedFilter = root.querySelector("[data-transaction-include-archived]");
    this.summaryFrom = root.querySelector("[data-summary-from]");
    this.summaryTo = root.querySelector("[data-summary-to]");
    this.reportState = root.querySelector("[data-finance-report-state]");
    this.reportSummary = root.querySelector("[data-finance-report-summary]");
    this.reportByDate = root.querySelector("[data-finance-report-by-date]");
    this.reportByCategory = root.querySelector("[data-finance-report-by-category]");
    this.assetMetricControls = root.querySelector("[data-finance-asset-metric-controls]");
    this.assetChart = root.querySelector("[data-finance-asset-chart]");
    this.assetRangeFrom = root.querySelector("[data-finance-asset-x-from]");
    this.assetRangeTo = root.querySelector("[data-finance-asset-x-to]");
    this.assetRangeState = root.querySelector("[data-finance-asset-range-state]");
    this.categoryMeasure = root.querySelector("[data-finance-category-measure]");
    this.categorySeriesControls = root.querySelector("[data-finance-category-series-controls]");
    this.categoryChart = root.querySelector("[data-finance-category-chart]");
    this.categoryRangeFrom = root.querySelector("[data-finance-category-x-from]");
    this.categoryRangeTo = root.querySelector("[data-finance-category-x-to]");
    this.categoryRangeState = root.querySelector("[data-finance-category-range-state]");
    this.error = root.querySelector("[data-global-error]");
    this.errorMessage = root.querySelector("[data-global-error-message]");
    this.accountDialog = root.querySelector("[data-account-dialog]");
    this.accountForm = root.querySelector("[data-account-form]");
    this.accountFormTitle = root.querySelector("[data-account-form-title]");
    this.balanceDialog = root.querySelector("[data-balance-dialog]");
    this.balanceForm = root.querySelector("[data-balance-form]");
    this.balanceAccountName = root.querySelector("[data-balance-account-name]");
    this.currentBalance = root.querySelector("[data-current-balance]");
    this.balanceDate = root.querySelector("[data-balance-date]");
    this.balanceDifference = root.querySelector("[data-balance-difference]");
    this.transactionDialog = root.querySelector("[data-transaction-dialog]");
    this.transactionForm = root.querySelector("[data-transaction-form]");
    this.transactionFormTitle = root.querySelector("[data-transaction-form-title]");
    this.saveAndNewTransaction = root.querySelector('[data-action="save-and-new-transaction"]');
    const search = new URLSearchParams(window.location.search);
    this.date = normalizeDate(search.get("date"));
    this.initialCategoryFilter = search.get("category") || "";
    this.initialIncludeArchived = search.get("include_archived") === "1";
    this.initialAllDates = search.get("all_dates") === "1";
    this.focusTransactionId = Number(search.get("focus_transaction")) || null;
    this.accounts = [];
    this.transactions = [];
    this.creditCycles = [];
    this.editingAccountId = null;
    this.editingTransactionId = null;
    this.accountBusy = false;
    this.balanceBusy = false;
    this.adjustingAccount = null;
    this.transactionBusy = false;
    this.transactionSearchTimer = null;
    this.assetReport = null;
    this.categoryReport = null;
    this.assetChartRevision = 0;
    this.categoryChartRevision = 0;
    this.assetMetricSelection = new Set(["total_assets", "net_worth"]);
    this.categorySeriesSelection = new Set();
    this.categoryControl = new CategorySelect(root.querySelector("[data-finance-category-control]"), {
      scope: "finance",
      onError: (error) => this.showError(error),
    });
  }

  start() {
    this.dateFilter.value = this.date;
    this.categoryFilter.value = this.initialCategoryFilter;
    this.includeArchivedFilter.checked = this.initialIncludeArchived;
    this.allDatesFilter.checked = this.initialAllDates;
    this.dateFilter.disabled = this.allDatesFilter.checked;
    this.summaryFrom.value = `${this.date.slice(0, 7)}-01`;
    this.summaryTo.value = this.date;
    this.assetRangeFrom.value = this.summaryFrom.value;
    this.assetRangeTo.value = this.summaryTo.value;
    this.categoryRangeFrom.value = this.summaryFrom.value;
    this.categoryRangeTo.value = this.summaryTo.value;
    this.replaceUrl();
    this.root.querySelector('[data-action="new-account"]').addEventListener("click", () => this.openAccount());
    this.root.querySelector('[data-action="new-transaction"]').addEventListener("click", () => this.openTransaction());
    this.root.querySelector('[data-action="retry-finance"]').addEventListener("click", () => this.loadAll());
    this.root.querySelector('[data-action="apply-period"]').addEventListener("click", () => this.loadSummary());
    this.root.querySelector('[data-action="apply-asset-x-range"]').addEventListener("click", () => this.loadChartReport("asset"));
    this.root.querySelector('[data-action="apply-category-x-range"]').addEventListener("click", () => this.loadChartReport("category"));
    this.root.querySelector('[data-action="close-account"]').addEventListener("click", () => this.closeAccount());
    this.root.querySelector('[data-action="cancel-account"]').addEventListener("click", () => this.closeAccount());
    this.root.querySelector('[data-action="close-balance-adjustment"]').addEventListener("click", () => this.closeBalanceAdjustment());
    this.root.querySelector('[data-action="cancel-balance-adjustment"]').addEventListener("click", () => this.closeBalanceAdjustment());
    this.root.querySelector('[data-action="close-transaction"]').addEventListener("click", () => this.closeTransaction());
    this.root.querySelector('[data-action="cancel-transaction"]').addEventListener("click", () => this.closeTransaction());
    this.accountDialog.addEventListener("cancel", (event) => this.accountBusy ? event.preventDefault() : this.resetAccountForm());
    this.balanceDialog.addEventListener("cancel", (event) => this.balanceBusy ? event.preventDefault() : this.resetBalanceAdjustment());
    this.transactionDialog.addEventListener("cancel", (event) => this.transactionBusy ? event.preventDefault() : this.resetTransactionForm());
    this.accountForm.addEventListener("submit", (event) => { event.preventDefault(); this.saveAccount(); });
    this.balanceForm.addEventListener("submit", (event) => { event.preventDefault(); this.saveBalanceAdjustment(); });
    this.balanceForm.elements.target_balance.addEventListener("input", () => this.updateBalanceDifference());
    this.accountForm.elements.account_type.addEventListener("change", () => this.syncAccountTypeFields());
    this.transactionForm.addEventListener("submit", (event) => { event.preventDefault(); this.saveTransaction(false); });
    this.saveAndNewTransaction.addEventListener("click", () => this.saveTransaction(true));
    this.transactionForm.elements.type.addEventListener("change", () => this.syncAccountFields());
    this.dateFilter.addEventListener("change", () => {
      this.date = normalizeDate(this.dateFilter.value, this.date);
      this.replaceUrl();
      Promise.all([this.loadTransactions(), this.loadCreditCardCycles()]);
    });
    this.typeFilter.addEventListener("change", () => this.loadTransactions());
    this.categoryFilter.addEventListener("input", () => {
      window.clearTimeout(this.transactionSearchTimer);
      this.transactionSearchTimer = window.setTimeout(() => {
        this.focusTransactionId = null;
        this.replaceUrl();
        this.loadTransactions();
      }, 250);
    });
    this.allDatesFilter.addEventListener("change", () => {
      this.dateFilter.disabled = this.allDatesFilter.checked;
      this.focusTransactionId = null;
      this.replaceUrl();
      this.loadTransactions();
    });
    this.includeArchivedFilter.addEventListener("change", () => {
      this.focusTransactionId = null;
      this.replaceUrl();
      this.loadTransactions();
    });
    this.categoryMeasure.addEventListener("change", () => this.renderCategoryChart());
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
    const params = new URLSearchParams();
    if (!this.allDatesFilter.checked) params.set("date", this.date);
    if (this.typeFilter.value) params.set("type", this.typeFilter.value);
    if (this.categoryFilter.value.trim()) params.set("category", this.categoryFilter.value.trim());
    if (this.includeArchivedFilter.checked) params.set("include_archived", "true");
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
      replace(this.transactionList, emptyMessage("没有找到符合当前日期、类型和分类条件的流水。"));
      return;
    }
    const accountNames = new Map(this.accounts.map((item) => [item.id, item.name]));
    replace(this.transactionList, element("ul", { className: "management-items" }, this.transactions.map((item) => {
      const displayType = item.is_adjustment ? "adjustment" : item.type;
      const route = item.type === "income"
        ? `进入 ${accountNames.get(item.to_account_id) || "账户"}`
        : item.type === "expense"
          ? `来自 ${accountNames.get(item.from_account_id) || "账户"}`
          : `${accountNames.get(item.from_account_id) || "账户"} → ${accountNames.get(item.to_account_id) || "账户"}`;
      const amountClass = item.type === "income" ? "money-positive" : item.type === "expense" ? "money-negative" : "";
      const archived = Boolean(item.archived_at);
      const focused = item.id === this.focusTransactionId;
      return element("li", {
        className: `management-item finance-transaction transaction-${displayType}${archived ? " is-archived" : ""}${focused ? " is-focused" : ""}`,
        attrs: { "data-transaction-id": item.id },
      }, [
        element("div", {}, [
          element("h3", { text: item.description || item.category || TYPE_LABELS[item.type] }),
          element("div", { className: "item-details" }, [
            element("span", { text: item.date }),
            element("span", { className: `finance-value ${amountClass}`, text: `${item.type === "income" ? "+" : item.type === "expense" ? "−" : ""}${money(item.amount)}` }),
            element("span", { className: `finance-type finance-type-${displayType}`, text: TYPE_LABELS[displayType] }),
            element("span", { text: route }),
            item.category ? element("span", { text: item.category }) : null,
            archived ? element("span", { className: "tag", text: "已归档" }) : null,
          ].filter(Boolean)),
        ].filter(Boolean)),
        element("div", { className: "item-actions" }, [
          archived ? button("恢复", () => this.restoreTransaction(item), "button button-secondary") : null,
          !archived && !item.is_adjustment ? button("编辑", () => this.openTransaction(item)) : null,
          !archived ? button("归档", () => this.archiveTransaction(item)) : null,
        ].filter(Boolean)),
      ]);
    })));
    if (this.focusTransactionId) {
      window.requestAnimationFrame(() => {
        this.transactionList.querySelector(`[data-transaction-id="${this.focusTransactionId}"]`)?.scrollIntoView({ block: "center" });
      });
    }
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
    this.reportSummary.setAttribute("aria-busy", "true");
    const initializeAssetChart = !this.assetReport;
    const initializeCategoryChart = !this.categoryReport;
    if (initializeAssetChart) this.reportByDate.setAttribute("aria-busy", "true");
    if (initializeCategoryChart) this.reportByCategory.setAttribute("aria-busy", "true");
    this.reportState.textContent = "生成中";
    const params = new URLSearchParams();
    if (from) params.set("date_from", from);
    if (to) params.set("date_to", to);
    try {
      const [summary, report] = await Promise.all([
        api.get(`/api/finance/summary?${params}`),
        api.get(`/api/finance/reports?${params}`),
      ]);
      const totals = [
        [summary.total_assets, "总资产", "finance-asset"], [summary.total_liabilities, "总负债", "finance-liability"], [summary.net_worth, "净资产", "finance-net"],
        [summary.income, "期间收入", "finance-income"], [summary.expense, "期间支出", "finance-expense"], [summary.net_cashflow, "期间净现金流", "finance-cashflow"],
      ];
      replace(this.totals, ...totals.map(([value, label, tone]) => element("div", { className: `metric ${tone}` }, [element("strong", { text: money(value) }), element("span", { text: label })])));
      const activeBalances = summary.accounts.filter((account) => account.active || Number(account.balance) !== 0);
      replace(this.balanceList, activeBalances.length
        ? element("ul", { className: "balance-items" }, activeBalances.map((account) => element("li", { className: `finance-account-${account.kind}` }, [
          element("div", { className: "balance-account-copy" }, [
            element("span", { text: account.name }),
            element("span", { className: "muted", text: `${KIND_LABELS[account.kind]} · ${account.active ? "使用中" : "已停用"}` }),
          ]),
          element("strong", { text: money(account.balance) }),
          account.active ? button("调整余额", () => this.openBalanceAdjustment(account), "button button-quiet balance-adjustment-button") : null,
        ].filter(Boolean))))
        : emptyMessage("暂无账户余额。"));
      this.renderReport(report);
      this.reportState.textContent = `${report.date_from} — ${report.date_to}`;
    } catch (error) {
      replace(this.totals, emptyMessage("统计暂时不可用。"));
      replace(this.reportSummary, emptyMessage("报表暂时不可用。"));
      if (initializeAssetChart) replace(this.reportByDate, emptyMessage("无法生成日期报表。"));
      if (initializeCategoryChart) replace(this.reportByCategory, emptyMessage("无法生成分类报表。"));
      this.reportState.textContent = "生成失败";
      this.showError(error);
      throw error;
    } finally {
      this.totals.setAttribute("aria-busy", "false");
      this.reportSummary.setAttribute("aria-busy", "false");
      if (initializeAssetChart) this.reportByDate.setAttribute("aria-busy", "false");
      if (initializeCategoryChart) this.reportByCategory.setAttribute("aria-busy", "false");
    }
  }

  renderReport(report) {
    const totals = [
      [report.total_assets, "期末总资产", "finance-asset"],
      [report.total_liabilities, "期末总负债", "finance-liability"],
      [report.net_worth, "期末净资产", "finance-net"],
      [report.income, "期间收入", "finance-income"],
      [report.expense, "期间支出", "finance-expense"],
      [report.net_cashflow, "期间净现金流", "finance-cashflow"],
    ];
    replace(this.reportSummary, ...totals.map(([value, label, tone]) => element("div", {
      className: `metric ${tone}`,
    }, [element("strong", { text: money(value) }), element("span", { text: label })])));

    if (!this.assetReport) this.setAssetReport(report);
    if (!this.categoryReport) this.setCategoryReport(report);
  }

  setAssetReport(report) {
    this.assetReport = report;

    const assetMetrics = [
      { key: "total_assets", label: "总资产" },
      { key: "total_liabilities", label: "总负债" },
      { key: "net_worth", label: "净资产" },
    ];
    replace(this.assetMetricControls, ...assetMetrics.map((metric) => {
      const input = element("input", { attrs: { type: "checkbox", value: metric.key } });
      input.checked = this.assetMetricSelection.has(metric.key);
      input.addEventListener("change", () => {
        if (input.checked) this.assetMetricSelection.add(metric.key);
        else this.assetMetricSelection.delete(metric.key);
        this.renderAssetChart();
      });
      return element("label", { className: "finance-chart-choice" }, [input, document.createTextNode(metric.label)]);
    }));
    this.renderAssetChart();

    const dateRows = report.by_date.map((point) => [
      point.date,
      money(point.income),
      money(point.expense),
      money(point.net_cashflow),
      money(point.total_assets),
      money(point.total_liabilities),
      money(point.net_worth),
    ]);
    replace(this.reportByDate, dateRows.length
      ? reportDetails("查看逐日精确数据", reportTable(["日期", "收入", "支出", "净现金流", "总资产", "总负债", "净资产"], dateRows))
      : emptyMessage("所选横轴范围内没有可输出的数据。"));
    this.assetRangeState.textContent = `${report.date_from} — ${report.date_to}`;
  }

  setCategoryReport(report) {
    this.categoryReport = report;

    const availableCategories = new Set(report.category_series.map((series) => series.category));
    this.categorySeriesSelection = new Set(
      [...this.categorySeriesSelection].filter((category) => availableCategories.has(category)),
    );
    if (!this.categorySeriesSelection.size) {
      report.category_series.slice(0, 3).forEach((series) => this.categorySeriesSelection.add(series.category));
    }
    replace(this.categorySeriesControls, ...report.category_series.map((series) => {
      const input = element("input", { attrs: { type: "checkbox", value: series.category } });
      input.checked = this.categorySeriesSelection.has(series.category);
      input.addEventListener("change", () => {
        if (input.checked) this.categorySeriesSelection.add(series.category);
        else this.categorySeriesSelection.delete(series.category);
        this.renderCategoryChart();
      });
      return element("label", { className: "finance-chart-choice" }, [input, document.createTextNode(series.category)]);
    }));
    this.renderCategoryChart();

    const categoryRows = report.by_category.map((point) => [
      point.category,
      String(point.transaction_count),
      money(point.income),
      money(point.expense),
      money(point.net_cashflow),
    ]);
    replace(this.reportByCategory, categoryRows.length
      ? reportDetails("查看分类汇总数据", reportTable(["分类", "流水笔数", "收入", "支出", "净现金流"], categoryRows))
      : emptyMessage("所选横轴范围内没有收入或支出流水。"));
    this.categoryRangeState.textContent = `${report.date_from} — ${report.date_to}`;
  }

  chartRange(fromInput, toInput, label) {
    if (!fromInput.reportValidity() || !toInput.reportValidity()) return null;
    if (fromInput.value > toInput.value) {
      toInput.setCustomValidity(`${label}横轴终点不能早于起点。`);
      toInput.reportValidity();
      toInput.setCustomValidity("");
      return null;
    }
    return { from: fromInput.value, to: toInput.value };
  }

  async loadChartReport(kind) {
    const isAsset = kind === "asset";
    const range = this.chartRange(
      isAsset ? this.assetRangeFrom : this.categoryRangeFrom,
      isAsset ? this.assetRangeTo : this.categoryRangeTo,
      isAsset ? "资产走势" : "流水走势",
    );
    if (!range) return;
    const revisionKey = isAsset ? "assetChartRevision" : "categoryChartRevision";
    const revision = ++this[revisionKey];
    const state = isAsset ? this.assetRangeState : this.categoryRangeState;
    const chart = isAsset ? this.assetChart : this.categoryChart;
    state.textContent = "生成中";
    chart.setAttribute("aria-busy", "true");
    const params = new URLSearchParams({ date_from: range.from, date_to: range.to });
    try {
      const report = await api.get(`/api/finance/reports?${params}`);
      if (revision !== this[revisionKey]) return;
      if (isAsset) this.setAssetReport(report);
      else this.setCategoryReport(report);
    } catch (error) {
      if (revision !== this[revisionKey]) return;
      state.textContent = "生成失败";
      this.showError(error);
    } finally {
      if (revision === this[revisionKey]) chart.setAttribute("aria-busy", "false");
    }
  }

  renderAssetChart() {
    if (!this.assetReport) return;
    const labels = { total_assets: "总资产", total_liabilities: "总负债", net_worth: "净资产" };
    const dates = this.assetReport.by_date.map((point) => point.date);
    const series = [...this.assetMetricSelection].map((key) => ({
      label: labels[key],
      values: this.assetReport.by_date.map((point) => point[key]),
    }));
    renderLineChart(this.assetChart, dates, series, "资产走势折线图");
  }

  renderCategoryChart() {
    if (!this.categoryReport) return;
    const measure = this.categoryMeasure.value;
    const measureLabels = { expense: "支出", income: "收入", net_cashflow: "净现金流" };
    const selected = this.categoryReport.category_series.filter((series) => this.categorySeriesSelection.has(series.category));
    const dates = this.categoryReport.by_date.map((point) => point.date);
    const series = selected.map((item) => ({
      label: item.category,
      values: item.points.map((point) => point[measure]),
    }));
    renderBarChart(
      this.categoryChart,
      dates,
      series,
      `分类${measureLabels[measure]}走势直方图`,
      "请选择至少一个流水分类。",
    );
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

  openBalanceAdjustment(account) {
    this.resetBalanceAdjustment();
    this.adjustingAccount = account;
    this.balanceAccountName.textContent = account.name;
    this.currentBalance.textContent = money(account.balance);
    this.balanceDate.textContent = toLocalDateString();
    this.balanceForm.elements.target_balance.value = account.balance;
    this.updateBalanceDifference();
    this.balanceDialog.showModal();
    this.balanceForm.elements.target_balance.select();
  }

  resetBalanceAdjustment() {
    this.adjustingAccount = null;
    this.balanceForm.reset();
    this.balanceAccountName.textContent = "—";
    this.currentBalance.textContent = money(0);
    this.balanceDate.textContent = "—";
    this.balanceDifference.textContent = `调整差额：${money(0)}`;
  }

  updateBalanceDifference() {
    const current = Number(this.adjustingAccount?.balance || 0);
    const target = Number(this.balanceForm.elements.target_balance.value);
    const difference = Number.isFinite(target) ? target - current : 0;
    const prefix = difference > 0 ? "+" : "";
    this.balanceDifference.textContent = `调整差额：${prefix}${money(difference)}`;
  }

  closeBalanceAdjustment() {
    if (this.balanceBusy) return;
    this.balanceDialog.close();
    this.resetBalanceAdjustment();
  }

  async saveBalanceAdjustment() {
    if (this.balanceBusy || !this.adjustingAccount || !this.balanceForm.reportValidity()) return;
    this.balanceBusy = true;
    this.setDisabled(this.balanceForm, true);
    this.hideError();
    try {
      const result = await api.post(
        `/api/finance/accounts/${this.adjustingAccount.id}/balance-adjustments`,
        { target_balance: this.balanceForm.elements.target_balance.value },
      );
      this.date = result.transaction.date;
      this.dateFilter.value = this.date;
      this.replaceUrl();
      this.balanceDialog.close();
      this.resetBalanceAdjustment();
      await this.loadAll();
      this.state.textContent = "余额已调整";
    } catch (error) {
      this.showError(error);
    } finally {
      this.balanceBusy = false;
      this.setDisabled(this.balanceForm, false);
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
    this.saveAndNewTransaction.classList.toggle("is-hidden", Boolean(transaction));
    const fields = this.transactionForm.elements;
    fields.date.value = preset.date || transaction?.date || this.date;
    fields.type.value = preset.type || transaction?.type || "expense";
    fields.amount.value = preset.amount || transaction?.amount || "";
    this.categoryControl.setValue(transaction?.category || "");
    fields.description.value = preset.description || transaction?.description || "";
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
    this.saveAndNewTransaction.classList.remove("is-hidden");
    this.categoryControl.setValue("");
    this.fillAccountOptions();
    this.syncAccountFields();
  }

  resetForNextTransaction(retained) {
    this.resetTransactionForm();
    const fields = this.transactionForm.elements;
    fields.date.value = retained.date;
    fields.type.value = retained.type;
    this.fillAccountOptions();
    fields.from_account_id.value = retained.fromAccountId;
    fields.to_account_id.value = retained.toAccountId;
    this.categoryControl.setValue(retained.category);
    this.syncAccountFields();
  }

  closeTransaction() {
    if (this.transactionBusy) return;
    this.transactionDialog.close();
    this.resetTransactionForm();
  }

  async saveTransaction(continueCreating = false) {
    if (this.transactionBusy || !this.transactionForm.reportValidity()) return;
    const fields = this.transactionForm.elements;
    if (fields.type.value === "transfer" && fields.from_account_id.value === fields.to_account_id.value) {
      fields.to_account_id.setCustomValidity("转出与转入账户不能相同。");
      fields.to_account_id.reportValidity();
      fields.to_account_id.setCustomValidity("");
      return;
    }
    const creating = this.editingTransactionId == null;
    const retained = {
      date: fields.date.value,
      type: fields.type.value,
      fromAccountId: fields.from_account_id.value,
      toAccountId: fields.to_account_id.value,
      category: fields.category.value.trim(),
    };
    const payload = {
      date: fields.date.value,
      type: fields.type.value,
      amount: fields.amount.value,
      from_account_id: fields.from_account_id.value ? Number(fields.from_account_id.value) : null,
      to_account_id: fields.to_account_id.value ? Number(fields.to_account_id.value) : null,
      category: fields.category.value.trim() || null,
      description: fields.description.value.trim() || null,
    };
    this.transactionBusy = true;
    this.setDisabled(this.transactionForm, true);
    this.hideError();
    let savedForNext = false;
    try {
      if (creating) await api.post("/api/finance/transactions", payload);
      else await api.put(`/api/finance/transactions/${this.editingTransactionId}`, payload);
      this.date = payload.date;
      this.dateFilter.value = this.date;
      this.replaceUrl();
      await this.loadAll();
      if (continueCreating && creating) {
        this.resetForNextTransaction(retained);
        savedForNext = true;
      } else {
        this.transactionDialog.close();
        this.resetTransactionForm();
      }
    } catch (error) {
      this.showError(error);
    } finally {
      this.transactionBusy = false;
      this.setDisabled(this.transactionForm, false);
      if (savedForNext) this.transactionForm.elements.amount.focus();
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

  async restoreTransaction(transaction) {
    this.hideError();
    try {
      await api.post(`/api/finance/transactions/${transaction.id}/restore`, {});
      await this.loadAll();
      this.state.textContent = "流水已恢复，可编辑分类";
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
    const category = this.categoryFilter?.value.trim();
    if (category) url.searchParams.set("category", category);
    else url.searchParams.delete("category");
    if (this.allDatesFilter?.checked) url.searchParams.set("all_dates", "1");
    else url.searchParams.delete("all_dates");
    if (this.includeArchivedFilter?.checked) url.searchParams.set("include_archived", "1");
    else url.searchParams.delete("include_archived");
    if (this.focusTransactionId) url.searchParams.set("focus_transaction", String(this.focusTransactionId));
    else url.searchParams.delete("focus_transaction");
    window.history.replaceState({}, "", url);
  }
}
