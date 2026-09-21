import { CalendarPage } from "./pages/calendar.js";
import { HabitsPage } from "./pages/habits.js";
import { HealthPage } from "./pages/health.js";
import { JournalPage } from "./pages/journal.js";
import { FinancePage } from "./pages/finance.js";
import { TasksPage } from "./pages/tasks.js";
import { TodayPage } from "./pages/today.js";

function showStartupError(root) {
  const notice = root.querySelector("[data-global-error]");
  const message = root.querySelector("[data-global-error-message]");
  if (!notice || !message) return;
  message.textContent = "页面初始化失败。请刷新页面；如果问题持续，请查看本机日志。";
  notice.classList.remove("is-hidden");
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-app-root]");
  if (!root) return;
  try {
    const pages = {
      calendar: CalendarPage,
      habits: HabitsPage,
      health: HealthPage,
      journal: JournalPage,
      finance: FinancePage,
      tasks: TasksPage,
      today: TodayPage,
    };
    const Page = pages[root.dataset.page] || TodayPage;
    const page = new Page(root);
    page.start();
  } catch (_error) {
    showStartupError(root);
  }
});
