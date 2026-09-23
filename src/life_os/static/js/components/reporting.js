import { parseLocalDate, toLocalDateString } from "../utils/date.js";

export const PERIOD_LABELS = { week: "周", month: "月", year: "年" };

export function shiftReportAnchor(value, period, amount) {
  const parsed = parseLocalDate(value) || new Date();
  if (period === "week") parsed.setDate(parsed.getDate() + amount * 7);
  else if (period === "month") parsed.setMonth(parsed.getMonth() + amount, 1);
  else parsed.setFullYear(parsed.getFullYear() + amount, 0, 1);
  return toLocalDateString(parsed);
}

export function reportRangeLabel(report) {
  if (!report) return "";
  return `${report.date_from} 至 ${report.date_to}`;
}

export function formatDuration(minutes) {
  if (minutes == null || Number.isNaN(Number(minutes))) return "未记录";
  const value = Math.max(0, Math.round(Number(minutes)));
  const hours = Math.floor(value / 60);
  const remainder = value % 60;
  if (!hours) return `${remainder} 分钟`;
  if (!remainder) return `${hours} 小时`;
  return `${hours} 小时 ${remainder} 分钟`;
}
