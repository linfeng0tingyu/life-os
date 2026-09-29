const PAGE_LOADERS = {
  calendar: () => import("./pages/calendar.js").then((module) => module.CalendarPage),
  habits: () => import("./pages/habits.js").then((module) => module.HabitsPage),
  health: () => import("./pages/health.js").then((module) => module.HealthPage),
  journal: () => import("./pages/journal.js").then((module) => module.JournalPage),
  finance: () => import("./pages/finance.js").then((module) => module.FinancePage),
  tasks: () => import("./pages/tasks.js").then((module) => module.TasksPage),
  today: () => import("./pages/today.js").then((module) => module.TodayPage),
  settings: () => import("./pages/settings.js").then((module) => module.SettingsPage),
};

function showStartupError(root) {
  const notice = root.querySelector("[data-global-error]");
  const message = root.querySelector("[data-global-error-message]");
  if (!notice || !message) return;
  message.textContent = "页面初始化失败。请刷新页面；如果问题持续，请查看本机日志。";
  notice.classList.remove("is-hidden");
}

document.addEventListener("DOMContentLoaded", async () => {
  const root = document.querySelector("[data-app-root]");
  if (!root) return;
  try {
    const loadPage = PAGE_LOADERS[root.dataset.page] || PAGE_LOADERS.today;
    const Page = await loadPage();
    const page = new Page(root);
    page.start();
  } catch (error) {
    console.error("Life OS page initialization failed", error);
    window.dispatchEvent(new CustomEvent("lifeos:frontend-error", {
      detail: { message: error?.message || "页面初始化失败" },
    }));
    showStartupError(root);
  }
});
