// Formatting helpers for Indian financial notation. Every number in this app is a figure from an
// Indian-listed company's financial statements, so these are the house conventions, not generic
// Intl wrappers: crore for currency, a space before FY in period labels, and a date format that reads
// naturally rather than the locale default's ambiguous DD/MM/YYYY.

export function fmtCrore(value: number, decimals = 1): string {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  return `${sign}Rs ${abs.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })} crore`;
}

export function fmtPct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function fmtPctPts(value: number, decimals = 1): string {
  const direction = value >= 0 ? "up" : "down";
  return `${direction} ${Math.abs(value * 100).toFixed(decimals)} points`;
}

export function fmtDays(value: number): string {
  return `${Math.round(value)} days`;
}

export function fmtZ(value: number, decimals = 1): string {
  return `z = ${value.toFixed(decimals)}`;
}

export function fmtPeriod(period: string): string {
  const match = period.match(/^(Q\d)FY(\d+)$/);
  if (match) return `${match[1]} FY${match[2]}`;
  return period;
}

export function fmtDateIN(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(d);
}

export function fmtDuration(seconds: number): string {
  const s = Math.round(seconds);
  const min = Math.floor(s / 60);
  const sec = s % 60;
  if (min === 0) return `${sec} sec`;
  return `${min} min ${sec} sec`;
}

export function fmtNumber(value: number, decimals = 2): string {
  return value.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
