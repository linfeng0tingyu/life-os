import { TodayPage } from "./pages/today.js";

function showStartupError(root) {
  const notice = root.querySelector("[data-global-error]");
  const message = root.querySelector("[data-global-error-message]");
  message.textContent = "页面初始化失败。请刷新页面；如果问题持续，请查看本机日志。";
  notice.classList.remove("is-hidden");
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-app-root]");
  if (!root) return;
  try {
    new TodayPage(root).start();
  } catch (_error) {
    showStartupError(root);
  }
});
