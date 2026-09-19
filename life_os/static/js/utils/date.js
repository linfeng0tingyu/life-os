const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function pad(value) {
  return String(value).padStart(2, "0");
}

export function toLocalDateString(value = new Date()) {
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

export function parseLocalDate(value) {
  const match = DATE_PATTERN.exec(value || "");
  if (!match) return null;
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) return null;
  return parsed;
}

export function normalizeDate(value, fallback = toLocalDateString()) {
  return parseLocalDate(value) ? value : fallback;
}

export function monthKey(value) {
  const parsed = typeof value === "string" ? parseLocalDate(value) : value;
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}`;
}

export function shiftMonth(value, amount) {
  const [year, month] = value.split("-").map(Number);
  const shifted = new Date(year, month - 1 + amount, 1);
  return monthKey(shifted);
}

export function monthLabel(value) {
  const [year, month] = value.split("-").map(Number);
  return `${year} 年 ${month} 月`;
}

export function longDateLabel(value) {
  const parsed = parseLocalDate(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(parsed);
}

export function dateHeading(value) {
  const parsed = parseLocalDate(value);
  return `${parsed.getMonth() + 1} 月 ${parsed.getDate()} 日`;
}

export function mondayOffset(value) {
  const [year, month] = value.split("-").map(Number);
  return (new Date(year, month - 1, 1).getDay() + 6) % 7;
}
