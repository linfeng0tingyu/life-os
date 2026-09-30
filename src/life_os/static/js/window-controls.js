(function () {
  "use strict";

  function initialize() {
    var root = document.querySelector("[data-window-controls]");
    if (!root || root.dataset.bound === "true") return;
    var api = window.pywebview && window.pywebview.api;
    if (!api || typeof api.set_window_on_top !== "function") return;

    var button = root.querySelector("[data-action='toggle-window-on-top']");
    var label = root.querySelector("[data-window-on-top-label]");
    var state = root.querySelector("[data-window-on-top-state]");
    var enabled = false;
    root.dataset.bound = "true";
    root.classList.remove("is-hidden");

    function render(value) {
      enabled = value;
      button.setAttribute("aria-pressed", String(value));
      button.classList.toggle("is-active", value);
      label.textContent = value ? "窗口保持在最前端" : "保持窗口在最前端";
      state.textContent = value ? "已开启窗口置顶" : "窗口置顶已关闭";
    }

    button.addEventListener("click", async function () {
      if (button.disabled) return;
      button.disabled = true;
      state.textContent = "正在切换窗口状态";
      try {
        var result = await api.set_window_on_top(!enabled);
        if (!result || result.success !== true) {
          throw new Error(result && result.error ? result.error : "窗口置顶切换失败");
        }
        render(Boolean(result && result.on_top));
      } catch (error) {
        state.textContent = "窗口置顶切换失败";
        window.dispatchEvent(new CustomEvent("lifeos:frontend-error", {
          detail: { message: error && error.message ? error.message : "窗口置顶切换失败" },
        }));
      } finally {
        button.disabled = false;
      }
    });

    render(false);
  }

  window.addEventListener("pywebviewready", initialize, { once: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize);
  else initialize();
}());
