(function () {
  "use strict";

  const STORAGE_KEY = "life-os.theme";
  const DEFAULT_THEME = "default";
  const THEMES = new Set([
    DEFAULT_THEME,
    "bamboo",
    "indigo",
    "water",
    "neumorphism",
    "macos-glass",
    "ghibli",
  ]);
  const LABELS = {
    default: "默认",
    bamboo: "古风竹青",
    indigo: "古风藏青",
    water: "古风水色",
    neumorphism: "新拟物派",
    "macos-glass": "macOS 毛玻璃",
    ghibli: "吉卜力风格",
  };
  const THEME_COLORS = {
    default: "#f5f3ed",
    bamboo: "#f1f0e3",
    indigo: "#243e63",
    water: "#edf6f4",
    neumorphism: "#e7ecf0",
    "macos-glass": "#dce8f2",
    ghibli: "#f5ecd7",
  };

  function readCookieTheme() {
    try {
      const prefix = `${STORAGE_KEY}=`;
      const stored = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith(prefix));
      if (!stored) return null;
      const value = decodeURIComponent(stored.slice(prefix.length));
      return THEMES.has(value) ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function readTheme() {
    try {
      const preview = new URLSearchParams(window.location.search).get("theme");
      if (THEMES.has(preview)) return preview;
    } catch (_error) {
      // Invalid or unavailable URLs fall back to the persisted preference.
    }
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (THEMES.has(stored)) return stored;
    } catch (_error) {
      // Fall through to the port-independent cookie stored in the same profile.
    }
    return readCookieTheme() || DEFAULT_THEME;
  }

  function persistTheme(theme) {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (_error) {
      // The visual switch remains available even when storage is unavailable.
    }
    try {
      // The desktop server uses a random localhost port. Cookies are scoped by
      // host rather than port, so this keeps the preference across restarts.
      document.cookie = `${STORAGE_KEY}=${encodeURIComponent(theme)}; Max-Age=31536000; Path=/; SameSite=Strict`;
    } catch (_error) {
      // The selected theme still applies for the current window.
    }
  }

  function applyTheme(theme, persist) {
    const selected = THEMES.has(theme) ? theme : DEFAULT_THEME;
    document.documentElement.dataset.theme = selected;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.setAttribute("content", THEME_COLORS[selected]);
    if (persist) persistTheme(selected);
    return selected;
  }

  const initialTheme = applyTheme(readTheme(), false);

  document.addEventListener("DOMContentLoaded", () => {
    const select = document.querySelector("[data-theme-select]");
    const status = document.querySelector("[data-theme-status]");
    if (!select) return;
    select.value = initialTheme;
    select.addEventListener("change", () => {
      const selected = applyTheme(select.value, true);
      select.value = selected;
      if (status) status.textContent = `已切换为${LABELS[selected]}，数据未改变`;
    });
  });
})();
