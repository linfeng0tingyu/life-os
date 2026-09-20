import { element, emptyMessage, replace } from "./dom.js";

function metric(value, label) {
  return element("div", { className: "metric" }, [
    element("strong", { text: value }),
    element("span", { text: label }),
  ]);
}

function uniqueTasks(tasks) {
  const map = new Map();
  for (const group of Object.values(tasks)) {
    for (const task of group) map.set(task.id, task);
  }
  return [...map.values()];
}

function dayDescription(day) {
  const labels = [day.calendar_day.holiday_name, day.calendar_day.custom_label].filter(Boolean);
  const type = day.calendar_day.day_type === "rest_day" ? "休息日" : "工作日";
  if (labels.length) return `这是一个${type}，已标记为${labels.join("、")}。`;
  if (day.calendar_day.explicit) return `这是你手动设定的${type}。`;
  return `这是根据星期自动推断的${type}，可前往日历补充节假日或自定义标记。`;
}

function renderOverview(day, nodes) {
  const tasks = uniqueTasks(day.tasks);
  const habitsDone = day.habits.filter((item) => item.log.status).length;
  replace(
    nodes.overview,
    element("p", { className: "day-summary-copy", text: dayDescription(day) }),
    element("div", { className: "summary-metrics" }, [
      metric(String(tasks.length), "相关事项"),
      metric(`${habitsDone}/${day.habits.length}`, "习惯完成"),
      metric(`¥ ${day.finance.net_cashflow}`, "当日净现金流"),
    ]),
  );
  nodes.overview.setAttribute("aria-busy", "false");
}

function renderTasks(day, container) {
  const groups = [
    ["逾期", day.tasks.overdue],
    ["当日到期", day.tasks.due],
    ["当日计划", day.tasks.scheduled],
  ];
  const seen = new Set();
  const rows = [];
  for (const [label, tasks] of groups) {
    for (const task of tasks) {
      if (seen.has(task.id)) continue;
      seen.add(task.id);
      rows.push(element("li", { className: "item-row", attrs: { "data-id": task.id } }, [
        element("div", {}, [
          element("p", { text: task.title }),
          element("small", { text: task.category || "未分类" }),
        ]),
        element("span", { className: "tag", text: label }),
      ]));
    }
  }
  replace(container, rows.length ? element("ul", { className: "item-list" }, rows) : emptyMessage("这一天没有需要关注的任务。"));
}

function renderRhythm(day, container) {
  const health = day.health;
  const values = health ? [
    [health.sleep_duration_minutes ? `${Math.floor(health.sleep_duration_minutes / 60)}时${health.sleep_duration_minutes % 60}分` : "未记录", "睡眠时长"],
    [health.weight_kg != null ? `${health.weight_kg} kg` : "未记录", "体重"],
    [health.exercise_minutes != null ? `${health.exercise_minutes} 分钟` : "未记录", "运动"],
    [health.body_status || "未记录", "身体健康"],
  ] : [
    ["未记录", "睡眠时长"], ["未记录", "体重"],
    ["未记录", "运动"], ["未记录", "身体健康"],
  ];
  replace(container, ...values.map(([value, label]) => element("div", { className: "rhythm-item" }, [
    element("strong", { text: value }),
    element("span", { text: label }),
  ])));
}

function renderHabits(day, container) {
  if (!day.habits.length) {
    replace(container, emptyMessage("还没有启用的习惯；可在 M5 中创建和管理。"));
    return;
  }
  const rows = day.habits.map(({ habit, log }) => element("li", {
    className: "item-row",
    attrs: { "data-id": habit.id },
  }, [
    element("div", {}, [
      element("p", { text: habit.name }),
      element("small", { text: habit.category || habit.description || "日常习惯" }),
    ]),
    element("span", { className: "tag", text: log.status ? "已完成" : "待完成" }),
  ]));
  replace(container, element("ul", { className: "item-list" }, rows));
}

function renderJournal(day, container) {
  if (!day.journal?.content) {
    replace(container, emptyMessage("这一天还没有日记。"));
    return;
  }
  replace(container, element("p", { className: "journal-preview", text: day.journal.content }));
}

function renderFinance(day, container) {
  const summary = element("div", { className: "summary-metrics" }, [
    metric(`¥ ${day.finance.income}`, "收入"),
    metric(`¥ ${day.finance.expense}`, "支出"),
    metric(`¥ ${day.finance.net_cashflow}`, "净现金流"),
  ]);
  const labels = {
    income: ["收入", "+"],
    expense: ["支出", "−"],
    transfer: ["转账", ""],
  };
  const transactions = day.finance.transactions.map((transaction) => {
    const [typeLabel, sign] = labels[transaction.type] || [transaction.type, ""];
    const description = transaction.description || transaction.category || transaction.note || "未填写说明";
    return element("li", { className: "item-row", attrs: { "data-id": transaction.id } }, [
      element("div", {}, [
        element("p", { text: description }),
        element("small", { text: [transaction.category, typeLabel].filter(Boolean).join(" · ") }),
      ]),
      element("span", { className: "tag finance-amount", text: `${sign}¥ ${transaction.amount}` }),
    ]);
  });
  replace(
    container,
    summary,
    transactions.length
      ? element("ul", { className: "item-list finance-list" }, transactions)
      : emptyMessage("这一天没有财务流水。"),
  );
}

export class DaySummary {
  constructor(root) {
    this.nodes = {
      panel: root.querySelector("[data-day-panel]"),
      state: root.querySelector("[data-day-state]"),
      overview: root.querySelector("[data-day-overview]"),
      tasks: root.querySelector("[data-task-summary]"),
      rhythm: root.querySelector("[data-rhythm-summary]"),
      habits: root.querySelector("[data-habit-summary]"),
      journal: root.querySelector("[data-journal-summary]"),
      finance: root.querySelector("[data-finance-summary]"),
    };
  }

  loading() {
    this.nodes.state.textContent = "加载中";
    this.nodes.panel.dataset.state = "loading";
    this.nodes.overview.setAttribute("aria-busy", "true");
    for (const key of ["tasks", "rhythm", "habits", "journal", "finance"]) {
      replace(this.nodes[key], emptyMessage("正在读取…"));
    }
  }

  ready(day) {
    this.nodes.state.textContent = "已载入";
    this.nodes.panel.dataset.state = "ready";
    renderOverview(day, this.nodes);
    renderTasks(day, this.nodes.tasks);
    renderRhythm(day, this.nodes.rhythm);
    renderHabits(day, this.nodes.habits);
    renderJournal(day, this.nodes.journal);
    renderFinance(day, this.nodes.finance);
  }

  error() {
    this.nodes.state.textContent = "读取失败";
    this.nodes.panel.dataset.state = "error";
    this.nodes.overview.setAttribute("aria-busy", "false");
    replace(this.nodes.overview, emptyMessage("数据暂时不可用，请使用页面上方的重试按钮。"));
    for (const key of ["tasks", "rhythm", "habits", "journal", "finance"]) {
      replace(this.nodes[key], emptyMessage("暂时无法显示。"));
    }
  }
}
