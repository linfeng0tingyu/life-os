(function () {
  "use strict";

  var clientEvents = [];
  var nodes = null;
  var refreshTimer = null;

  function shortTime(value) {
    if (!value) return "刚刚";
    var parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value.slice(11, 19) || value;
    return parsed.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  }

  function formatBytes(value) {
    var size = Number(value) || 0;
    if (size < 1024) return size + " B";
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + " KiB";
    return (size / 1024 / 1024).toFixed(1) + " MiB";
  }

  function rememberClientEvent(level, message) {
    clientEvents.push({
      timestamp: new Date().toISOString(),
      level: level,
      logger: "frontend",
      message: String(message || "未知前端错误"),
    });
    clientEvents = clientEvents.slice(-8);
    if (nodes) {
      nodes.root.dataset.state = level === "ERROR" ? "error" : nodes.root.dataset.state;
      if (level === "ERROR") {
        nodes.label.textContent = "检测到前端异常";
        nodes.brief.textContent = "展开查看详细信息";
      }
      renderLogs(nodes.backendLogs || []);
    }
  }

  function errorLocation(event) {
    var source = event.filename ? event.filename.split("/").pop() : "";
    var position = event.lineno ? ":" + event.lineno + (event.colno ? ":" + event.colno : "") : "";
    return source ? "（" + source + position + "）" : "";
  }

  window.addEventListener("error", function (event) {
    rememberClientEvent("ERROR", (event.message || "脚本执行失败") + errorLocation(event));
  });

  window.addEventListener("unhandledrejection", function (event) {
    var reason = event.reason;
    rememberClientEvent("ERROR", reason && reason.message ? reason.message : String(reason || "异步操作失败"));
  });

  window.addEventListener("lifeos:frontend-error", function (event) {
    rememberClientEvent("ERROR", event.detail && event.detail.message ? event.detail.message : "页面初始化失败");
  });

  window.addEventListener("lifeos:api-status", function (event) {
    if (!nodes || !event.detail) return;
    var detail = event.detail;
    if (detail.state === "loading") {
      nodes.request.textContent = "请求中 · " + detail.method + " " + detail.path;
      return;
    }
    if (detail.state === "ok") {
      nodes.request.textContent = "正常 · " + detail.elapsed + " ms";
      return;
    }
    if (detail.state === "cancelled") {
      nodes.request.textContent = "已取消 · " + detail.method + " " + detail.path;
      return;
    }
    nodes.request.textContent = "失败 · " + detail.method + " " + detail.path;
    rememberClientEvent("ERROR", "接口失败：" + detail.method + " " + detail.path + " · " + (detail.message || detail.code || "未知错误"));
  });

  function makeLogItem(entry) {
    var item = document.createElement("li");
    var time = document.createElement("time");
    var message = document.createElement("span");
    item.dataset.level = entry.level || "INFO";
    time.textContent = shortTime(entry.timestamp);
    message.textContent = entry.message || "无详细信息";
    item.appendChild(time);
    item.appendChild(message);
    return item;
  }

  function renderLogs(backendLogs) {
    var items = backendLogs.concat(clientEvents).slice(-20).reverse();
    nodes.log.innerHTML = "";
    if (!items.length) {
      nodes.log.appendChild(makeLogItem({ level: "INFO", message: "暂无后台信息。" }));
    } else {
      items.forEach(function (entry) { nodes.log.appendChild(makeLogItem(entry)); });
    }
    nodes.logCount.textContent = items.length + " 条";
  }

  function backupLabel(backup) {
    if (!backup) return "未知";
    if (backup.status === "created") return "已创建 · " + (backup.filename || "自动备份");
    if (backup.status === "current") return "今日备份已是最新";
    if (backup.status === "not_run") return "测试模式未执行";
    if (backup.status === "failed") return "自动备份失败";
    return backup.status || "未知";
  }

  function applyDiagnostics(data) {
    nodes.backendLogs = data.logs && data.logs.items ? data.logs.items : [];
    nodes.service.textContent = data.status === "ok" ? "正常 · v" + data.version : "异常";
    nodes.database.textContent = data.runtime.database_ready
      ? "正常 · schema v" + data.schema_version + " · " + formatBytes(data.runtime.database_size_bytes)
      : "不可用";
    nodes.backup.textContent = backupLabel(data.backup);
    renderLogs(nodes.backendLogs);

    var hasClientError = clientEvents.some(function (entry) { return entry.level === "ERROR"; });
    var recentBackendErrors = Number(data.logs && data.logs.error_count) || 0;
    if (data.status !== "ok" || hasClientError) {
      nodes.root.dataset.state = "error";
      nodes.label.textContent = "后台或界面异常";
      nodes.brief.textContent = "展开查看错误详情";
    } else if (recentBackendErrors > 0) {
      nodes.root.dataset.state = "warning";
      nodes.label.textContent = "后台运行正常";
      nodes.brief.textContent = recentBackendErrors + " 条历史错误记录";
    } else {
      nodes.root.dataset.state = "ok";
      nodes.label.textContent = "后台运行正常";
      nodes.brief.textContent = "检查于 " + shortTime(data.checked_at);
    }
  }

  function refresh() {
    nodes.root.dataset.state = "loading";
    nodes.label.textContent = "正在检查后台";
    return fetch("/api/system/diagnostics", { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("状态接口返回 " + response.status);
        return response.json();
      })
      .then(function (payload) {
        if (!payload || payload.success !== true) throw new Error("状态接口响应无效");
        applyDiagnostics(payload.data);
      })
      .catch(function (error) {
        nodes.root.dataset.state = "error";
        nodes.label.textContent = "后台连接失败";
        nodes.brief.textContent = "展开查看错误详情";
        rememberClientEvent("ERROR", "后台状态读取失败：" + error.message);
      });
  }

  function initialize() {
    var root = document.querySelector("[data-system-status]");
    if (!root) return;
    nodes = {
      root: root,
      toggle: root.querySelector("[data-system-status-toggle]"),
      panel: root.querySelector("[data-system-status-panel]"),
      label: root.querySelector("[data-system-status-label]"),
      brief: root.querySelector("[data-system-status-brief]"),
      service: root.querySelector("[data-system-service]"),
      database: root.querySelector("[data-system-database]"),
      backup: root.querySelector("[data-system-backup]"),
      request: root.querySelector("[data-system-request]"),
      log: root.querySelector("[data-system-status-log]"),
      logCount: root.querySelector("[data-system-log-count]"),
      backendLogs: [],
    };
    nodes.toggle.addEventListener("click", function () {
      var expanded = nodes.toggle.getAttribute("aria-expanded") === "true";
      nodes.toggle.setAttribute("aria-expanded", String(!expanded));
      nodes.panel.hidden = expanded;
    });
    root.querySelector('[data-action="refresh-system-status"]').addEventListener("click", refresh);
    refresh();
    refreshTimer = window.setInterval(refresh, 30000);
    window.addEventListener("beforeunload", function () { window.clearInterval(refreshTimer); }, { once: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize);
  else initialize();
}());
