const LUNAR_DAYS = [
  "",
  "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
  "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
  "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
];

let lunarFormatter = null;
try {
  lunarFormatter = new Intl.DateTimeFormat("zh-CN-u-ca-chinese", {
    month: "long",
    day: "numeric",
  });
} catch (_error) {
  // Old WebView runtimes can still use the Gregorian calendar without blocking.
}

export function lunarLabel(value) {
  if (!lunarFormatter || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return "";
  const parts = lunarFormatter.formatToParts(parsed);
  const month = parts.find((part) => part.type === "month")?.value || "";
  const day = Number(parts.find((part) => part.type === "day")?.value || 0);
  if (!month || !day) return "";
  return day === 1 ? month : (LUNAR_DAYS[day] || `${day}日`);
}
